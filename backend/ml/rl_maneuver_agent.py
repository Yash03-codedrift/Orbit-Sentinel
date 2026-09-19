"""
rl_maneuver_agent.py — PPO-based collision avoidance maneuver optimizer.

Reward design follows CARA/JSC operational criteria:
  • Pc-shaped reward using the 1×10⁻⁴ NASA maneuver threshold (Foster 1992 / Chan 2008)
  • Potential-based continuous shaping so gradient is never zero
  • Fuel cost as fraction of remaining budget (not absolute ΔV penalty)
  • Semi-major axis drift penalty for altitude preservation
  • Urgency scaling via inverse time-to-TCA weighting
"""

import numpy as np
import gymnasium as gym
try:
    from stable_baselines3 import PPO
except ImportError:
    PPO = None
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("orbit_sentinel.rl_maneuver_agent")

# ─────────────────────────────────────────────────────────────────────────────
# PHYSICAL / OPERATIONAL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
GM_KM3 = 398600.4418          # km³ s⁻²
RE_KM  = 6378.137             # km
G0     = 9.80665              # m s⁻²
ISP_S  = 220.0                # Hydrazine monoprop Isp (s)
SAT_MASS_KG = 500.0           # Wet mass reference

# NASA/CARA maneuver decision threshold
PC_THRESHOLD = 1e-4

# Combined covariance hard-body radius (1σ HBR, m) — standard 10 m cross-section
HBR_M = 10.0

# Miss-distance safety target (km) — operationally accepted 2σ gate
MISS_SAFE_KM = 2.0

# Max ΔV per action step (m/s) — generous so agent can handle late-notice burns
MAX_DV_MS = 5.0


# ─────────────────────────────────────────────────────────────────────────────
# FOSTER-CHAN Pc CALCULATOR  (2-D Gaussian, circular HBR)
# ─────────────────────────────────────────────────────────────────────────────
def foster_chan_pc(miss_km: float, sigma_km: float = 0.1, hbr_km: float = HBR_M / 1000.0) -> float:
    """
    Analytic 2-D Pc for a circular combined covariance (Chan 2008, eq. 3).
    Uses the Poisson series approximation valid for Pc < 0.1.

    σ_combined is treated as isotropic in the conjunction plane.
    In practice you would pass the eigenvalues of the projected covariance;
    here we use a representative 100 m (0.1 km) 1σ, adjustable by caller.
    """
    if miss_km <= 0.0 or sigma_km <= 0.0:
        return 1.0

    r   = miss_km / sigma_km          # normalised miss
    rho = hbr_km  / sigma_km          # normalised HBR

    # Zeroth-order term of the Poisson series (dominant contribution)
    pc_approx = (rho ** 2 / (r ** 2)) * np.exp(-0.5 * r ** 2)
    return float(np.clip(pc_approx, 0.0, 1.0))


def pc_reward_signal(pc: float) -> float:
    """
    Continuous reward signal centred on the NASA 1e-4 threshold.
    Returns:
      +1.0 when Pc is well below threshold (safe)
       0.0 at exactly the threshold
      −1.0 when Pc >> threshold (dangerous)

    Shaped as a sigmoid on log10(Pc) so the agent always has a gradient.
    """
    if pc <= 0.0:
        return 1.0
    if pc >= 1.0:
        return -1.0
    log_pc   = np.log10(pc)               # e.g. −4 at threshold
    log_thr  = np.log10(PC_THRESHOLD)     # −4.0
    # Shift so threshold → 0, safe side → positive
    scaled   = (log_thr - log_pc)         # positive when pc < threshold
    # Soft-clip via tanh so signal stays in (−1, +1) everywhere
    return float(np.tanh(scaled / 2.0))


# ─────────────────────────────────────────────────────────────────────────────
# POTENTIAL FUNCTION  (for Potential-Based Reward Shaping, Ng et al. 1999)
# ─────────────────────────────────────────────────────────────────────────────
def phi(miss_km: float, time_to_tca_h: float, pc: float) -> float:
    """
    State potential Φ(s).
    Shaping bonus F = γ·Φ(s') − Φ(s) is added to every reward.
    This guarantees the optimal policy is unchanged while providing
    a dense gradient for the agent.
    """
    # Miss-distance component: linear ramp from 0 at 0 km to 1.0 at MISS_SAFE_KM
    miss_term = np.clip(miss_km / MISS_SAFE_KM, 0.0, 1.0)

    # Pc component: maps Pc → 0 (safe) … 1 (critical) via log scale
    if pc > 0:
        pc_term = np.clip((np.log10(PC_THRESHOLD) - np.log10(pc)) / 4.0, 0.0, 1.0)
        # pc_term > 0 means we're BELOW threshold (good) — invert for potential
        pc_term = 1.0 - pc_term
    else:
        pc_term = 0.0

    # Time urgency: higher potential when time is short (encourages early action)
    urgency = 1.0 / (1.0 + time_to_tca_h)

    return float((miss_term * 0.5 + pc_term * 0.5) * urgency)


# ─────────────────────────────────────────────────────────────────────────────
# SEMI-MAJOR AXIS CHANGE  (from impulsive ΔV via vis-viva + CW)
# ─────────────────────────────────────────────────────────────────────────────
def delta_sma_km(altitude_km: float, dv_intrack_kms: float) -> float:
    """
    First-order change in semi-major axis due to a tangential (in-track) impulse.
    Δa ≈ 2·a · Δv / v_circ    (linearised vis-viva)
    """
    a_km   = RE_KM + altitude_km
    v_circ = np.sqrt(GM_KM3 / a_km)          # km s⁻¹
    return float(2.0 * a_km * abs(dv_intrack_kms) / v_circ)


# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────
class ManeuverEnv(gym.Env):
    """
    Conjunction avoidance environment with:
      • Continuous Pc-shaped reward (Foster-Chan)
      • Potential-based dense shaping
      • Fuel cost as fraction of remaining budget
      • Altitude / SMA drift penalty
      • Urgency scaling with time-to-TCA
    """
    metadata = {"render_modes": []}

    # Observation indices
    OBS_MISS   = 0
    OBS_TIME   = 1
    OBS_RELVEL = 2
    OBS_FUEL   = 3
    OBS_ALT    = 4
    OBS_CRIT   = 5
    OBS_LOG_PC = 6   # log10(Pc) — gives agent direct Pc information

    OBS_DIM = 7

    def __init__(
        self,
        miss_distance_km:       float = 2.0,
        time_to_tca_hours:      float = 6.0,
        relative_velocity_kmps: float = 7.0,
        current_fuel_kg:        float = 50.0,
        altitude_km:            float = 550.0,
        criticality_partner:    float = 5.0,
        sigma_covariance_km:    float = 0.1,
    ):
        super().__init__()
        self.MAX_STEPS = 10

        # Observation: [miss_km, t_tca_h, rel_vel, fuel_kg, alt_km, crit, log10_Pc]
        self.obs_low  = np.array([0.0,  0.0, 0.0,   0.0,   200.0, 1.0, -20.0], dtype=np.float32)
        self.obs_high = np.array([50.0, 72.0, 15.0, 200.0, 2000.0, 10.0, 0.0], dtype=np.float32)

        self.observation_space = gym.spaces.Box(
            low=self.obs_low, high=self.obs_high, dtype=np.float32
        )

        # ΔV action in RIC (Radial, In-track, Cross-track), m/s
        self.action_space = gym.spaces.Box(
            low=-MAX_DV_MS, high=MAX_DV_MS, shape=(3,), dtype=np.float32
        )

        # Episode state
        self.miss_distance_km       = miss_distance_km
        self.time_to_tca_hours      = time_to_tca_hours
        self.relative_velocity_kmps = relative_velocity_kmps
        self.current_fuel_kg        = current_fuel_kg
        self.initial_fuel_kg        = current_fuel_kg
        self.altitude_km            = altitude_km
        self.criticality_partner    = criticality_partner
        self.sigma_covariance_km    = sigma_covariance_km
        self.current_step           = 0

    # ── Randomise episode on reset ─────────────────────────────────────────
    def reset(self, seed=None, options=None) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        rng = self.np_random

        self.miss_distance_km       = float(rng.uniform(0.05, 4.0))
        self.time_to_tca_hours      = float(rng.uniform(0.5, 48.0))
        self.relative_velocity_kmps = float(rng.uniform(0.5, 15.0))
        self.current_fuel_kg        = float(rng.uniform(10.0, 120.0))
        self.initial_fuel_kg        = self.current_fuel_kg
        self.altitude_km            = float(rng.uniform(300.0, 1500.0))
        self.criticality_partner    = float(rng.uniform(1.0, 10.0))
        # Covariance spread — representative range 50 m … 300 m (0.05 … 0.3 km)
        self.sigma_covariance_km    = float(rng.uniform(0.05, 0.30))
        self.current_step           = 0

        self._prev_phi = phi(
            self.miss_distance_km,
            self.time_to_tca_hours,
            foster_chan_pc(self.miss_distance_km, self.sigma_covariance_km),
        )
        return self._get_obs(), {}

    # ── Observation builder ────────────────────────────────────────────────
    def _get_obs(self) -> np.ndarray:
        pc = foster_chan_pc(self.miss_distance_km, self.sigma_covariance_km)
        log_pc = float(np.log10(max(pc, 1e-20)))
        obs = np.array([
            self.miss_distance_km,
            self.time_to_tca_hours,
            self.relative_velocity_kmps,
            self.current_fuel_kg,
            self.altitude_km,
            self.criticality_partner,
            log_pc,
        ], dtype=np.float32)
        return np.clip(obs, self.obs_low, self.obs_high)

    # ── Physics step ──────────────────────────────────────────────────────
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, dict]:
        self.current_step += 1

        dv_r   = float(action[0]) / 1000.0   # km/s  radial
        dv_t   = float(action[1]) / 1000.0   # km/s  in-track
        dv_n   = float(action[2]) / 1000.0   # km/s  cross-track
        dv_mag = float(np.linalg.norm(action))  # m/s magnitude

        # ── Clohessy-Wiltshire miss distance propagation ──────────────────
        a_km = RE_KM + self.altitude_km
        n    = np.sqrt(GM_KM3 / a_km**3)          # rad/s mean motion
        tau  = self.time_to_tca_hours * 3600.0     # s to TCA
        nt   = n * tau

        delta_r = (dv_r / n) * np.sin(nt) - (2.0 * dv_t / n) * (1.0 - np.cos(nt))
        delta_s = (2.0 * dv_r / n) * (1.0 - np.cos(nt)) + (4.0 * dv_t / n) * np.sin(nt) - 3.0 * dv_t * tau
        delta_c = (dv_n / n) * np.sin(nt)

        new_miss = float(np.sqrt(
            max(0.0, (self.miss_distance_km + delta_r)**2 + delta_s**2 + delta_c**2)
        ))

        # ── Pc before and after ───────────────────────────────────────────
        pc_before = foster_chan_pc(self.miss_distance_km, self.sigma_covariance_km)
        pc_after  = foster_chan_pc(new_miss,              self.sigma_covariance_km)

        # ── Fuel consumption (Tsiolkovsky) ────────────────────────────────
        ve        = ISP_S * G0 / 1000.0   # km/s effective exhaust velocity
        dm_kg     = SAT_MASS_KG * (1.0 - np.exp(-dv_mag / 1000.0 / ve))
        self.current_fuel_kg = max(0.0, self.current_fuel_kg - dm_kg)

        # ── Altitude drift (semi-major axis change) ───────────────────────
        sma_delta_km = delta_sma_km(self.altitude_km, dv_t)  # in-track drives SMA

        # ─────────────────────────────────────────────────────────────────
        # REWARD COMPUTATION
        # ─────────────────────────────────────────────────────────────────

        # 1. Primary Pc-shaped signal  ∈ (−1, +1)
        r_pc = pc_reward_signal(pc_after)

        # 2. Urgency scaling: a Pc=1e-4 burn at t=1h counts 48× more than t=48h
        #    (inverse time, capped to avoid inf at t≈0)
        urgency = 1.0 / max(self.time_to_tca_hours, 0.25)

        r_pc_weighted = r_pc * urgency

        # 3. Potential-based shaping  F = γ·Φ(s') − Φ(s)  (γ=1, undiscounted)
        phi_next = phi(new_miss, max(self.time_to_tca_hours - 1.0/6.0, 0.0), pc_after)
        phi_shaping = phi_next - self._prev_phi
        self._prev_phi = phi_next

        # 4. Fuel cost as fraction of remaining budget
        #    Cost is 0 if no fuel left, and penalises more heavily when fuel is scarce
        if self.initial_fuel_kg > 0:
            fuel_fraction_used = dm_kg / max(self.current_fuel_kg + dm_kg, 1e-3)
        else:
            fuel_fraction_used = 1.0
        r_fuel = -fuel_fraction_used * 5.0    # penalty in [−5, 0]

        # 5. Altitude/SMA drift penalty — penalise orbit lowering proportional to change
        #    CARA threshold: flag maneuvers that change altitude > 1 km
        r_alt = -min(sma_delta_km, 5.0) * 0.5   # penalty in [−2.5, 0]

        # 6. Hard penalties
        r_out_of_fuel = -20.0 if self.current_fuel_kg <= 0.0 else 0.0

        # 7. Terminal bonus/penalty
        r_terminal = 0.0
        terminated = new_miss >= MISS_SAFE_KM and pc_after < PC_THRESHOLD
        truncated  = self.current_step >= self.MAX_STEPS

        if terminated:
            # Successfully cleared threshold — scaled by how much margin we have
            pc_margin_bonus = max(0.0, np.log10(PC_THRESHOLD) - np.log10(max(pc_after, 1e-20)))
            r_terminal = 30.0 + pc_margin_bonus * 5.0
        elif truncated and not terminated:
            # Failed to resolve in budget
            r_terminal = -15.0

        # Total reward — urgency-weighted Pc signal dominates, shaped by potential
        reward = (
            r_pc_weighted * 10.0
            + phi_shaping  * 5.0
            + r_fuel
            + r_alt
            + r_out_of_fuel
            + r_terminal
        )

        self.miss_distance_km = new_miss

        info = {
            "new_miss_km":  new_miss,
            "pc_after":     pc_after,
            "pc_before":    pc_before,
            "dv_mag_ms":    dv_mag,
            "dm_kg":        dm_kg,
            "sma_delta_km": sma_delta_km,
            "r_pc":         r_pc,
            "urgency":      urgency,
            "r_fuel":       r_fuel,
        }
        return self._get_obs(), float(reward), terminated, truncated, info


# ─────────────────────────────────────────────────────────────────────────────
# PPO AGENT WRAPPER
# ─────────────────────────────────────────────────────────────────────────────
class RLManeuverAgent:
    MODEL_PATH     = "ml_models/ppo_maneuver_agent.zip"
    VECNORM_PATH   = "ml_models/ppo_vecnorm.pkl"

    def __init__(self):
        self.model      = None
        self.vec_norm   = None          # VecNormalize stats if available
        self.is_trained = False
        self.training_metrics = {}
        os.makedirs("ml_models", exist_ok=True)

    # ── Training ──────────────────────────────────────────────────────────
    def train(self, total_timesteps: int = 500_000):
        logger.info(f"Training PPO agent ({total_timesteps} steps) with CARA-grade reward design …")

        class MetricsCallback(BaseCallback):
            def __init__(self):
                super().__init__()
                self.episode_rewards: list = []
                self.episode_lengths: list = []
                self.pc_finals:       list = []

            def _on_step(self) -> bool:
                if len(self.model.ep_info_buffer) > 0:
                    for ep in self.model.ep_info_buffer:
                        self.episode_rewards.append(float(ep["r"]))
                        self.episode_lengths.append(int(ep["l"]))
                return True

        # Parallel envs for faster training
        n_envs = min(8, os.cpu_count() or 1)

        def make_env():
            def _init():
                env = ManeuverEnv()
                env = Monitor(env)
                return env
            return _init

        # DummyVecEnv avoids subprocess-spawn issues on servers / Docker
        from stable_baselines3.common.vec_env import DummyVecEnv
        vec_env = DummyVecEnv([make_env() for _ in range(n_envs)])

        vec_norm = VecNormalize(vec_env, norm_obs=True, norm_reward=True, clip_obs=10.0)

        self.model = PPO(
            "MlpPolicy",
            vec_norm,
            verbose=0,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=256,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,           # encourage exploration
            policy_kwargs=dict(net_arch=[256, 256, 128]),
        )

        callback = MetricsCallback()
        self.model.learn(total_timesteps=total_timesteps, callback=callback, progress_bar=False)
        self.model.save(self.MODEL_PATH)
        vec_norm.save(self.VECNORM_PATH)
        self.vec_norm = vec_norm

        # Persist training curve
        ep_r = callback.episode_rewards
        curve_path = self.MODEL_PATH.replace(".zip", "_training_curve.json")
        with open(curve_path, "w") as f:
            json.dump({
                "episode_rewards":  ep_r[-500:],
                "episode_lengths":  callback.episode_lengths[-500:],
                "total_timesteps":  total_timesteps,
                "final_mean_reward": float(np.mean(ep_r[-50:])) if ep_r else 0.0,
                "reward_design": "CARA-grade: Pc-shaped, potential-based, fuel-fraction, SMA-drift, urgency-weighted",
                "pc_threshold":  PC_THRESHOLD,
                "miss_safe_km":  MISS_SAFE_KM,
            }, f, indent=2)

        self.is_trained = True
        logger.info(f"Training complete. Final mean reward (last 50 eps): {float(np.mean(ep_r[-50:])) if ep_r else 0.0:.3f}")

    # ── Load ──────────────────────────────────────────────────────────────
    def load(self) -> bool:
        if not os.path.exists(self.MODEL_PATH):
            return False
        try:
            self.model = PPO.load(self.MODEL_PATH)
            if os.path.exists(self.VECNORM_PATH):
                from stable_baselines3.common.vec_env import DummyVecEnv
                dummy = DummyVecEnv([lambda: Monitor(ManeuverEnv())])
                self.vec_norm = VecNormalize.load(self.VECNORM_PATH, dummy)
                self.vec_norm.training = False
                self.vec_norm.norm_reward = False
            self.is_trained = True
            curve_path = self.MODEL_PATH.replace(".zip", "_training_curve.json")
            if os.path.exists(curve_path):
                try:
                    with open(curve_path, "r") as f:
                        self.training_metrics = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load PPO training curve metrics: {e}")
            return True
        except Exception as e:
            logger.error(f"Model load failed: {e}")
            return False

    # ── Inference ─────────────────────────────────────────────────────────
    def get_optimal_action(self, observation_dict: Dict[str, Any]) -> np.ndarray:
        if not self.is_trained or self.model is None:
            # Physics-informed fallback: small cross-track nudge
            return np.array([0.0, 0.0, 0.2], dtype=np.float32)

        miss_km  = float(observation_dict.get("miss_distance_km",       2.0))
        t_tca_h  = float(observation_dict.get("time_to_tca_hours",      6.0))
        rel_vel  = float(observation_dict.get("relative_velocity_kmps", 7.0))
        fuel     = float(observation_dict.get("current_fuel_kg",       50.0))
        alt      = float(observation_dict.get("altitude_km",          550.0))
        crit     = float(observation_dict.get("criticality_partner",    5.0))
        sigma    = float(observation_dict.get("sigma_covariance_km",    0.1))

        pc      = foster_chan_pc(miss_km, sigma)
        log_pc  = float(np.log10(max(pc, 1e-20)))

        obs = np.array([miss_km, t_tca_h, rel_vel, fuel, alt, crit, log_pc], dtype=np.float32)
        env = ManeuverEnv()
        obs = np.clip(obs, env.obs_low, env.obs_high)

        action, _ = self.model.predict(obs, deterministic=True)
        return np.array(action, dtype=np.float32)

    # ── Utility: expose computed Pc to callers ─────────────────────────────
    @staticmethod
    def compute_pc(miss_km: float, sigma_km: float = 0.1) -> float:
        return foster_chan_pc(miss_km, sigma_km)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE SINGLETON
# ─────────────────────────────────────────────────────────────────────────────
rl_agent = RLManeuverAgent()


async def initialize_rl_agent() -> None:
    """Load or train the model at startup."""
    if rl_agent.load():
        try:
            env  = ManeuverEnv()
            obs, _ = env.reset()
            rl_agent.model.predict(obs, deterministic=True)
            logger.info("RL Agent loaded and verified (CARA-grade reward design).")
            return
        except Exception as e:
            logger.critical(f"RL Agent verification failed: {e}")
            rl_agent.is_trained = False

    if not rl_agent.is_trained:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: rl_agent.train(total_timesteps=500_000))


async def get_optimal_action(
    state_vector: Dict[str, Any],
    conjunction_event: Any,
) -> np.ndarray:
    """
    Module-level entry point used by ManeuverCalculator.
    Converts domain objects to the 7-dim observation expected by the model.
    """
    if not rl_agent.is_trained:
        if not rl_agent.load():
            logger.warning("RL Agent unavailable — returning physics fallback.")
            return np.array([0.0, 0.0, 0.2], dtype=np.float32)

    tca_utc = getattr(conjunction_event, "tca_utc", datetime.now(timezone.utc))
    if isinstance(tca_utc, str):
        try:
            tca_utc = datetime.fromisoformat(tca_utc.replace("Z", "+00:00"))
        except ValueError:
            tca_utc = datetime.now(timezone.utc)

    time_to_tca_h = max(0.1, (tca_utc - datetime.now(timezone.utc)).total_seconds() / 3600.0)

    obs_dict = {
        "miss_distance_km":       float(getattr(conjunction_event, "miss_distance_km",  2.0)),
        "time_to_tca_hours":      time_to_tca_h,
        "relative_velocity_kmps": float(getattr(conjunction_event, "relative_velocity_kmps", 7.0)),
        "current_fuel_kg":        float(state_vector.get("fuel_kg",   50.0)),
        "altitude_km":            float(state_vector.get("altitude_km", 550.0)),
        "criticality_partner":    float(getattr(conjunction_event, "criticality_b", 5.0)),
        # Use covariance from event if available, else default
        "sigma_covariance_km":    float(getattr(conjunction_event, "sigma_km", 0.1)),
    }

    return rl_agent.get_optimal_action(obs_dict)
