import httpx
import hashlib
import hmac
import json
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from backend.config import settings
from backend.utils.time_utils import utc_now, datetime_to_iso

logger = logging.getLogger("orbit_sentinel.webhook_dispatcher")

def get_val(obj: Any, key: str, default: Any = None) -> Any:
    """
    Helper to extract a field/attribute from either a dictionary or a dataclass/object safely.
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def build_webhook_payload(maneuver_plan: Any, conjunction_event: Any) -> dict:
    """
    Constructs a heavily structured JSON payload for external operator webhooks.
    Includes comprehensive metadata, orbital elements, relative parameters at TCA,
    and thruster fire recommendations.
    """
    plan_norad_id = get_val(maneuver_plan, "norad_id")
    plan_satellite_name = get_val(maneuver_plan, "satellite_name")
    
    evt_event_id = get_val(conjunction_event, "event_id")
    evt_norad_id_a = get_val(conjunction_event, "norad_id_a")
    evt_norad_id_b = get_val(conjunction_event, "norad_id_b")
    evt_name_a = get_val(conjunction_event, "name_a")
    evt_name_b = get_val(conjunction_event, "name_b")
    
    # Partner identification logic based on which item we calculated maneuver recommendations for
    if evt_norad_id_a == plan_norad_id:
        partner_norad_id = evt_norad_id_b
        partner_name = evt_name_b
    else:
        partner_norad_id = evt_norad_id_a
        partner_name = evt_name_a

    # Parse and convert TCA date safely
    tca_utc = get_val(conjunction_event, "tca_utc")
    if isinstance(tca_utc, str):
        try:
            tca_dt = datetime.fromisoformat(tca_utc.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Unable to parse TCA ISO string: {tca_utc}, defaulting expiration time calculation.")
            tca_dt = utc_now() + timedelta(hours=1)
    elif isinstance(tca_utc, datetime):
        tca_dt = tca_utc
    else:
        tca_dt = utc_now() + timedelta(hours=1)
        
    expires_at = tca_dt - timedelta(minutes=15)
    
    # Convert recommended burn epoch
    burn_epoch = get_val(maneuver_plan, "burn_epoch_utc")
    if isinstance(burn_epoch, datetime):
        burn_epoch_str = datetime_to_iso(burn_epoch)
    else:
        burn_epoch_str = str(burn_epoch)
        
    fuel_cost = float(get_val(maneuver_plan, "estimated_fuel_cost_kg", 0.0))
    percentage_fuel_used = round((fuel_cost / 50.0) * 100.0, 3)

    risk_level = get_val(conjunction_event, "risk_level")

    payload = {
        "event_id": str(uuid.uuid4()),
        "schema_version": "1.0",
        "timestamp_utc": datetime_to_iso(utc_now()),
        "issued_by": "ORBIT_SENTINEL_AUTONOMOUS",
        "satellite": {
            "norad_id": plan_norad_id,
            "name": plan_satellite_name,
            "operator_webhook_confirmed": False
        },
        "conjunction": {
            "event_id": evt_event_id,
            "partner_norad_id": partner_norad_id,
            "partner_name": partner_name,
            "time_of_closest_approach_utc": datetime_to_iso(tca_dt),
            "current_miss_distance_km": float(get_val(conjunction_event, "miss_distance_km", 0.0)),
            "relative_velocity_kmps": float(get_val(conjunction_event, "relative_velocity_kmps", 0.0)),
            "collision_probability_chan": float(get_val(conjunction_event, "collision_probability_chan", 0.0)),
            "risk_level": risk_level,
            "altitude_km": float(get_val(conjunction_event, "altitude_km", 0.0))
        },
        "recommended_maneuver": {
            "burn_epoch_utc": burn_epoch_str,
            "delta_v_magnitude_ms": float(get_val(maneuver_plan, "delta_v_magnitude_ms", 0.0)),
            "delta_v_vector_eci_ms": [float(x) for x in get_val(maneuver_plan, "delta_v_vector_ms", [0.0, 0.0, 0.0])],
            "burn_duration_seconds": float(get_val(maneuver_plan, "burn_duration_seconds", 0.0)),
            "estimated_fuel_cost_kg": fuel_cost,
            "predicted_post_maneuver_miss_km": float(get_val(maneuver_plan, "post_maneuver_miss_km", 0.0)),
            "algorithm": get_val(maneuver_plan, "algorithm", "UNKNOWN"),
            "rl_agent_used": bool(get_val(maneuver_plan, "rl_agent_used", False)),
            "confidence_score": float(get_val(maneuver_plan, "confidence_score", 0.0)),
            "auto_execute_recommended": risk_level in ["CRITICAL", "HIGH"]
        },
        "fuel_budget_impact": {
            "assumed_total_fuel_kg": 50.0,
            "this_maneuver_kg": fuel_cost,
            "percentage_used": percentage_fuel_used
        },
        "expires_at_utc": datetime_to_iso(expires_at)
    }
    
    return payload

def build_hmac_signature(payload_json: str, secret: str) -> str:
    """
    Computes a cryptographic HMAC-SHA256 signature to verify message origin authenticity.
    """
    h = hmac.new(secret.encode('utf-8'), payload_json.encode('utf-8'), hashlib.sha256)
    return h.hexdigest()

async def dispatch_webhook(payload: dict, webhook_url: str) -> bool:
    """
    Serializes payload to a JSON string, computes security signatures, and transmits to target.
    Retries up to three attempts utilizing exponential backoff triggers (1s, 2s, 4s).
    """
    payload_str = json.dumps(payload, sort_keys=True)
    secret = getattr(settings, "WEBHOOK_SECRET", "changeme")
    signature = build_hmac_signature(payload_str, secret)
    
    headers = {
        "Content-Type": "application/json",
        "X-Orbit-Sentinel-Signature": f"sha256={signature}",
        "X-Orbit-Sentinel-Timestamp": datetime_to_iso(utc_now())
    }
    
    logger.info(f"Starting webhook dispatch to url: {webhook_url}")
    
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload, headers=headers)
                if 200 <= response.status_code < 300:
                    logger.info(f"Successfully dispatched webhook on attempt {attempt}. Status: {response.status_code}")
                    return True
                else:
                    logger.warning(f"Webhook response returned invalid status code: {response.status_code} (Attempt {attempt}/3)")
        except Exception as exc:
            logger.error(f"Transport/networking error on webhook dispatch attempt {attempt}/3: {exc}")
            
        if attempt < 3:
            delay = 2 ** (attempt - 1)
            logger.info(f"Backing off for {delay} seconds before retry...")
            await asyncio.sleep(delay)
            
    logger.error(f"All 3 dispatch attempts to '{webhook_url}' failed.")
    return False

async def simulate_webhook_dispatch(payload: dict, db: Any) -> str:
    """
    Simulates sending webserv payloads by saving records straight inside the MongoDB audit log buffers.
    Does not require external HTTP routes.
    """
    document = {
        "stored_at": utc_now(),
        "payload": payload,
        "simulated": True
    }
    result = await db["webhooks"].insert_one(document)
    logger.info(f"Simulated webhook event written to database. Event target: {get_val(payload, 'event_id')}. Record ID: {result.inserted_id}")
    return str(result.inserted_id)
