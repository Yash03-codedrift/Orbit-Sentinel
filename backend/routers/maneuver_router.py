from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from backend.db.mongo_client import get_db
from backend.db import maneuver_repo
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

@router.get("/recent")
async def get_recent_maneuvers(
    limit: int = Query(default=20, ge=1, le=100),
    db = Depends(get_db)
):
    """
    Retrieve the most recently computed satellite burn/avoidance maneuvers.
    """
    try:
        maneuvers = await maneuver_repo.get_recent_maneuvers(db, limit=limit)
        return [serialize_mongo_doc(m) for m in maneuvers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database retrieval failed: {e}")

@router.get("")
async def get_recent_maneuvers_alias(
    limit: int = Query(default=20, ge=1, le=100),
    db = Depends(get_db)
):
    """
    Alias endpoint to retrieve recent maneuvers at /api/maneuvers.
    """
    return await get_recent_maneuvers(limit=limit, db=db)

@router.get("/{maneuver_id}")
async def get_by_id(
    maneuver_id: str,
    db = Depends(get_db)
):
    """
    Get detailed metrics of a specific recommended maneuver plan.
    """
    maneuver = await maneuver_repo.get_maneuver(db, maneuver_id)
    if not maneuver:
        raise HTTPException(status_code=404, detail=f"Maneuver proposal {maneuver_id} not found.")
    return serialize_mongo_doc(maneuver)

@router.get("/{maneuver_id}/webhook_payload")
async def get_webhook_payload(maneuver_id: str, db = Depends(get_db)):
    """
    Fetch dispatched webhook metadata matching a maneuver's target conjunction.
    """
    maneuver = await maneuver_repo.get_maneuver(db, maneuver_id)
    if not maneuver:
        raise HTTPException(status_code=404, detail=f"Maneuver proposal {maneuver_id} not found.")

    conj_id = maneuver.get("conjunction_event_id")
    if not conj_id:
        raise HTTPException(status_code=400, detail="Maneuver record is missing its target conjunction linkage.")

    try:
        # Search webhook documents which contain this conjunction ID in their payload
        webhook_doc = await db["webhooks"].find_one({
            "$or": [
                {"payload.conjunction.event_id": conj_id},
                {"payload.conjunction_event_id": conj_id}
            ]
        })
        if not webhook_doc:
            raise HTTPException(
                status_code=404, 
                detail="No dispatched webhook payload found in the active dispatch buffer."
            )
        return webhook_doc.get("payload")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")

@router.get("/{maneuver_id}/verification")
async def get_maneuver_verification(maneuver_id: str, db = Depends(get_db)):
    """
    Retrieve real time spatial post-burn trajectory confirmation logs for this maneuver.
    """
    maneuver = await maneuver_repo.get_maneuver(db, maneuver_id)
    if not maneuver:
        raise HTTPException(status_code=404, detail=f"Maneuver proposal {maneuver_id} not found.")

    verification_result = maneuver.get("verification_result")
    if not verification_result:
        return {}
    return verification_result

@router.post("/{maneuver_id}/verify", dependencies=[Depends(verify_api_key)])
async def verify_maneuver(
    maneuver_id: str,
    success: bool = True,
    telemetry_match: bool = True,
    post_miss_km: float = 2.5,
    db = Depends(get_db)
):
    """
    Record manual or automated simulation verification logs for a recommended maneuver.
    """
    verification_payload = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "telemetry_match": telemetry_match,
        "post_maneuver_miss_km": post_miss_km,
        "notes": "Triggered via operator API endpoint verification routine."
    }
    
    result = await maneuver_repo.update_maneuver_verification(db, maneuver_id, verification_payload)
    if not result:
        raise HTTPException(status_code=404, detail=f"Maneuver proposal {maneuver_id} not found to update.")
        
    # Broadcast through WebSockets
    try:
        from backend.routers.websocket_router import broadcast
        await broadcast({
            "type": "maneuver_verified",
            "maneuver_id": maneuver_id,
            "verification": verification_payload
        })
    except Exception:
        pass
        
    return serialize_mongo_doc(result)
