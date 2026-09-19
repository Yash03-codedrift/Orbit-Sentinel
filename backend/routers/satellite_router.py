from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from backend.db.mongo_client import get_db
from backend.db import satellite_repo

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

@router.get("")
async def get_satellites(
    limit: int = Query(default=100, ge=1, le=5000),
    object_type: Optional[str] = Query(default=None),
    db = Depends(get_db)
):
    """
    Retrieve satellite catalog entries, optionally filtering by LEO object type.
    """
    try:
        satellites = await satellite_repo.get_all_satellites(db, limit=limit, object_type=object_type)
        return [serialize_mongo_doc(s) for s in satellites]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

@router.get("/search")
async def search_satellites_api(
    q: str = Query(..., min_length=1),
    db = Depends(get_db)
):
    """
    Search satellite catalog targets by name (case-insensitive regex match). Max 50 results.
    """
    try:
        results = await satellite_repo.search_satellites(db, query_str=q)
        serialized_results = [serialize_mongo_doc(s) for s in results]
        return serialized_results[:50]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Satellite search failed: {e}")

@router.get("/{norad_id}")
async def get_satellite_by_id(
    norad_id: str,
    db = Depends(get_db)
):
    """
    Retrieve a single satellite's orbital features by NORAD ID.
    """
    sat = await satellite_repo.get_satellite(db, norad_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found.")
    return serialize_mongo_doc(sat)

@router.get("/{norad_id}/conjunctions")
async def get_satellite_conjunctions(
    norad_id: str,
    db = Depends(get_db)
):
    """
    Retrieve all historical or active close approach threat alerts involving this spacecraft.
    """
    try:
        cursor = db["conjunctions"].find({
            "$or": [
                {"norad_id_a": norad_id},
                {"norad_id_b": norad_id}
            ]
        }).sort("tca_utc", -1)
        conjs = await cursor.to_list(length=1000)
        return [serialize_mongo_doc(c) for c in conjs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load satellite conjunctions: {e}")
