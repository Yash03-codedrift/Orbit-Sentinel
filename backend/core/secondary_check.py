import logging
import asyncio
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from backend.config import settings
from backend.utils.time_utils import utc_now, datetime_to_iso
from backend.core.sgp4_propagator import propagate_single, get_propagation_timestamps, propagate_batch_python
from backend.core.conjunction_detector import detect_conjunctions, ConjunctionEvent
from backend.core.risk_scorer import score_conjunction, classify_risk_level
from backend.db.conjunction_repo import get_conjunction
from backend.db.audit_repo import append_audit_entry

logger = logging.getLogger("orbit_sentinel.secondary_check")

# --- Propagation Cache Mechanism ---
# TTL set to 15 minutes by default (aligns with standard TLE refresh cycles)
_PROPAGATION_CACHE: Dict[str, Any] = {
    "timestamp": None,
    "states": None
}
CACHE_TTL_MINUTES = 15

def update_propagation_cache(states: Dict[str, List[Dict[str, Any]]]):
    """Updates the global cache with fresh batch propagation results."""
    _PROPAGATION_CACHE["timestamp"] = utc_now()
    _PROPAGATION_CACHE["states"] = states
    logger.debug("Global propagation state cache updated.")

def get_cached_states() -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """Retrieves cached states if they are within the TTL window."""
    ts = _PROPAGATION_CACHE.get("timestamp")
    if ts and (utc_now() - ts) < timedelta(minutes=CACHE_TTL_MINUTES):
        return _PROPAGATION_CACHE.get("states")
    return None
# -----------------------------------

@dataclass
class VerificationResult:
    maneuver_id: str
    verified_at: datetime
    original_event_id: str
    risk_resolved: bool
    post_maneuver_miss_km: float
    secondary_conjunctions: List[dict]
    escalation_required: bool = False

    def to_dict(self) -> dict:
        res = asdict(self)
        res["verified_at"] = datetime_to_iso(res["verified_at"])
        return res

def get_val(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

async def verify_maneuver_resolution(
    maneuver_plan: Any, 
    all_satellites: List[dict], 
    db: Any
) -> VerificationResult:
    maneuver_id = get_val(maneuver_plan, "maneuver_id")
    original_event_id = get_val(maneuver_plan, "conjunction_event_id")
    norad_id = get_val(maneuver_plan, "norad_id")
    
    logger.info(f"Verifying maneuver {maneuver_id} for NORAD {norad_id}...")
    
    new_tle1 = get_val(maneuver_plan, "new_tle1_estimate")
    new_tle2 = get_val(maneuver_plan, "new_tle2_estimate")
    original_sat = next((s for s in all_satellites if s.get("norad_id") == norad_id), None)
    
    tle1 = new_tle1 or (original_sat.get("tle1") if original_sat else "")
    tle2 = new_tle2 or (original_sat.get("tle2") if original_sat else "")
    
    if not tle1 or not tle2:
        logger.error(f"Incomplete TLE for verification: {norad_id}")
        return VerificationResult(maneuver_id=maneuver_id, verified_at=utc_now(), 
                                  original_event_id=original_event_id, risk_resolved=False, 
                                  post_maneuver_miss_km=0.0, secondary_conjunctions=[], 
                                  escalation_required=True)
        
    timestamps = get_propagation_timestamps(
        hours_forward=getattr(settings, "PROPAGATION_HOURS", 72),
        interval_minutes=5
    )
    
    # 1. Propagate only the maneuvered target (Cheap)
    target_trajectory = [p for ts in timestamps if (p := propagate_single(tle1, tle2, ts))]
    if not target_trajectory:
        return VerificationResult(maneuver_id=maneuver_id, verified_at=utc_now(), 
                                  original_event_id=original_event_id, risk_resolved=False, 
                                  post_maneuver_miss_km=0.0, secondary_conjunctions=[], 
                                  escalation_required=True)
        
    # 2. Retrieve background states (Cached or Batch)
    cached_batch = get_cached_states()
    
    if cached_batch:
        logger.info("Using cached propagation states for secondary verification sweep.")
        # Create a working copy without the maneuvered satellite
        propagated_states = {nid: states for nid, states in cached_batch.items() if nid != norad_id}
    else:
        logger.warning("Cache expired or empty. Re-propagating all objects (expensive operation).")
        other_sats = [s for s in all_satellites if s.get("norad_id") != norad_id]
        propagated_states = await propagate_batch_python(other_sats, timestamps)
        # Populate cache for subsequent parallel verifications
        update_propagation_cache(propagated_states)

    # Inject maneuvered trajectory
    propagated_states[norad_id] = target_trajectory

    # 3. Detection Sweep (Threshold 1.0km)
    satellites_catalogue = {s["norad_id"]: s for s in all_satellites}
    detected_new = await detect_conjunctions(
        propagated_states=propagated_states,
        satellites_catalogue=satellites_catalogue,
        timestamps=timestamps,
        threshold_km=1.0
    )
    
    # 4. Analyze Resolution
    original_conjunction = await get_conjunction(db, original_event_id)
    partner_id = None
    if original_conjunction:
        nid_a, nid_b = original_conjunction.get("norad_id_a"), original_conjunction.get("norad_id_b")
        partner_id = nid_b if nid_a == norad_id else nid_a
        
    risk_resolved, post_maneuver_miss_km, secondary_conjunctions = True, 999.0, []
    
    for evt in detected_new:
        if (evt.norad_id_a == norad_id and evt.norad_id_b == partner_id) or \
           (evt.norad_id_a == partner_id and evt.norad_id_b == norad_id):
            post_maneuver_miss_km = evt.miss_distance_km
            if evt.miss_distance_km < 1.0: risk_resolved = False
        elif evt.norad_id_a == norad_id or evt.norad_id_b == norad_id:
            secondary_conjunctions.append(evt.to_dict())
                
    # Precise math for out-of-bounds miss
    if partner_id and post_maneuver_miss_km == 999.0:
        partner_trajectory = propagated_states.get(partner_id)
        if partner_trajectory:
            try:
                from backend.core.conjunction_detector import find_tca_between_pair
                _, actual_min_dist, _, _ = find_tca_between_pair(target_trajectory, partner_trajectory, timestamps)
                post_maneuver_miss_km = actual_min_dist
            except: post_maneuver_miss_km = 1.0

    # 5. Final Evaluation & Audit
    risk_threshold = getattr(settings, "RISK_THRESHOLD", 0.0001)
    escalation_required = any(sec.get("risk_score", 0.0) > risk_threshold for sec in secondary_conjunctions)
            
    verified_result = VerificationResult(
        maneuver_id=maneuver_id, verified_at=utc_now(), original_event_id=original_event_id,
        risk_resolved=risk_resolved, post_maneuver_miss_km=float(post_maneuver_miss_km),
        secondary_conjunctions=secondary_conjunctions, escalation_required=escalation_required
    )
    
    await append_audit_entry(db, {
         "timestamp": utc_now(),
         "action_type": "MANEUVER_VERIFICATION",
         "severity": "CRITICAL" if escalation_required else ("WARNING" if not risk_resolved else "INFO"),
         "details": f"Burn verification for {maneuver_id}. Spacing: {post_maneuver_miss_km:.3f}km. Collateral: {len(secondary_conjunctions)}."
    })
    
    try:
        from backend.db.maneuver_repo import update_maneuver_verification
        await update_maneuver_verification(db, maneuver_id, verified_result.to_dict())
    except Exception as e: logger.error(f"Log update failed: {e}")

    if escalation_required:
        asyncio.create_task(emergency_escalation(secondary_conjunctions, db))
        
    return verified_result

async def emergency_escalation(secondary_conjunctions: List[dict], db: Any) -> None:
    for sec in secondary_conjunctions:
        logger.warning(f"ESCALATION: Collateral risk for NORAD {sec.get('norad_id_a')}/{sec.get('norad_id_b')}")
        await append_audit_entry(db, {"timestamp": utc_now(), "action_type": "ESCALATION", "severity": "CRITICAL", "details": str(sec)})
        try:
            from backend.routers.websocket_router import broadcast_message
            await broadcast_message({"type": "escalation_alert", "conjunction": sec, "timestamp_utc": datetime_to_iso(utc_now())})
        except: pass