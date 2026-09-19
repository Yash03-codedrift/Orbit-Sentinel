import logging
import asyncio
import numpy as np
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional
from scipy.integrate import dblquad

from backend.core.spatial_index import build_spatial_index, find_close_pairs, filter_same_constellation, get_positions_snapshot
from backend.utils.orbital_math import compute_altitude
from backend.utils.coordinate_transforms import compute_range, compute_relative_velocity
from backend.utils.time_utils import utc_now, datetime_to_iso

try:
    from backend.ml.trajectory_lstm import lstm_predictor as _lstm_predictor
except ImportError:
    _lstm_predictor = None

logger = logging.getLogger("orbit_sentinel.conjunction_detector")

@dataclass
class ConjunctionEvent:
    detected_at: datetime
    norad_id_a: str
    norad_id_b: str
    name_a: str
    name_b: str
    tca_utc: datetime
    miss_distance_km: float
    relative_velocity_kmps: float
    collision_probability_chan: float
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    risk_score: float = 0.0
    risk_level: str = "LOW"
    object_type_a: str = "UNKNOWN"
    object_type_b: str = "UNKNOWN"
    criticality_a: float = 1.0
    criticality_b: float = 1.0
    combined_criticality: float = 0.0
    altitude_km: float = 0.0
    state_vector_at_tca_a: dict = field(default_factory=dict)
    state_vector_at_tca_b: dict = field(default_factory=dict)
    already_maneuvered: bool = False
    resolved: bool = False
    lstm_uncertainty_a: float = 0.0
    lstm_uncertainty_b: float = 0.0
    pc_lower_1sigma: float = 0.0
    pc_upper_1sigma: float = 0.0
    covariance_source: str = "conservative_default"

    def to_dict(self) -> dict:
        res = asdict(self)
        res["detected_at"] = datetime_to_iso(res["detected_at"])
        res["tca_utc"] = datetime_to_iso(res["tca_utc"])
        return res

def _interpolate_state(pt_prev: dict, pt_next: dict, factor: float) -> dict:
    """Linearly interpolates state vectors for reporting at the calculated TCA."""
    interpolated = {}
    for key in ["x", "y", "z", "vx", "vy", "vz", "lat", "lon", "alt"]:
        if key in pt_prev and key in pt_next:
            interpolated[key] = pt_prev[key] + factor * (pt_next[key] - pt_prev[key])
    return interpolated

def find_tca_between_pair(
    positions_a: List[dict], 
    positions_b: List[dict], 
    timestamps: List[datetime]
) -> Tuple[datetime, float, dict, dict]:
    """
    Refined TCA search using a wide-bracket parabolic fit.
    1. Finds discrete minimum index.
    2. Brackets ±3 indices (30-minute window for 5-min intervals).
    3. Fits a parabola to distance^2 to find the sub-sample analytical minimum.
    """
    n = len(timestamps)
    distances_sq = []
    for i in range(n):
        pos_a = np.array([positions_a[i]["x"], positions_a[i]["y"], positions_a[i]["z"]])
        pos_b = np.array([positions_b[i]["x"], positions_b[i]["y"], positions_b[i]["z"]])
        distances_sq.append(np.sum((pos_a - pos_b)**2))

    min_idx = np.argmin(distances_sq)
    
    # Widen bracket to ±3 for parabolic stability
    start_idx = max(0, min_idx - 3)
    end_idx = min(n - 1, min_idx + 3)
    
    if end_idx - start_idx < 2:
        return (timestamps[min_idx], np.sqrt(distances_sq[min_idx]), positions_a[min_idx], positions_b[min_idx])

    # Time relative to the start of our window in seconds
    t_ref = timestamps[start_idx]
    x_times = np.array([(timestamps[i] - t_ref).total_seconds() for i in range(start_idx, end_idx + 1)])
    y_dists_sq = np.array(distances_sq[start_idx:end_idx + 1])

    # Fit 2nd degree polynomial: d^2 = at^2 + bt + c
    poly = np.polyfit(x_times, y_dists_sq, 2)
    a, b, c = poly

    # Vertex of parabola is at t = -b / 2a
    if a > 0:  # Ensure it's a minimum
        t_min_secs = -b / (2 * a)
        # Constrain to window
        t_min_secs = np.clip(t_min_secs, x_times[0], x_times[-1])
    else:
        t_min_secs = x_times[np.argmin(y_dists_sq)]

    refined_tca = t_ref + timedelta(seconds=t_min_secs)
    
    # Determine which discrete interval the refined time falls into for interpolation
    interp_idx = start_idx
    for i in range(start_idx, end_idx):
        if x_times[i-start_idx] <= t_min_secs <= x_times[i+1-start_idx]:
            interp_idx = i
            break
            
    span = (timestamps[interp_idx+1] - timestamps[interp_idx]).total_seconds()
    factor = (t_min_secs - (timestamps[interp_idx] - t_ref).total_seconds()) / span if span > 0 else 0
    
    state_a = _interpolate_state(positions_a[interp_idx], positions_a[interp_idx+1], factor)
    state_b = _interpolate_state(positions_b[interp_idx], positions_b[interp_idx+1], factor)
    
    refined_dist = np.sqrt(max(0, a * t_min_secs**2 + b * t_min_secs + c))
    
    return (refined_tca, refined_dist, state_a, state_b)

def estimate_lstm_uncertainty(norad_id: str, positions_list: List[dict]) -> float:
    """
    Uses the LSTM trajectory predictor to estimate positional uncertainty for a satellite.
    Takes the last 10 position history entries and returns the predicted deviation magnitude (km).
    Falls back to 0.1 km (100 m default) if LSTM is not trained or prediction fails.
    """
    if _lstm_predictor is None or not getattr(_lstm_predictor, "is_trained", False):
        return 0.1

    history = positions_list[-10:] if len(positions_list) >= 10 else positions_list
    if len(history) < 2:
        return 0.1

    try:
        sequence = [
            {"x": float(pt.get("x", 0.0)), "y": float(pt.get("y", 0.0)), "z": float(pt.get("z", 0.0)),
             "vx": float(pt.get("vx", 0.0)), "vy": float(pt.get("vy", 0.0)), "vz": float(pt.get("vz", 0.0))}
            for pt in history
        ]
        deviation = _lstm_predictor.predict_deviation(sequence)
        if isinstance(deviation, dict):
            dx = deviation.get("dx_km", 0.0)
            dy = deviation.get("dy_km", 0.0)
            dz = deviation.get("dz_km", 0.0)
            return float(np.sqrt(dx**2 + dy**2 + dz**2))
        return float(np.linalg.norm(np.asarray(deviation)[:3]))
    except Exception as e:
        logger.debug(f"LSTM uncertainty estimation failed for {norad_id}: {e}")
        return 0.1


def compute_collision_probability_chan(
    state_a: dict,
    state_b: dict,
    miss_distance_km: float,
    combined_radius_km: float = 0.02,  # 20 meters
    lstm_uncertainty_a: float = 0.0,
    lstm_uncertainty_b: float = 0.0,
) -> dict:
    """
    Implements 2D Probability of Collision (Pc) using the Chan/Foster formulation.
    Projects the combined covariance into the encounter plane (normal to relative velocity).
    Returns a dict with pc_nominal, pc_lower_1sigma, pc_upper_1sigma, sigma_r_km, covariance_source.
    """
    # 1. Setup Relative State
    r_a = np.array([state_a['x'], state_a['y'], state_a['z']])
    r_b = np.array([state_b['x'], state_b['y'], state_b['z']])
    v_a = np.array([state_a['vx'], state_a['vy'], state_a['vz']])
    v_b = np.array([state_b['vx'], state_b['vy'], state_b['vz']])

    r_rel = r_a - r_b
    v_rel = v_a - v_b
    v_rel_mag = np.linalg.norm(v_rel)

    null_result = {"pc_nominal": 0.0, "pc_lower_1sigma": 0.0, "pc_upper_1sigma": 0.0, "sigma_r_km": 0.1, "covariance_source": "conservative_default"}
    if v_rel_mag < 1e-6:
        return null_result

    # 2. Define encounter plane
    z_hat = v_rel / v_rel_mag
    x_vec = r_rel - np.dot(r_rel, z_hat) * z_hat
    x_dist = np.linalg.norm(x_vec)
    if x_dist < 1e-8:
        x_hat = np.array([1, 0, 0])
    else:
        x_hat = x_vec / x_dist
    y_hat = np.cross(z_hat, x_hat)

    # 3. Construct Proxy Covariance with LSTM-aware sigma_r
    sigma_r = max(0.1, lstm_uncertainty_a + lstm_uncertainty_b) if (lstm_uncertainty_a + lstm_uncertainty_b) > 0 else 0.1
    sigma_it, sigma_ct = 0.5, 0.1
    covariance_source = "lstm_augmented" if (lstm_uncertainty_a + lstm_uncertainty_b) > 0 else "conservative_default"

    def get_proxy_cov(v, r, sr):
        u_r = r / np.linalg.norm(r)
        cross = np.cross(r, v)
        cross_norm = np.linalg.norm(cross)
        if cross_norm < 1e-10:
            return np.eye(3) * sr**2
        u_c = cross / cross_norm
        u_t = np.cross(u_c, u_r)
        rot = np.column_stack((u_r, u_t, u_c))
        diag = np.diag([sr**2, sigma_it**2, sigma_ct**2])
        return rot @ diag @ rot.T

    def compute_pc_for_sigma(sr: float) -> float:
        cov_total = get_proxy_cov(v_a, r_a, sr) + get_proxy_cov(v_b, r_b, sr)
        proj_matrix = np.column_stack((x_hat, y_hat))
        cov_2d = proj_matrix.T @ cov_total @ proj_matrix
        det_cov = np.linalg.det(cov_2d)
        if det_cov <= 0:
            return 0.0
        inv_cov = np.linalg.inv(cov_2d)

        def integrand(y, x):
            dx = np.array([x - x_dist, y])
            exponent = -0.5 * (dx.T @ inv_cov @ dx)
            return (1.0 / (2.0 * np.pi * np.sqrt(det_cov))) * np.exp(exponent)

        prob, _ = dblquad(
            integrand,
            -combined_radius_km, combined_radius_km,
            lambda x: -np.sqrt(max(0, combined_radius_km**2 - x**2)),
            lambda x: np.sqrt(max(0, combined_radius_km**2 - x**2))
        )
        return float(np.clip(prob, 0.0, 1.0))

    pc_nominal = compute_pc_for_sigma(sigma_r)
    pc_lower = compute_pc_for_sigma(sigma_r * 0.5)   # optimistic covariance
    pc_upper = compute_pc_for_sigma(sigma_r * 2.0)   # pessimistic covariance

    return {
        "pc_nominal": pc_nominal,
        "pc_lower_1sigma": pc_lower,
        "pc_upper_1sigma": pc_upper,
        "sigma_r_km": sigma_r,
        "covariance_source": covariance_source,
    }

async def detect_conjunctions(
    propagated_states: dict, 
    satellites_catalogue: dict, 
    timestamps: List[datetime], 
    threshold_km: float = 5.0
) -> List[ConjunctionEvent]:
    """
    Orchestrates the detection sweep using optimized TCA and 2D Pc logic.
    Risk scoring is deliberately excluded here to allow the central Risk Scorer
    to handle the final computation using its standard formula.
    """
    logger.info("Initializing high-fidelity conjunction sweep...")
    detected_events = []
    
    if not propagated_states or not timestamps:
        return []

    # Broad-phase KDTree scan
    candidate_pairs = set()
    step_frames = range(0, len(timestamps), 5)
    for t_idx in step_frames:
        snapshot = get_positions_snapshot(propagated_states, t_idx)
        if not snapshot: continue
        kdtree, ordered_ids = build_spatial_index(snapshot)
        close_pairs = find_close_pairs(kdtree, ordered_ids, threshold_km)
        filtered_pairs = filter_same_constellation(close_pairs, satellites_catalogue)
        for nid_a, nid_b, _ in filtered_pairs:
            candidate_pairs.add(tuple(sorted((nid_a, nid_b))))
            
    # Narrow-phase Refinement
    for nid_a, nid_b in candidate_pairs:
        try:
            pos_a_series = propagated_states.get(nid_a)
            pos_b_series = propagated_states.get(nid_b)
            if not pos_a_series or not pos_b_series: continue
                
            tca_utc, miss_km, state_a, state_b = find_tca_between_pair(
                pos_a_series, pos_b_series, timestamps
            )
            
            if miss_km < threshold_km:
                sat_a = satellites_catalogue.get(nid_a, {})
                sat_b = satellites_catalogue.get(nid_b, {})
                
                # Relative stats
                vel_a = (state_a["vx"], state_a["vy"], state_a["vz"])
                vel_b = (state_b["vx"], state_b["vy"], state_b["vz"])
                rel_v = compute_relative_velocity(vel_a, vel_b)

                # LSTM uncertainty estimation: predicted position deviation inflates covariance
                unc_a = estimate_lstm_uncertainty(nid_a, pos_a_series)
                unc_b = estimate_lstm_uncertainty(nid_b, pos_b_series)
                
                # The Golden Formula: 2D Chan Integration with LSTM-aware covariance + confidence intervals
                pc_result = compute_collision_probability_chan(
                    state_a, state_b, miss_km,
                    lstm_uncertainty_a=unc_a,
                    lstm_uncertainty_b=unc_b,
                )
                p_collision = pc_result["pc_nominal"]

                # Collect criticality metadata for the Risk Scorer to use later
                crit_a = sat_a.get("criticality_score", 1.0)
                crit_b = sat_b.get("criticality_score", 1.0)
                combined_crit = crit_a + crit_b

                # risk_score and risk_level are left at defaults (0.0 and LOW)
                # They will be overwritten by the scheduler calling risk_scorer.py
                detected_events.append(ConjunctionEvent(
                    detected_at=utc_now(),
                    norad_id_a=nid_a, norad_id_b=nid_b,
                    name_a=sat_a.get("name", nid_a), name_b=sat_b.get("name", nid_b),
                    tca_utc=tca_utc,
                    miss_distance_km=miss_km,
                    relative_velocity_kmps=rel_v,
                    collision_probability_chan=p_collision,
                    pc_lower_1sigma=pc_result["pc_lower_1sigma"],
                    pc_upper_1sigma=pc_result["pc_upper_1sigma"],
                    covariance_source=pc_result["covariance_source"],
                    object_type_a=sat_a.get("object_type", "UNKNOWN"),
                    object_type_b=sat_b.get("object_type", "UNKNOWN"),
                    criticality_a=crit_a,
                    criticality_b=crit_b,
                    combined_criticality=combined_crit,
                    altitude_km=float(compute_altitude(state_a['x'], state_a['y'], state_a['z'])),
                    state_vector_at_tca_a=state_a,
                    state_vector_at_tca_b=state_b,
                    lstm_uncertainty_a=unc_a,
                    lstm_uncertainty_b=unc_b,
                ))
        except Exception as e:
            logger.error(f"Refinement failed for {nid_a}/{nid_b}: {e}")

    detected_events.sort(key=lambda x: x.tca_utc)
    return detected_events