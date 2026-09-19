import numpy as np

import logging
import asyncio
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional

from backend.utils.time_utils import utc_now, datetime_to_iso
from backend.utils.coordinate_transforms import compute_range, compute_relative_velocity
from backend.utils.orbital_math import compute_altitude


logger = logging.getLogger("orbit_sentinel.maneuver_calculator")

@dataclass
class ManeuverPlan:
    norad_id: str
    satellite_name: str
    conjunction_event_id: str
    burn_epoch_utc: datetime
    delta_v_vector_ms: List[float]  # 3 elements (x, y, z) in m/s
    delta_v_magnitude_ms: float
    burn_duration_seconds: float
    estimated_fuel_cost_kg: float
    algorithm: str
    rl_agent_used: bool = False
    pre_maneuver_miss_km: float = 0.0
    post_maneuver_miss_km: float = 0.0
    confidence_score: float = 0.0
    new_tle1_estimate: str = ""
    new_tle2_estimate: str = ""
    maneuver_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        """
        Converts the ManeuverPlan dataclass instance to a clean JSON-serializable dictionary.
        """
        res = asdict(self)
        res["burn_epoch_utc"] = datetime_to_iso(res["burn_epoch_utc"])
        return res

def compute_burn_duration(
    delta_v_ms: float, 
    thruster_force_n: float = 1.0, 
    specific_impulse_s: float = 220.0, 
    satellite_mass_kg: float = 500.0
) -> Tuple[float, float]:
    """
    Computes burn duration and propellant mass usage using the Tsiolkovsky Rocket Equation.
    """
    g0 = 9.80665
    ve = specific_impulse_s * g0
    
    # Propellant consumed (kg)
    dm_kg = satellite_mass_kg * (1.0 - np.exp(-delta_v_ms / ve))
    
    # Burn duration based on mass flow rate matching thrust output
    mass_flow_rate = thruster_force_n / ve
    if mass_flow_rate > 0:
        burn_duration_seconds = dm_kg / mass_flow_rate
    else:
        burn_duration_seconds = 0.0
        
    return (float(burn_duration_seconds), float(dm_kg))

def compute_impulsive_maneuver(
    state_vector_a: dict, 
    state_vector_b: dict, 
    miss_distance_km: float, 
    tca_utc: datetime, 
    conjunction_event_id: str, 
    target_miss_distance_km: float = 1.5
) -> ManeuverPlan:
    """
    Computes a linear in-track impulsive burn plan and validates it via re-propagation.
    """
    now = utc_now()
    time_to_tca_s = (tca_utc - now).total_seconds()
    if time_to_tca_s <= 0:
        raise ValueError("Time of Closest Approach (TCA) must be positioned in future chronological timelines.")
        
    norad_id = state_vector_a.get("norad_id", "UNKNOWN")
    satellite_name = state_vector_a.get("name", "UNKNOWN")
    
    vx = state_vector_a.get("vx", 0.0)
    vy = state_vector_a.get("vy", 0.0)
    vz = state_vector_a.get("vz", 0.0)
    
    # Calculate velocity unit vector to orient the in-track burn direction
    vel_mag = np.sqrt(vx**2 + vy**2 + vz**2)
    if vel_mag < 1e-9:
        vel_unit = np.array([1.0, 0.0, 0.0])
    else:
        vel_unit = np.array([vx, vy, vz]) / vel_mag
        
    # Calculate Delta-V magnitude
    # Using linear estimate to find required DV
    delta_v_magnitude_ms = abs(target_miss_distance_km - miss_distance_km) * 1000.0 / (time_to_tca_s * 0.5)

    # Dynamic delta-V cap based on time to TCA — a 5 m/s hard cap silently under-burns late-notice emergencies
    if time_to_tca_s > 43200:    # > 12 hours: small burn is sufficient
        max_dv = 2.0
    elif time_to_tca_s > 7200:   # 2–12 hours: moderate burn
        max_dv = 10.0
    elif time_to_tca_s > 1800:   # 30 min – 2 hours: emergency burn
        max_dv = 50.0
    else:                         # < 30 minutes: maximum thrust
        max_dv = 100.0
    delta_v_magnitude_ms = float(np.clip(delta_v_magnitude_ms, 0.01, max_dv))

    if delta_v_magnitude_ms > 10.0:
        logger.warning(
            f"Late-notice emergency maneuver for {norad_id}: delta_v={delta_v_magnitude_ms:.2f} m/s "
            f"(time_to_tca={time_to_tca_s:.0f}s). Review conjunction urgency."
        )
    
    # Delta-V vector projection (m/s)
    delta_v_vector = (vel_unit * delta_v_magnitude_ms).tolist()
    
    # Apply burn delta-V and propagate position linearly to TCA
    post_burn_vx = vx + delta_v_vector[0] / 1000.0
    post_burn_vy = vy + delta_v_vector[1] / 1000.0
    post_burn_vz = vz + delta_v_vector[2] / 1000.0

    propagated_a = {
        "x": state_vector_a.get("x", 0.0) + post_burn_vx * time_to_tca_s,
        "y": state_vector_a.get("y", 0.0) + post_burn_vy * time_to_tca_s,
        "z": state_vector_a.get("z", 0.0) + post_burn_vz * time_to_tca_s
    }

    # APPLY CLOHESSY-WILTSHIRE CORRECTION
    pos_a = np.array([state_vector_a.get("x", 0.0), state_vector_a.get("y", 0.0), state_vector_a.get("z", 0.0)])
    r_km = float(np.linalg.norm(pos_a))
    n_rad_s = np.sqrt(398600.4418 / r_km**3)
    dv_intrack_kms = np.dot(np.array(delta_v_vector), vel_unit) / 1000.0
    cw_secular_km = -3.0 * dv_intrack_kms * time_to_tca_s
    nt = n_rad_s * time_to_tca_s
    cw_radial_km = (2.0 * dv_intrack_kms / n_rad_s) * (1.0 - np.cos(nt))
    intrack_corr = cw_secular_km - (dv_intrack_kms * time_to_tca_s)
    r_unit = pos_a / r_km
    
    propagated_a["x"] += vel_unit[0] * intrack_corr + r_unit[0] * cw_radial_km
    propagated_a["y"] += vel_unit[1] * intrack_corr + r_unit[1] * cw_radial_km
    propagated_a["z"] += vel_unit[2] * intrack_corr + r_unit[2] * cw_radial_km
    
    post_maneuver_miss_km = float(compute_range(propagated_a, state_vector_b))
    
    # Calculate burn epochs mid-way towards TCA checkpoint
    burn_epoch_utc = now + timedelta(seconds=time_to_tca_s / 2.0)
    
    # Retrieve burn properties matching average smallsat platforms
    burn_duration_seconds, dm_kg = compute_burn_duration(delta_v_magnitude_ms)
    
    confidence_score = float(min(0.95, 0.7 + (miss_distance_km / 5.0) * 0.25))
    
    return ManeuverPlan(
        norad_id=norad_id,
        satellite_name=satellite_name,
        conjunction_event_id=conjunction_event_id,
        burn_epoch_utc=burn_epoch_utc,
        delta_v_vector_ms=delta_v_vector,
        delta_v_magnitude_ms=delta_v_magnitude_ms,
        burn_duration_seconds=burn_duration_seconds,
        estimated_fuel_cost_kg=dm_kg,
        algorithm="Impulsive In-Track (Propagated)",
        pre_maneuver_miss_km=float(miss_distance_km),
        post_maneuver_miss_km=float(post_maneuver_miss_km),
        confidence_score=confidence_score
    )

async def compute_optimal_maneuver(
    state_vector_a: dict, 
    conjunction_event: Any, 
    use_rl: bool = False
) -> ManeuverPlan:
    """
    Computes optimal spacecraft maneuver plans, executing either analytical impulsive math
    or leveraging reinforcement learning agent models if available.
    """
    # Create baseline impulsive maneuver plan first
    baseline_plan = compute_impulsive_maneuver(
        state_vector_a=state_vector_a,
        state_vector_b=conjunction_event.state_vector_at_tca_b,
        miss_distance_km=conjunction_event.miss_distance_km,
        tca_utc=conjunction_event.tca_utc,
        conjunction_event_id=conjunction_event.event_id
    )
    
    if not use_rl:
        logger.info(f"Impulsive maneuver generated for NORAD {baseline_plan.norad_id}. Propagated New Miss: {baseline_plan.post_maneuver_miss_km:.4f} km")
        return baseline_plan
        
    try:
        from backend.ml.rl_maneuver_agent import get_optimal_action
        
        # Request optimal flight adjustments from the agent
        rl_dv_action = await get_optimal_action(state_vector_a, conjunction_event)
        
        if rl_dv_action and len(rl_dv_action) == 3:
            dv_vector = [float(x) for x in rl_dv_action]
            dv_mag = float(np.sqrt(np.sum(np.array(dv_vector) ** 2)))
            
            # Recalculate burn durations adjusted to the RL action vector
            burn_duration_seconds, dm_kg = compute_burn_duration(dv_mag)
            
            # Re-propagate for RL action to get high-fidelity miss distance
            now_rl = utc_now()
            time_to_tca_s_rl = max(1.0, (conjunction_event.tca_utc - now_rl).total_seconds())

            post_burn_vx_rl = state_vector_a.get("vx", 0.0) + dv_vector[0] / 1000.0
            post_burn_vy_rl = state_vector_a.get("vy", 0.0) + dv_vector[1] / 1000.0
            post_burn_vz_rl = state_vector_a.get("vz", 0.0) + dv_vector[2] / 1000.0

            propagated_a_rl = {
                "x": state_vector_a.get("x", 0.0) + post_burn_vx_rl * time_to_tca_s_rl,
                "y": state_vector_a.get("y", 0.0) + post_burn_vy_rl * time_to_tca_s_rl,
                "z": state_vector_a.get("z", 0.0) + post_burn_vz_rl * time_to_tca_s_rl
            }

            # APPLY CLOHESSY-WILTSHIRE CORRECTION FOR RL BRANCH
            vx_rl = state_vector_a.get("vx", 0.0)
            vy_rl = state_vector_a.get("vy", 0.0)
            vz_rl = state_vector_a.get("vz", 0.0)
            vel_mag_rl = np.sqrt(vx_rl**2 + vy_rl**2 + vz_rl**2)
            vel_unit_rl = np.array([vx_rl, vy_rl, vz_rl]) / vel_mag_rl if vel_mag_rl > 1e-9 else np.array([1.0, 0.0, 0.0])

            pos_a_rl = np.array([state_vector_a.get("x", 0.0), state_vector_a.get("y", 0.0), state_vector_a.get("z", 0.0)])
            r_km_rl = float(np.linalg.norm(pos_a_rl))
            n_rad_s_rl = np.sqrt(398600.4418 / r_km_rl**3)
            dv_intrack_kms_rl = np.dot(np.array(dv_vector), vel_unit_rl) / 1000.0
            cw_secular_km_rl = -3.0 * dv_intrack_kms_rl * time_to_tca_s_rl
            nt_rl = n_rad_s_rl * time_to_tca_s_rl
            cw_radial_km_rl = (2.0 * dv_intrack_kms_rl / n_rad_s_rl) * (1.0 - np.cos(nt_rl))
            intrack_corr_rl = cw_secular_km_rl - (dv_intrack_kms_rl * time_to_tca_s_rl)
            r_unit_rl = pos_a_rl / r_km_rl

            propagated_a_rl["x"] += vel_unit_rl[0] * intrack_corr_rl + r_unit_rl[0] * cw_radial_km_rl
            propagated_a_rl["y"] += vel_unit_rl[1] * intrack_corr_rl + r_unit_rl[1] * cw_radial_km_rl
            propagated_a_rl["z"] += vel_unit_rl[2] * intrack_corr_rl + r_unit_rl[2] * cw_radial_km_rl

            post_maneuver_miss_km = float(compute_range(propagated_a_rl, conjunction_event.state_vector_at_tca_b))
            
            confidence_score = float(min(0.98, 0.75 + (conjunction_event.miss_distance_km / 5.0) * 0.23))
            
            logger.info(f"Optimized RL maneuver plan for {baseline_plan.norad_id}. Propagated Miss Projection: {post_maneuver_miss_km:.4f} km")
            return ManeuverPlan(
                norad_id=baseline_plan.norad_id,
                satellite_name=baseline_plan.satellite_name,
                conjunction_event_id=baseline_plan.conjunction_event_id,
                burn_epoch_utc=baseline_plan.burn_epoch_utc,
                delta_v_vector_ms=dv_vector,
                delta_v_magnitude_ms=dv_mag,
                burn_duration_seconds=burn_duration_seconds,
                estimated_fuel_cost_kg=dm_kg,
                algorithm="RL PPO (Propagated)",
                rl_agent_used=True,
                pre_maneuver_miss_km=baseline_plan.pre_maneuver_miss_km,
                post_maneuver_miss_km=float(post_maneuver_miss_km),
                confidence_score=confidence_score
            )
            
    except ImportError:
        logger.warning("RL Maneuver Agent module not present. Falling back to analytical baseline.")
    except Exception as exc:
        logger.error(f"Error computing RL maneuver: {exc}. Utilizing analytical baseline...")
        
    return baseline_plan