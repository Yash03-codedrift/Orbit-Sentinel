from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from backend.db.mongo_client import get_db
from backend.db import conjunction_repo, satellite_repo, maneuver_repo, audit_repo
from backend.core.conjunction_detector import ConjunctionEvent
from backend.core.maneuver_calculator import compute_optimal_maneuver
from backend.core.webhook_dispatcher import build_webhook_payload, simulate_webhook_dispatch
from backend.core.sgp4_propagator import propagate_single
from backend.utils.auth import verify_api_key

router = APIRouter()

def serialize_mongo_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    res = {}
    for k, v in doc.items():
        if k == "_id":
            res["_id"] = str(v)
        elif isinstance(v, datetime):
            res[k] = v.isoformat()
        else:
            res[k] = v
    return res

def apply_conjunction_adjustments(c: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies the ISS priority override to a conjunction record.
    GPS tracking boosts are already applied during detection and stored in the DB.
    """
    res = dict(c)
    nid_a = res.get("norad_id_a", "")
    nid_b = res.get("norad_id_b", "")
    miss_km = float(res.get("miss_distance_km", 0.0))
    
    # ISS Override Protocol
    # If the ISS (NORAD 25544) is involved and the miss distance is tight,
    # force the risk level to CRITICAL.
    if "25544" in [nid_a, nid_b]:
        if miss_km < 2.0:
            res["risk_level"] = "CRITICAL"
            res["risk_score"] = float(max(res.get("risk_score", 0.0), 95.0))

    return res

def db_to_conjunction_event_obj(d: Dict[str, Any]) -> ConjunctionEvent:
    def parse_dt(val: Any) -> datetime:
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    return ConjunctionEvent(
        detected_at=parse_dt(d.get("detected_at")),
        norad_id_a=d.get("norad_id_a", ""),
        norad_id_b=d.get("norad_id_b", ""),
        name_a=d.get("name_a", "UNKNOWN"),
        name_b=d.get("name_b", "UNKNOWN"),
        tca_utc=parse_dt(d.get("tca_utc")),
        miss_distance_km=float(d.get("miss_distance_km", 0.0)),
        relative_velocity_kmps=float(d.get("relative_velocity_kmps", 0.0)),
        collision_probability_chan=float(d.get("collision_probability_chan", 0.0)),
        event_id=d.get("event_id", ""),
        risk_score=float(d.get("risk_score", 0.0)),
        risk_level=d.get("risk_level", "LOW"),
        object_type_a=d.get("object_type_a", "UNKNOWN"),
        object_type_b=d.get("object_type_b", "UNKNOWN"),
        criticality_a=float(d.get("criticality_a", 1.0)),
        criticality_b=float(d.get("criticality_b", 1.0)),
        combined_criticality=float(d.get("combined_criticality", 0.0)),
        altitude_km=float(d.get("altitude_km", 0.0)),
        state_vector_at_tca_a=d.get("state_vector_at_tca_a", {}),
        state_vector_at_tca_b=d.get("state_vector_at_tca_b", {}),
        already_maneuvered=bool(d.get("already_maneuvered", False)),
        resolved=bool(d.get("resolved", False))
    )

@router.get("/active")
async def get_active_conjunctions(db = Depends(get_db)):
    """
    Retrieve active (unresolved) close approach events.
    Applies real-time ISS collision overrides.
    """
    try:
        active_list = await conjunction_repo.get_active_conjunctions(db)
        adjusted = [apply_conjunction_adjustments(serialize_mongo_doc(c)) for c in active_list]
        return adjusted
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load active threats: {e}")

@router.get("/stats")
async def get_stats(db = Depends(get_db)):
    """
    Fetch global daily tallies and active warning severity counts.
    """
    try:
        stats = await conjunction_repo.get_conjunction_stats(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch conjunction stats: {e}")

@router.get("/search")
async def search(
    q: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db = Depends(get_db)
):
    """
    Search system alerts with text filters and target TCA range checks.
    """
    parsed_from = None
    parsed_to = None
    if date_from:
        try:
            parsed_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use ISO format.")
    if date_to:
        try:
            parsed_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use ISO format.")

    try:
        results = await conjunction_repo.search_conjunctions(db, q=q, date_from=parsed_from, date_to=parsed_to)
        return [serialize_mongo_doc(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

@router.get("/history")
async def get_history(
    days: int = Query(default=7, ge=1, le=90),
    db = Depends(get_db)
):
    """
    Retrieve historical conjunction alerts within the last N days.
    """
    try:
        conjs = await conjunction_repo.get_conjunction_history(db, days=days)
        return [serialize_mongo_doc(c) for c in conjs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load history: {e}")

@router.get("/{event_id}")
async def get_by_id(
    event_id: str,
    db = Depends(get_db)
):
    """
    Get detailed analysis attributes for a specific collision warning item.
    """
    conj = await conjunction_repo.get_conjunction(db, event_id)
    if not conj:
        raise HTTPException(status_code=404, detail=f"Conjunction event {event_id} not found.")
    return apply_conjunction_adjustments(serialize_mongo_doc(conj))


@router.post("/{event_id}/trigger_response", dependencies=[Depends(verify_api_key)])
async def trigger_response(event_id: str, db = Depends(get_db)):
    """
    Manually deploy reinforcement learning mitigation actions regarding a critical warning threat.
    """
    # 1. Get conjunction from DB
    conj_doc = await conjunction_repo.get_conjunction(db, event_id)
    if not conj_doc:
        raise HTTPException(status_code=404, detail=f"Conjunction event with ID {event_id} not found.")

    # Apply standard adjustments first to make sure risk data aligns
    adjusted_conj_doc = apply_conjunction_adjustments(conj_doc)
    
    # 2. Get satellite A state from propagated positions
    nid_a = adjusted_conj_doc.get("norad_id_a")
    tca_utc_raw = adjusted_conj_doc.get("tca_utc")
    
    # Parse TCA date safely
    tca_dt = None
    if isinstance(tca_utc_raw, datetime):
        tca_dt = tca_utc_raw
    elif isinstance(tca_utc_raw, str):
        try:
            tca_dt = datetime.fromisoformat(tca_utc_raw.replace("Z", "+00:00"))
        except ValueError:
            pass
            
    if not tca_dt:
        tca_dt = datetime.now(timezone.utc) + timedelta(hours=12)

    state_vector_a = adjusted_conj_doc.get("state_vector_at_tca_a", {})
    
    sat_a = await satellite_repo.get_satellite(db, nid_a)
    if sat_a:
        tle1 = sat_a.get("tle1")
        tle2 = sat_a.get("tle2")
        if tle1 and tle2:
            try:
                propagated = propagate_single(tle1, tle2, tca_dt)
                if propagated:
                    state_vector_a = propagated
                    state_vector_a["norad_id"] = nid_a
                    state_vector_a["name"] = sat_a.get("name", "SAT")
                    state_vector_a["criticality_score"] = adjusted_conj_doc.get("criticality_a", 5.0)
            except Exception:
                pass

    if not state_vector_a:
        raise HTTPException(
            status_code=400,
            detail="Could not retrieve or propagate state vector parameters for the target satellite A."
        )

    # 3. Call compute_optimal_maneuver with use_rl=True
    conjunction_event_obj = db_to_conjunction_event_obj(adjusted_conj_doc)
    try:
        maneuver_plan = await compute_optimal_maneuver(
            state_vector_a=state_vector_a,
            conjunction_event=conjunction_event_obj,
            use_rl=True
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Reinforcement learning solver failed to optimize evasive actions: {exc}"
        )

    # 4. Call build_webhook_payload
    webhook_payload = build_webhook_payload(maneuver_plan, conjunction_event_obj)

    # 5. Insert maneuver to DB
    await maneuver_repo.insert_maneuver(db, maneuver_plan.to_dict())

    # 6. Simulate webhook dispatch (store in DB)
    await simulate_webhook_dispatch(webhook_payload, db)

    # 7. Mark conjunction as maneuvered
    await db["conjunctions"].update_one(
        {"event_id": event_id},
        {"$set": {
            "maneuvered": True,
            "maneuver_id": maneuver_plan.maneuver_id,
            "resolved": True,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # 8. Append audit entry
    audit_entry = {
         "timestamp": datetime.now(timezone.utc),
         "action_type": "MANEUVER_TRIGGERED",
         "severity": "WARNING",
         "details": (
              f"Operator triggered maneuver plan {maneuver_plan.maneuver_id} regarding conjunction {event_id}. "
              f"Prescribed Burn Vector Magnitude: {maneuver_plan.delta_v_magnitude_ms:.3f} m/s. "
              f"Estimated post miss spacing layout: {maneuver_plan.post_maneuver_miss_km:.3f} km."
         )
    }
    await audit_repo.append_audit_entry(db, audit_entry)

    # 9. Broadcast via WebSocket
    try:
        from backend.routers.websocket_router import broadcast
        serialized_plan = maneuver_plan.to_dict()
        await broadcast({
            "type": "maneuver_computed",
            "maneuver": serialized_plan,
            "conjunction_event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception:
        pass

    # 10. Return payload
    return {
        "maneuver_id": maneuver_plan.maneuver_id,
        "maneuver": maneuver_plan.to_dict(),
        "webhook_payload": webhook_payload,
        "status": "RESPONSE_TRIGGERED"
    }

@router.post("/{event_id}/resolve", dependencies=[Depends(verify_api_key)])
async def resolve_conjunction(
    event_id: str,
    maneuver_id: Optional[str] = None,
    db = Depends(get_db)
):
    """
    Manually mark a conjunction resolved, optionally tagging a corresponding maneuver.
    """
    result = await conjunction_repo.mark_conjunction_resolved(db, event_id, maneuver_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Collision warning item {event_id} not found to resolve.")
    
    # Broadcast state change
    try:
        from backend.routers.websocket_router import broadcast
        await broadcast({
            "type": "conjunction_resolved",
            "event_id": event_id,
            "maneuver_id": maneuver_id,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception:
        pass
        
    return serialize_mongo_doc(result)

@router.get("/{event_id}/cdm")
async def export_cdm(event_id: str, db = Depends(get_db)):
    """
    Exports a conjunction event as a CCSDS 508.0-B-1 Conjunction Data Message (CDM).
    This format is the operational standard used by SpaceTrack, CARA, and LeoLabs.
    Returns a plain-text CDM file as a downloadable attachment.
    """
    from fastapi.responses import PlainTextResponse

    doc = await db["conjunctions"].find_one({"event_id": event_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Conjunction event {event_id} not found.")

    created = datetime.now(timezone.utc).strftime("%Y-%jT%H:%M:%S.000")
    tca = doc.get("tca_utc", "")
    if hasattr(tca, "isoformat"):
        tca = tca.isoformat().replace("+00:00", "Z")

    sv_a = doc.get("state_vector_at_tca_a") or {}
    sv_b = doc.get("state_vector_at_tca_b") or {}

    # --- True RTN decomposition (CCSDS 508.0-B-1 §4.3) ---
    # RTN frame is defined relative to object A's orbit at TCA:
    #   R_hat = pos_a / |pos_a|           (radial outward)
    #   N_hat = (pos_a × vel_a) / |...|  (orbit-normal, out of plane)
    #   T_hat = N_hat × R_hat             (in-track, ~velocity direction)
    # Relative position ΔP = pos_a - pos_b is then projected onto each axis.
    import numpy as np
    pos_a = np.array([float(sv_a.get("x", 0)), float(sv_a.get("y", 0)), float(sv_a.get("z", 0))])
    vel_a = np.array([float(sv_a.get("vx", 0)), float(sv_a.get("vy", 0)), float(sv_a.get("vz", 0))])
    pos_b = np.array([float(sv_b.get("x", 0)), float(sv_b.get("y", 0)), float(sv_b.get("z", 0))])

    delta_pos = pos_a - pos_b  # ECI relative position vector [km]

    r_mag = np.linalg.norm(pos_a)
    h_vec = np.cross(pos_a, vel_a)
    h_mag = np.linalg.norm(h_vec)

    if r_mag > 1e-9 and h_mag > 1e-9:
        R_hat = pos_a / r_mag
        N_hat = h_vec / h_mag
        T_hat = np.cross(N_hat, R_hat)
        dr  = round(float(np.dot(delta_pos, R_hat)), 6)
        dt_ = round(float(np.dot(delta_pos, T_hat)), 6)
        dn  = round(float(np.dot(delta_pos, N_hat)), 6)
    else:
        # Fallback: state vectors missing — report raw ECI diff with warning
        dr  = round(float(delta_pos[0]), 6)
        dt_ = round(float(delta_pos[1]), 6)
        dn  = round(float(delta_pos[2]), 6)

    pc = doc.get("collision_probability_chan", 0.0)
    pc_str = f"{float(pc):.4e}" if pc else "0.0000e+00"

    cdm = f"""CCSDS_CDM_VERS = 1.0
CREATION_DATE = {created}
ORIGINATOR = ORBIT-SENTINEL
MESSAGE_FOR = {doc.get("name_a", doc.get("norad_id_a", "UNKNOWN"))}
MESSAGE_ID = CDM-{event_id}

COMMENT CREATED BY ORBIT SENTINEL AUTONOMOUS SSA SYSTEM
COMMENT DETECTION METHOD: KDTree broad-phase + parabolic TCA refinement + Chan/Foster 2D Pc
COMMENT COVARIANCE SOURCE: {doc.get("covariance_source", "conservative_default")}

TCA = {tca}
MISS_DISTANCE = {doc.get("miss_distance_km", 0.0)} [km]
RELATIVE_SPEED = {doc.get("relative_velocity_kmps", 0.0)} [km/s]
RELATIVE_POSITION_R = {dr} [km]
RELATIVE_POSITION_T = {dt_} [km]
RELATIVE_POSITION_N = {dn} [km]
PROBABILITY_OF_COLLISION = {pc_str}
PC_LOWER_1SIGMA = {doc.get("pc_lower_1sigma", 0.0):.4e}
PC_UPPER_1SIGMA = {doc.get("pc_upper_1sigma", 0.0):.4e}
RISK_LEVEL = {doc.get("risk_level", "UNKNOWN")}

OBJECT = OBJECT1
OBJECT_DESIGNATOR = {doc.get("norad_id_a", "UNKNOWN")}
CATALOG_NAME = {doc.get("name_a", "UNKNOWN")}
OBJECT_TYPE = {doc.get("object_type_a", "UNKNOWN")}
CRITICALITY = {doc.get("criticality_a", 0.0)}

OBJECT = OBJECT2
OBJECT_DESIGNATOR = {doc.get("norad_id_b", "UNKNOWN")}
CATALOG_NAME = {doc.get("name_b", "UNKNOWN")}
OBJECT_TYPE = {doc.get("object_type_b", "UNKNOWN")}
CRITICALITY = {doc.get("criticality_b", 0.0)}
"""

    return PlainTextResponse(
        content=cdm,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="CDM_{event_id}.txt"'}
    )
