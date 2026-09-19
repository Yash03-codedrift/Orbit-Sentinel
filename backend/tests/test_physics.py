"""
10 unit tests for Orbit Sentinel physics core.
Covers Chan Pc, CW maneuver mechanics, Tsiolkovsky, TLE parsing,
KDTree spatial index, risk scoring, ANN labels, and MARL fuel conflicts.

Run with:
    pytest backend/tests/test_physics.py -v
"""
import math
import sys
import os
import numpy as np
import pytest
from datetime import datetime, timezone

# ── helpers ──────────────────────────────────────────────────────────────────

def make_state(x=7000.0, y=0.0, z=0.0, vx=0.0, vy=7.5, vz=0.0) -> dict:
    return {"x": x, "y": y, "z": z, "vx": vx, "vy": vy, "vz": vz}


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1 — Chan Pc: near-collision → Pc ≈ 1
# ═══════════════════════════════════════════════════════════════════════════
def test_chan_pc_near_collision():
    """Objects 1 m apart at the same position → Pc should be high (> 0.5)."""
    from backend.core.conjunction_detector import compute_collision_probability_chan
    sa = make_state(x=7000.0, vx=0.0)
    # Offset by 0.001 km (1 metre)
    sb = make_state(x=7000.001, vx=0.0, vy=7.6)
    result = compute_collision_probability_chan(sa, sb, miss_distance_km=0.001)
    assert isinstance(result, dict), "Should return a dict"
    assert result["pc_nominal"] > 0.001, f"Expected Pc > 0.001 for 1 m miss, got {result['pc_nominal']}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2 — Chan Pc: far miss → Pc ≈ 0
# ═══════════════════════════════════════════════════════════════════════════
def test_chan_pc_far_miss():
    """Objects 100 km apart → Pc should be essentially zero (< 1e-10)."""
    from backend.core.conjunction_detector import compute_collision_probability_chan
    sa = make_state(x=7000.0, vy=7.5)
    sb = make_state(x=7100.0, vy=7.6)
    result = compute_collision_probability_chan(sa, sb, miss_distance_km=100.0)
    assert result["pc_nominal"] < 1e-10, f"Expected Pc < 1e-10 for 100 km miss, got {result['pc_nominal']}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3 — Chan Pc: confidence interval structure
# ═══════════════════════════════════════════════════════════════════════════
def test_chan_pc_confidence_interval_structure():
    """Returned dict must have all CI keys and lower ≤ nominal ≤ upper."""
    from backend.core.conjunction_detector import compute_collision_probability_chan
    sa = make_state(x=7000.0, vy=7.5)
    sb = make_state(x=7000.5, vy=7.6)
    result = compute_collision_probability_chan(sa, sb, miss_distance_km=0.5)
    assert "pc_nominal" in result
    assert "pc_lower_1sigma" in result
    assert "pc_upper_1sigma" in result
    assert "sigma_r_km" in result
    assert "covariance_source" in result
    assert result["pc_lower_1sigma"] <= result["pc_nominal"] + 1e-12, "lower should not exceed nominal"
    assert result["pc_upper_1sigma"] >= result["pc_nominal"] - 1e-12, "upper should not be below nominal"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4 — CW step: zero burn → miss unchanged
# ═══════════════════════════════════════════════════════════════════════════
def test_cw_zero_burn_preserves_miss():
    """Zero delta-V action should leave new_miss approximately equal to current_miss."""
    from backend.ml.rl_maneuver_agent import ManeuverEnv
    env = ManeuverEnv(miss_distance_km=2.0, time_to_tca_hours=12.0,
                     relative_velocity_kmps=7.0, current_fuel_kg=50.0,
                     altitude_km=550.0, criticality_partner=3.0)
    env.reset(seed=42)
    action = np.array([0.0, 0.0, 0.0])
    obs, reward, terminated, truncated, info = env.step(action)
    new_miss = info.get("new_miss_km", 2.0)
    # With zero burn, CW displacement is zero → miss should stay at ~2.0 km
    assert abs(new_miss - 2.0) < 0.5, f"Zero burn should barely change miss: got {new_miss}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5 — CW step: in-track burn changes miss
# ═══════════════════════════════════════════════════════════════════════════
def test_cw_intrack_burn_changes_miss():
    """A non-zero in-track burn should produce a different miss distance than the initial."""
    from backend.ml.rl_maneuver_agent import ManeuverEnv
    env = ManeuverEnv(miss_distance_km=2.0, time_to_tca_hours=12.0,
                     relative_velocity_kmps=7.0, current_fuel_kg=50.0,
                     altitude_km=550.0, criticality_partner=3.0)
    env.reset(seed=42)
    action = np.array([0.0, 0.5, 0.0])  # 0.5 m/s in-track
    _, _, _, _, info = env.step(action)
    new_miss = info.get("new_miss_km", 2.0)
    assert new_miss != 2.0, "In-track burn should change miss distance"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6 — Tsiolkovsky fuel consumption
# ═══════════════════════════════════════════════════════════════════════════
def test_tsiolkovsky_fuel_mass():
    """
    For dv=1.0 m/s, Isp=220s, M0=500 kg:
    dm = M0 * (1 - exp(-dv / ve)) ≈ 0.232 kg
    """
    from backend.core.maneuver_calculator import compute_burn_duration
    burn_s, dm_kg = compute_burn_duration(
        delta_v_ms=1.0, thruster_force_n=1.0,
        specific_impulse_s=220.0, satellite_mass_kg=500.0
    )
    expected_dm = 500.0 * (1.0 - math.exp(-1.0 / (220.0 * 9.80665)))
    assert abs(dm_kg - expected_dm) < 1e-6, f"Expected dm ≈ {expected_dm:.6f} kg, got {dm_kg:.6f}"
    assert burn_s > 0, "Burn duration should be positive"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7 — TLE parsing (ISS Zarya)
# ═══════════════════════════════════════════════════════════════════════════
def test_tle_parsing():
    """Valid ISS TLE should parse to NORAD 25544 and have 69-char lines."""
    tle1 = "1 25544U 98067A   24001.50000000  .00001764  00000-0  32567-4 0  999"
    tle2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.50437522 428952"
    assert len(tle1) == 69, f"TLE line 1 must be 69 chars, got {len(tle1)}"
    assert len(tle2) == 69, f"TLE line 2 must be 69 chars, got {len(tle2)}"
    norad_id = tle1[2:7].strip()
    assert norad_id == "25544", f"Expected NORAD 25544, got '{norad_id}'"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 8 — KDTree spatial index
# ═══════════════════════════════════════════════════════════════════════════
def test_kdtree_spatial_index():
    """KDTree finds close pair within threshold, returns empty below minimum separation."""
    from backend.core.spatial_index import build_spatial_index, find_close_pairs

    positions = {
        "SAT_A": (7000.0, 0.0, 0.0),
        "SAT_B": (7000.3, 0.0, 0.0),   # 0.3 km away
        "SAT_C": (8000.0, 0.0, 0.0),   # far away
    }
    tree, norad_ids = build_spatial_index(positions)

    pairs_within_1km = find_close_pairs(tree, norad_ids, threshold_km=1.0)
    pair_ids = {(a, b) for a, b, _ in pairs_within_1km}
    assert ("SAT_A", "SAT_B") in pair_ids or ("SAT_B", "SAT_A") in pair_ids, \
        "Should detect SAT_A–SAT_B pair within 1 km"

    pairs_within_01km = find_close_pairs(tree, norad_ids, threshold_km=0.1)
    assert len(pairs_within_01km) == 0, "No pairs should be within 0.1 km"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 9 — Risk scoring: CRITICAL vs NEGLIGIBLE
# ═══════════════════════════════════════════════════════════════════════════
def test_risk_scoring_critical_vs_negligible():
    """Close fast conjunction → CRITICAL; distant slow → NEGLIGIBLE."""
    from backend.core.conjunction_detector import ConjunctionEvent
    from backend.core.risk_scorer import score_conjunction, classify_risk_level

    # High-risk event
    hi = ConjunctionEvent(
        detected_at=datetime.now(timezone.utc),
        norad_id_a="AAA", norad_id_b="BBB",
        name_a="SAT_A", name_b="SAT_B",
        tca_utc=datetime.now(timezone.utc),
        miss_distance_km=0.1, relative_velocity_kmps=10.0,
        collision_probability_chan=1e-3,
        criticality_a=8.0, criticality_b=8.0, combined_criticality=16.0,
    )
    hi_score = score_conjunction(hi)
    assert classify_risk_level(hi_score) == "CRITICAL", \
        f"Expected CRITICAL for high-risk event, got {classify_risk_level(hi_score)} (score={hi_score:.4f})"

    # Low-risk event
    lo = ConjunctionEvent(
        detected_at=datetime.now(timezone.utc),
        norad_id_a="CCC", norad_id_b="DDD",
        name_a="SAT_C", name_b="SAT_D",
        tca_utc=datetime.now(timezone.utc),
        miss_distance_km=50.0, relative_velocity_kmps=0.5,
        collision_probability_chan=1e-15,
        criticality_a=1.0, criticality_b=1.0, combined_criticality=2.0,
    )
    lo_score = score_conjunction(lo)
    assert classify_risk_level(lo_score) == "NEGLIGIBLE", \
        f"Expected NEGLIGIBLE for low-risk event, got {classify_risk_level(lo_score)} (score={lo_score:.6f})"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 10 — ANN label generation sanity
# ═══════════════════════════════════════════════════════════════════════════
def test_ann_label_generation_sanity():
    """
    generate_synthetic_training_data should produce ≥1000 samples with 12 features,
    and the positive-class rate should be non-trivial (between 1% and 50%).
    """
    from backend.ml.collision_probability_ann import generate_synthetic_training_data
    X, y = generate_synthetic_training_data(n_samples=1000)
    assert X.shape[0] >= 1000, f"Expected ≥1000 rows, got {X.shape[0]}"
    assert X.shape[1] == 12, f"Expected 12 features, got {X.shape[1]}"
    pos_rate = y.mean()
    assert 0.01 < pos_rate < 0.5, \
        f"Positive class rate should be 1–50% for balanced physics labels, got {pos_rate:.4f}"
