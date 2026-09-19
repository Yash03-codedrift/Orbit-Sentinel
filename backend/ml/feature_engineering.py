import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, Optional

def safe_float(val: Any, default: float) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def parse_datetime(dt_val: Any) -> datetime:
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        try:
            # Replace 'Z' with UTC timezone offset
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)

def get_val(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def encode_object_type(obj_type: str) -> int:
    """
    Encodes object types: PAYLOAD -> 0, ROCKET_BODY -> 1, DEBRIS -> 2, else -> 3.
    """
    if not obj_type:
        return 3
    obj_type_upper = str(obj_type).strip().upper()
    if obj_type_upper == "PAYLOAD":
        return 0
    elif obj_type_upper == "ROCKET_BODY":
        return 1
    elif obj_type_upper == "DEBRIS":
        return 2
    else:
        return 3

def build_ann_features(conjunction_event: Any, kp_index: float = 3.0, f107: float = 150.0, maneuver_history_count: int = 0) -> Dict[str, Any]:
    """
    Returns dict with exact 12 keys matching ANN input.
    """
    miss_distance_km = safe_float(get_val(conjunction_event, "miss_distance_km"), 5.0)
    relative_velocity_kmps = safe_float(get_val(conjunction_event, "relative_velocity_kmps"), 10.0)
    combined_cross_section_m2 = safe_float(get_val(conjunction_event, "combined_cross_section_m2"), 20.0)

    # Time to TCA in hours = from utcnow to tca_utc
    tca_val = get_val(conjunction_event, "tca_utc")
    if tca_val:
        tca_dt = parse_datetime(tca_val)
        now_dt = datetime.now(timezone.utc)
        time_to_tca_hours = (tca_dt - now_dt).total_seconds() / 3600.0
    else:
        time_to_tca_hours = safe_float(get_val(conjunction_event, "time_to_tca_hours"), 72.0)

    criticality_a = safe_float(get_val(conjunction_event, "criticality_a"), 1.0)
    criticality_b = safe_float(get_val(conjunction_event, "criticality_b"), 1.0)

    object_type_a_str = get_val(conjunction_event, "object_type_a", "UNKNOWN")
    object_type_b_str = get_val(conjunction_event, "object_type_b", "UNKNOWN")
    object_type_a_encoded = encode_object_type(object_type_a_str)
    object_type_b_encoded = encode_object_type(object_type_b_str)

    altitude_km = safe_float(get_val(conjunction_event, "altitude_km"), 1000.0)

    # Prioritize any event fields or fallback to parameters
    solar_flux_f10_7 = safe_float(get_val(conjunction_event, "solar_flux_f10_7") or get_val(conjunction_event, "f10_7"), f107)
    kp_index_val = safe_float(get_val(conjunction_event, "kp_index"), kp_index)
    maneuver_history_val = int(safe_float(get_val(conjunction_event, "maneuver_history_count"), maneuver_history_count))

    return {
        "miss_distance_km": miss_distance_km,
        "relative_velocity_kmps": relative_velocity_kmps,
        "combined_cross_section_m2": combined_cross_section_m2,
        "time_to_tca_hours": time_to_tca_hours,
        "criticality_a": criticality_a,
        "criticality_b": criticality_b,
        "object_type_a_encoded": object_type_a_encoded,
        "object_type_b_encoded": object_type_b_encoded,
        "altitude_km": altitude_km,
        "solar_flux_f10_7": solar_flux_f10_7,
        "kp_index": kp_index_val,
        "maneuver_history_count": maneuver_history_val
    }

def build_marl_observation(satellite_state: Dict[str, Any], conjunction: Dict[str, Any], allied_maneuvers: list[Dict[str, Any]]) -> np.ndarray:
    """
    6-element observation for RL agent:
    [miss_distance_km / 5.0, time_to_tca_hours / 72.0, relative_velocity_kmps / 15.0, current_fuel_kg / 50.0, altitude_km / 2000.0, criticality_partner / 10.0]
    All clamped to [0.0, 1.0]. Return np.float32 array.
    """
    miss_distance_km = safe_float(conjunction.get("miss_distance_km", conjunction.get("miss_distance")), 5.0)

    tca_val = conjunction.get("tca_utc", conjunction.get("tca"))
    if tca_val:
        tca_dt = parse_datetime(tca_val)
        now_dt = datetime.now(timezone.utc)
        time_to_tca_hours = (tca_dt - now_dt).total_seconds() / 3600.0
    else:
        time_to_tca_hours = safe_float(conjunction.get("time_to_tca_hours"), 72.0)

    relative_velocity_kmps = safe_float(conjunction.get("relative_velocity_kmps", conjunction.get("relative_velocity")), 10.0)
    current_fuel_kg = safe_float(satellite_state.get("current_fuel_kg", satellite_state.get("fuel_kg", satellite_state.get("fuel"))), 50.0)
    altitude_km = safe_float(satellite_state.get("altitude_km", satellite_state.get("altitude", conjunction.get("altitude_km", conjunction.get("altitude")))), 1000.0)

    # Calculate criticality of the partner object
    our_id = str(satellite_state.get("norad_id", satellite_state.get("id", satellite_state.get("satellite_id", ""))))
    id_a = str(conjunction.get("norad_id_a", ""))
    id_b = str(conjunction.get("norad_id_b", ""))

    if our_id == id_a:
        criticality_partner = safe_float(conjunction.get("criticality_b"), 1.0)
    elif our_id == id_b:
        criticality_partner = safe_float(conjunction.get("criticality_a"), 1.0)
    else:
        criticality_partner = safe_float(conjunction.get("criticality_b", conjunction.get("criticality_a")), 1.0)

    obs = [
        miss_distance_km / 5.0,
        time_to_tca_hours / 72.0,
        relative_velocity_kmps / 15.0,
        current_fuel_kg / 50.0,
        altitude_km / 2000.0,
        criticality_partner / 10.0
    ]

    # Clamp to [0.0, 1.0]
    clamped_obs = [max(0.0, min(1.0, float(x))) for x in obs]
    return np.array(clamped_obs, dtype=np.float32)

def normalize_conjunction_for_storage(conjunction_event: Any, maneuver_outcome: Optional[str] = None) -> Dict[str, Any]:
    """
    Builds training data record for ml_training_data collection.
    """
    features = build_ann_features(conjunction_event)
    event_id = get_val(conjunction_event, "event_id") or get_val(conjunction_event, "id")
    label = 1 if maneuver_outcome == "RESOLVED" else 0
    return {
        "timestamp": datetime.now(timezone.utc),
        "features": features,
        "label": label,
        "event_id": event_id
    }
