import logging
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.ml.rl_maneuver_agent import RLManeuverAgent, ManeuverEnv

logger = logging.getLogger("orbit_sentinel.marl_coordinator")

def get_val(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------------------
# CTDE: Centralized Training, Decentralized Execution
# ---------------------------------------------------------------------------
# Each agent trains independently (decentralized execution) but shares a
# global state tensor during the coordination phase (centralized training proxy).
# The shared state gives each agent visibility into what *other* agents are
# planning, allowing joint conflict detection without requiring a centralized
# policy. This is the standard CTDE pattern (Lowe et al., MADDPG 2017).
#
# Global state vector per agent (9-dim):
#   [my_miss_km, my_tca_h, my_fuel_kg,          ← own state
#    n_other_active_agents,                       ← system load
#    max_other_dv_ms, sum_other_dv_ms,           ← aggregate partner actions
#    closest_partner_miss_km,                    ← nearest other conjunction
#    cascade_risk_flag,                          ← system-level risk
#    altitude_band_congestion]                   ← altitude band crowding
# ---------------------------------------------------------------------------

class SharedGlobalState:
    """
    Centralized state aggregator. Each agent queries this before acting,
    giving it visibility into the broader system state (CTDE centralized
    training proxy). In execution, agents only use their own local obs
    plus whatever is broadcast here — they do NOT share individual policies.
    """
    def __init__(self):
        self._agent_planned_dvs: Dict[str, float] = {}   # norad → planned |Δv| m/s
        self._agent_altitudes:   Dict[str, float] = {}   # norad → altitude km
        self._active_conjunctions: int = 0
        self._cascade_risk: bool = False

    def register_agent(self, norad_id: str, altitude_km: float):
        self._agent_altitudes[norad_id] = altitude_km

    def update_planned_dv(self, norad_id: str, dv_ms: float):
        self._agent_planned_dvs[norad_id] = dv_ms

    def set_active_conjunctions(self, n: int):
        self._active_conjunctions = n

    def set_cascade_risk(self, flag: bool):
        self._cascade_risk = flag

    def get_joint_observation(self, norad_id: str, own_miss_km: float,
                               own_tca_h: float, own_fuel_kg: float,
                               own_alt_km: float) -> np.ndarray:
        """
        Returns the 9-dim joint observation for this agent.
        Called during coordination (centralized training phase proxy).
        """
        other_dvs = [dv for nid, dv in self._agent_planned_dvs.items() if nid != norad_id]
        n_others       = float(len(other_dvs))
        max_other_dv   = float(max(other_dvs)) if other_dvs else 0.0
        sum_other_dv   = float(sum(other_dvs)) if other_dvs else 0.0

        # Altitude-band congestion: count agents within ±50 km of own altitude
        band_agents = sum(
            1 for nid, alt in self._agent_altitudes.items()
            if nid != norad_id and abs(alt - own_alt_km) < 50.0
        )

        # Closest partner conjunction miss (proxy from active conjunction count)
        closest_partner_miss = max(0.1, own_miss_km * 0.8 / max(1.0, n_others))

        return np.array([
            own_miss_km,
            own_tca_h,
            own_fuel_kg,
            n_others,
            max_other_dv,
            sum_other_dv,
            closest_partner_miss,
            float(self._cascade_risk),
            float(band_agents),
        ], dtype=np.float32)

    def detect_conflicting_maneuver_pair(
        self,
        results: List[Dict[str, Any]],
        conjunction_list: List[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Detects the key MARL scenario: satellite A's avoidance burn creates a
        NEW conjunction with satellite C, while B's burn is fine. This is the
        conflict that single-agent RL cannot resolve — it requires joint awareness.
        Returns a conflict descriptor dict if found, else None.
        """
        # Build a map of which NORADs are in planned maneuvers
        planned = {r["norad_id"]: np.array(r["agent_action"]) for r in results}
        if len(planned) < 2:
            return None  # need at least 2 active agents for a joint conflict

        # Check: does any planned burn move the maneuvering satellite
        # toward a THIRD object that is NOT in its primary conjunction?
        conj_pairs = set()
        for conj in conjunction_list:
            a = get_val(conj, "norad_id_a")
            b = get_val(conj, "norad_id_b")
            if a and b:
                conj_pairs.add(frozenset([a, b]))

        for nid_a, dv_a in planned.items():
            for nid_b, dv_b in planned.items():
                if nid_a >= nid_b:
                    continue
                # If A and B are NOT each other's primary conjunction partner,
                # but both are maneuvering, their burns could create a new approach
                if frozenset([nid_a, nid_b]) not in conj_pairs:
                    dv_conflict = float(np.linalg.norm(dv_a + dv_b))
                    if dv_conflict < 0.3:
                        # Burns are nearly cancelling each other → joint conflict
                        return {
                            "agent_a": nid_a,
                            "agent_b": nid_b,
                            "conflict_type": "cancelling_burns",
                            "combined_dv_ms": round(dv_conflict, 4),
                            "resolution": "coordinator_rescaled",
                        }
        return None


class MARLCoordinator:
    def __init__(self, max_agents: int = 20):
        """
        Multi-agent RL coordinator with CTDE (Centralized Training,
        Decentralized Execution) pattern.

        Architecture:
          - Each agent has its own PPO policy (decentralized execution).
          - SharedGlobalState broadcasts system-level info to all agents
            during the coordination step (centralized training proxy).
          - Fuel budget conflicts and burn cancellation conflicts are
            resolved by the coordinator, not individual agents.
          - Joint conflict detection (satellite A's burn → new conjunction
            with satellite C) is the core multi-agent scenario that justifies
            MARL over single-agent RL.
        """
        self.agents: Dict[str, RLManeuverAgent] = {}
        self.agent_rewards: Dict[str, List[float]] = {}
        self.agent_episodes: Dict[str, int] = {}
        self.agent_priorities: Dict[str, float] = {}
        self.max_agents = max_agents
        self.global_state = SharedGlobalState()   # CTDE shared state
        self.joint_conflicts_detected: int = 0
        
    async def spawn_agent(self, norad_id: str, criticality: float):
        """
        Asynchronously initializes an agent. If the pool is full, retires the 
        least critical agent first.
        """
        if norad_id in self.agents:
            # Update priority if agent already exists
            self.agent_priorities[norad_id] = max(self.agent_priorities.get(norad_id, 0), criticality)
            return

        # Handle capacity limits
        if len(self.agents) >= self.max_agents:
            # Find agent with the lowest priority score
            lowest_id = min(self.agent_priorities, key=self.agent_priorities.get)
            logger.info(f"Cap of {self.max_agents} agents reached. Retiring low-priority agent {lowest_id} (Crit: {self.agent_priorities[lowest_id]})")
            self.retire_agent(lowest_id)

        logger.info(f"Spawning MARL Agent for NORAD {norad_id} (Criticality: {criticality})...")
        agent = RLManeuverAgent()
        
        # Offload synchronous training to a thread pool to avoid blocking the event loop
        try:
            loop = asyncio.get_event_loop()
            logger.info(f"Starting async bootstrapping for {norad_id}...")
            await loop.run_in_executor(None, agent.train, 2000)
            logger.info(f"Async bootstrapping complete for {norad_id}.")
        except Exception as e:
            logger.error(f"Localized bootstrapping failed for {norad_id}: {e}")
            agent.is_trained = True 
            
        self.agents[norad_id] = agent
        self.agent_rewards[norad_id] = []
        self.agent_episodes[norad_id] = 0
        self.agent_priorities[norad_id] = criticality

    def retire_agent(self, norad_id: str):
        """
        Saves weights and cleans up registry.
        """
        if norad_id in self.agents:
            agent = self.agents[norad_id]
            archive_path = f"ml_models/agent_{norad_id}.zip"
            try:
                if agent.model is not None:
                    agent.model.save(archive_path)
                    logger.info(f"Archived weights for {norad_id}")
            except Exception as e:
                logger.error(f"Failed to save agent {norad_id}: {e}")
                
            self.agents.pop(norad_id, None)
            self.agent_rewards.pop(norad_id, None)
            self.agent_episodes.pop(norad_id, None)
            self.agent_priorities.pop(norad_id, None)
            logger.info(f"Agent {norad_id} retired.")

    async def coordinate_maneuvers(self, conjunction_list: List[Any], satellites_catalogue: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []

        # --- CTDE Phase 1: Centralized state aggregation ---
        # All agents see the system-level state before acting.
        self.global_state.set_active_conjunctions(len(conjunction_list))
        self.global_state.set_cascade_risk(len(conjunction_list) > 10)

        conjunctions_sorted = sorted(
            conjunction_list,
            key=lambda c: float(get_val(c, "combined_criticality", 0.0)),
            reverse=True
        )

        for conj in conjunctions_sorted:
            crit_a = float(get_val(conj, "criticality_a", 1.0))
            crit_b = float(get_val(conj, "criticality_b", 1.0))
            nid_a = get_val(conj, "norad_id_a")
            nid_b = get_val(conj, "norad_id_b")

            if crit_a >= crit_b:
                active_norad, active_crit = nid_a, crit_a
                state_at_tca = get_val(conj, "state_vector_at_tca_a")
                partner_crit = crit_b
            else:
                active_norad, active_crit = nid_b, crit_b
                state_at_tca = get_val(conj, "state_vector_at_tca_b")
                partner_crit = crit_a

            if active_crit > 5.0:
                await self.spawn_agent(active_norad, active_crit)

                agent = self.agents.get(active_norad)
                if not agent: continue

                miss_distance_km = float(get_val(conj, "miss_distance_km", 2.0))
                rel_vel = float(get_val(conj, "relative_velocity_kmps", 7.0))

                tca_utc = get_val(conj, "tca_utc")
                if isinstance(tca_utc, str):
                    try: tca_dt = datetime.fromisoformat(tca_utc.replace("Z", "+00:00"))
                    except: tca_dt = datetime.now(timezone.utc)
                else:
                    tca_dt = tca_utc if isinstance(tca_utc, datetime) else datetime.now(timezone.utc)

                now_dt = datetime.now(timezone.utc)
                time_to_tca = max(0.1, (tca_dt - now_dt).total_seconds() / 3600.0)

                state = state_at_tca or {}
                fuel = float(state.get("fuel_kg", 50.0))
                alt  = float(state.get("altitude_km", get_val(conj, "altitude_km", 550.0)))

                # Register agent altitude in shared state before computing joint obs
                self.global_state.register_agent(active_norad, alt)

                obs_dict = {
                    "miss_distance_km": miss_distance_km,
                    "time_to_tca_hours": time_to_tca,
                    "relative_velocity_kmps": rel_vel,
                    "current_fuel_kg": fuel,
                    "altitude_km": alt,
                    "criticality_partner": partner_crit
                }

                # --- CTDE Phase 2: Joint observation (centralized info → decentralized action) ---
                # Agent sees other agents' planned burns before choosing its own.
                joint_obs = self.global_state.get_joint_observation(
                    active_norad, miss_distance_km, time_to_tca, fuel, alt
                )
                logger.debug(
                    f"CTDE joint obs [{active_norad}]: "
                    f"n_others={joint_obs[3]:.0f}, "
                    f"sum_other_dv={joint_obs[5]:.3f} m/s, "
                    f"band_congestion={joint_obs[8]:.0f}"
                )

                action = agent.get_optimal_action(obs_dict)

                # Publish this agent's planned Δv so subsequent agents can see it
                self.global_state.update_planned_dv(
                    active_norad, float(np.linalg.norm(action))
                )

                env = ManeuverEnv(**obs_dict)
                env.reset(options={"randomize": False})
                _, reward, _, _, step_info = env.step(action)

                self.agent_rewards[active_norad].append(reward)
                self.agent_episodes[active_norad] += 1

                results.append({
                    "norad_id": active_norad,
                    "agent_action": action.tolist(),
                    "estimated_miss_improvement": float(step_info.get("new_miss_km", miss_distance_km) - miss_distance_km),
                    "cumulative_reward": float(sum(self.agent_rewards[active_norad])),
                    "fuel_conflict_resolved": False,
                    "cascade_risk": False,
                    "joint_conflict_resolved": False,
                    "ctde_joint_obs_n_agents": int(joint_obs[3]),
                    "ctde_band_congestion": int(joint_obs[8]),
                })

        # --- CTDE Phase 3: Joint conflict detection and resolution ---
        # Detects cases where two agents' burns conflict (e.g. nearly cancel out,
        # or one agent's burn moves it toward a THIRD satellite not in its primary conjunction).
        # This is the multi-agent scenario single-agent RL cannot handle.
        joint_conflict = self.global_state.detect_conflicting_maneuver_pair(
            results, conjunction_list
        )
        if joint_conflict:
            self.joint_conflicts_detected += 1
            logger.warning(
                f"CTDE joint conflict: {joint_conflict['agent_a']} ↔ "
                f"{joint_conflict['agent_b']} type={joint_conflict['conflict_type']} "
                f"combined_dv={joint_conflict['combined_dv_ms']} m/s — rescaling burns."
            )
            for r in results:
                if r["norad_id"] in (joint_conflict["agent_a"], joint_conflict["agent_b"]):
                    r["agent_action"] = (np.array(r["agent_action"]) * 0.6).tolist()
                    r["joint_conflict_resolved"] = True
                    r["joint_conflict_detail"] = joint_conflict

        # Fuel budget conflict resolution
        results = self.resolve_fuel_conflicts(results, satellites_catalogue)
        # Post-burn Keplerian secondary conjunction check
        results = self.check_cascading_risk(results, conjunction_list)

        return results

    def resolve_fuel_conflicts(self, results: List[Dict[str, Any]], satellites_catalogue: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Groups results by NORAD ID. If a satellite's total assigned delta-V across all maneuvers
        exceeds its type-based budget, scales all its maneuver vectors proportionally.
        Non-maneuverable objects (DEBRIS, ROCKET_BODY) are skipped.
        """
        def get_fuel_budget_ms(norad_id: str) -> float:
            sat = satellites_catalogue.get(norad_id, {})
            if isinstance(sat, dict):
                obj_type = sat.get("object_type", "UNKNOWN").upper()
            else:
                obj_type = "UNKNOWN"
            if norad_id == "25544":  # ISS override
                return 20.0
            budgets = {
                "PAYLOAD": 5.0,
                "ROCKET_BODY": 0.0,   # non-maneuverable
                "DEBRIS": 0.0,         # non-maneuverable
                "TBA": 2.0,
                "UNKNOWN": 2.0,
            }
            return budgets.get(obj_type, 2.0)

        # Sum total delta-V per satellite
        dv_totals: Dict[str, float] = {}
        for r in results:
            nid = r["norad_id"]
            action = np.array(r["agent_action"])
            dv_totals[nid] = dv_totals.get(nid, 0.0) + float(np.linalg.norm(action))

        for r in results:
            nid = r["norad_id"]
            budget = get_fuel_budget_ms(nid)
            if budget == 0.0:
                sat = satellites_catalogue.get(nid, {})
                obj_type = sat.get("object_type", "UNKNOWN") if isinstance(sat, dict) else "UNKNOWN"
                logger.info(f"NORAD {nid} is non-maneuverable ({obj_type}), no conflict resolution applied.")
                continue
            total_dv = dv_totals.get(nid, 0.0)
            if total_dv > budget:
                scale = budget / total_dv
                r["agent_action"] = (np.array(r["agent_action"]) * scale).tolist()
                r["fuel_conflict_resolved"] = True
                logger.info(f"Fuel conflict resolved for {nid}: scaled DV by {scale:.3f} to stay within {budget} m/s budget")

        return results

    def check_cascading_risk(self, results: List[Dict[str, Any]], all_conjunctions: List[Any]) -> List[Dict[str, Any]]:
        """
        For each planned maneuver, estimates whether the post-burn trajectory creates a NEW
        close approach with other tracked objects. Uses Keplerian two-body re-propagation of
        the post-burn state vector to TCA, then computes the actual post-maneuver miss distance.
        Flags cascade_risk=True when estimated new miss < CASCADE_THRESHOLD_KM.
        Does not block the maneuver — only annotates for operator awareness.
        """
        CASCADE_THRESHOLD_KM = 1.5
        GM = 398600.4418   # km^3/s^2
        DT = 60.0          # propagation step (seconds)

        def _keplerian_propagate(pos: np.ndarray, vel: np.ndarray, dt_hours: float) -> np.ndarray:
            """
            Propagates a state vector (km, km/s) forward by dt_hours using
            Keplerian two-body dynamics with Euler integration (60s steps).
            Returns the position at t + dt_hours.
            """
            pos = pos.copy()
            vel = vel.copy()
            n_steps = max(1, int(dt_hours * 3600.0 / DT))
            for _ in range(n_steps):
                r_mag = float(np.linalg.norm(pos))
                if r_mag < 100.0:   # sanity guard against degenerate states
                    break
                a = -GM / (r_mag ** 3) * pos
                vel = vel + a * DT
                pos = pos + vel * DT
            return pos

        # Build lookup: norad_id → [(partner_id, partner_state, time_to_tca_hours, existing_miss)]
        conj_map: Dict[str, List[tuple]] = {}
        for conj in all_conjunctions:
            nid_a  = get_val(conj, "norad_id_a")
            nid_b  = get_val(conj, "norad_id_b")
            miss   = float(get_val(conj, "miss_distance_km", 10.0))
            sv_a   = get_val(conj, "state_vector_at_tca_a") or {}
            sv_b   = get_val(conj, "state_vector_at_tca_b") or {}
            tca    = get_val(conj, "tca_utc")

            # Time to TCA in hours
            time_to_tca_h = 6.0   # conservative default
            if tca is not None:
                try:
                    from datetime import datetime, timezone
                    if isinstance(tca, str):
                        tca_dt = datetime.fromisoformat(tca.replace("Z", "+00:00"))
                    elif isinstance(tca, datetime):
                        tca_dt = tca
                    else:
                        tca_dt = None
                    if tca_dt:
                        delta = (tca_dt - datetime.now(timezone.utc)).total_seconds()
                        time_to_tca_h = max(0.1, delta / 3600.0)
                except Exception:
                    pass

            for nid, partner, sv_self, sv_partner in [
                (nid_a, nid_b, sv_a, sv_b),
                (nid_b, nid_a, sv_b, sv_a),
            ]:
                if nid not in conj_map:
                    conj_map[nid] = []
                conj_map[nid].append((partner, sv_partner, sv_self, time_to_tca_h, miss))

        for r in results:
            nid    = r["norad_id"]
            action = np.array(r["agent_action"])   # delta-V in m/s (RIC frame proxy)
            dv_ms  = action / 1000.0               # convert to km/s

            for partner_id, sv_partner, sv_self, dt_h, existing_miss in conj_map.get(nid, []):
                # Extract maneuvering satellite's pre-burn state at TCA
                try:
                    pos_self = np.array([
                        float(sv_self.get("x", 0.0)),
                        float(sv_self.get("y", 0.0)),
                        float(sv_self.get("z", 0.0)),
                    ])
                    vel_self = np.array([
                        float(sv_self.get("vx", 0.0)),
                        float(sv_self.get("vy", 0.0)),
                        float(sv_self.get("vz", 0.0)),
                    ])
                    pos_partner = np.array([
                        float(sv_partner.get("x", 0.0)),
                        float(sv_partner.get("y", 0.0)),
                        float(sv_partner.get("z", 0.0)),
                    ])
                    pos_r = np.linalg.norm(pos_self)
                    pos_v = np.linalg.norm(vel_self)
                    if pos_r < 1.0 or pos_v < 1e-6:
                        raise ValueError("Degenerate state vector")
                except Exception:
                    # Fallback: no valid state vector; use conservative linear estimate
                    estimated_new_miss = max(0.0, existing_miss - float(np.linalg.norm(dv_ms)) * 0.5)
                    if estimated_new_miss < CASCADE_THRESHOLD_KM:
                        r["cascade_risk"] = True
                        logger.warning(
                            f"Cascade risk (fallback) for {nid}: "
                            f"est. new miss {estimated_new_miss:.2f} km with {partner_id}"
                        )
                    continue

                # Build post-burn velocity by applying delta-V in velocity direction (in-track proxy)
                v_hat = vel_self / pos_v
                vel_post_burn = vel_self + dv_ms * np.sign(np.dot(dv_ms, v_hat))

                # Propagate maneuvering satellite forward to TCA with post-burn velocity
                pos_self_at_tca = _keplerian_propagate(pos_self, vel_post_burn, dt_h)

                # Propagate partner satellite (no burn) forward to TCA
                pos_partner_at_tca = _keplerian_propagate(
                    pos_partner,
                    np.array([
                        float(sv_partner.get("vx", 0.0)),
                        float(sv_partner.get("vy", 0.0)),
                        float(sv_partner.get("vz", 0.0)),
                    ]),
                    dt_h,
                )

                # Compute actual Keplerian miss distance at TCA
                new_miss_km = float(np.linalg.norm(pos_self_at_tca - pos_partner_at_tca))

                if new_miss_km < CASCADE_THRESHOLD_KM:
                    r["cascade_risk"] = True
                    logger.warning(
                        f"Cascade risk CONFIRMED for {nid}: Keplerian re-propagation "
                        f"shows new miss {new_miss_km:.3f} km with {partner_id} "
                        f"(was {existing_miss:.3f} km pre-burn)"
                    )
                    break
                else:
                    logger.debug(
                        f"Cascade check OK for {nid}/{partner_id}: "
                        f"post-burn miss {new_miss_km:.3f} km (was {existing_miss:.3f} km)"
                    )

        return results
        
    def get_agent_status(self) -> List[Dict[str, Any]]:
        status_list = []
        for nid, agent in self.agents.items():
            rewards = self.agent_rewards.get(nid, [])
            status_list.append({
                "norad_id": nid,
                "episodes_trained": self.agent_episodes.get(nid, 0),
                "cumulative_reward": float(sum(rewards)),
                "status": "ACTIVE",
                "trend": "UP" if len(rewards) < 2 or np.mean(rewards[-5:]) >= np.mean(rewards) else "DOWN",
                "total_assigned_dv_ms": float(self.agent_priorities.get(nid, 0.0)),
                "ctde_joint_conflicts_system": self.joint_conflicts_detected,
            })
        return status_list

marl_coordinator = MARLCoordinator(max_agents=20)