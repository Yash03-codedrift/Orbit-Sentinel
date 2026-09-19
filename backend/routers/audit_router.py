from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from backend.db.mongo_client import get_db
from backend.db import audit_repo
from backend.utils.auth import verify_api_key

router = APIRouter()

class AuditEntry(BaseModel):
    action_type: str
    actor: str = "ORBIT_SENTINEL_AUTONOMOUS"
    satellite_norad_id: str = ""
    conjunction_event_id: str = ""
    input_data: dict = Field(default_factory=dict)
    output_data: dict = Field(default_factory=dict)
    ml_model_version: str = "ann_v1_lstm_v1"
    outcome: str = "SUCCESS"
    notes: str = ""

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

@router.get("/log")
async def get_logs_api(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db = Depends(get_db)
):
    """
    Retrieve chronological audit logs, matching system events and automated operator actions.
    """
    try:
        logs = await audit_repo.get_audit_log(db, limit=limit, offset=offset)
        total = await audit_repo.get_audit_count(db)
        return {
            "entries": [serialize_mongo_doc(l) for l in logs],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query audit logs: {e}")

@router.get("")
async def get_logs_alias(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db = Depends(get_db)
):
    """
    Alias / backward compatibility index for chronological audit logs.
    """
    res = await get_logs_api(limit=limit, offset=offset, db=db)
    return {
        "logs": res["entries"],
        "total": res["total"],
        "limit": res["limit"],
        "offset": res["offset"]
    }

@router.post("/log", dependencies=[Depends(verify_api_key)])
async def log_action_pydantic_api(
    entry: AuditEntry,
    db = Depends(get_db)
):
    """
    Create a structured audit entry and log it securely using Pydantic parameters.
    """
    try:
        # Pydantic v2 compatible dict conversion
        entry_dict = entry.model_dump() if hasattr(entry, "model_dump") else entry.dict()
        
        # Inject standard timestamp
        entry_dict["timestamp"] = datetime.now(timezone.utc)
        
        # Set a severity / details fallback for backward compatibility
        entry_dict["severity"] = "INFO" if entry.outcome == "SUCCESS" else "WARNING"
        entry_dict["details"] = f"{entry.action_type} - {entry.notes}"
        
        result = await audit_repo.append_audit_entry(db, entry_dict)
        
        # Broadcast via WebSockets
        try:
            from backend.routers.websocket_router import broadcast
            serialized = serialize_mongo_doc(result)
            await broadcast({
                "type": "audit_logged",
                "entry": serialized
            })
        except Exception:
            pass
            
        return {"inserted_id": str(result.get("_id"))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append audit entry: {e}")

@router.post("", dependencies=[Depends(verify_api_key)])
async def log_action_legacy_api(
    action_type: str,
    details: str,
    severity: str = "INFO",
    db = Depends(get_db)
):
    """
    Legacy and manual audit append route supporting direct URL parameters.
    """
    entry_dict = {
        "timestamp": datetime.now(timezone.utc),
        "action_type": action_type,
        "severity": severity,
        "details": details,
        "actor": "ORBIT_SENTINEL_OPERATOR",
        "outcome": "SUCCESS",
        "notes": details
    }
    try:
        result = await audit_repo.append_audit_entry(db, entry_dict)
        
        # Broadcast via WebSockets
        try:
            from backend.routers.websocket_router import broadcast
            serialized = serialize_mongo_doc(result)
            await broadcast({
                "type": "audit_logged",
                "entry": serialized
            })
        except Exception:
            pass
            
        return serialize_mongo_doc(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append legacy audit entry: {e}")
