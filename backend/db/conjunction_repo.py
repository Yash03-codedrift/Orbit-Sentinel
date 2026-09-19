import logging
from datetime import datetime, timedelta, timezone
from backend.db.opensearch_client import index_conjunction
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger("orbit_sentinel.conjunction_repo")

async def insert_conjunction(db: AsyncIOMotorDatabase, conjunction_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Upserts a conjunction record keyed on the satellite pair (norad_id_a + norad_id_b).
    This ensures each sweep overwrites stale data instead of accumulating duplicates.
    """
    nid_a = conjunction_dict.get("norad_id_a")
    nid_b = conjunction_dict.get("norad_id_b")
    if not nid_a or not nid_b:
        raise ValueError("Missing norad_id_a or norad_id_b in conjunction data.")

    pair_key = "_".join(sorted([nid_a, nid_b]))
    conjunction_dict["pair_key"] = pair_key

    # Detection sweeps rebuild ConjunctionEvent objects, which gives the same
    # satellite pair a fresh UUID each run. Preserve the existing event_id so
    # frontend detail links do not become stale between polling/websocket ticks.
    existing = await db["conjunctions"].find_one({"pair_key": pair_key})
    if existing and existing.get("event_id"):
        conjunction_dict["event_id"] = existing["event_id"]

    try:
        result = await db["conjunctions"].find_one_and_update(
            {"pair_key": pair_key},
            {"$set": conjunction_dict},
            upsert=True,
            return_document=True
        )
        logger.info(f"Conjunction upserted for pair {pair_key}")
        index_conjunction(conjunction_dict)
        return result
    except Exception as e:
        logger.error(f"Failed to upsert conjunction for pair {pair_key}: {e}")
        return None

async def get_active_conjunctions(db: AsyncIOMotorDatabase) -> List[Dict[str, Any]]:
    """
    Retrieves all high-risk close-approach incidents currently flagged as unresolved,
    sorted by Time of Closest Approach (TCA UTC) in ascending order.
    """
    cursor = db["conjunctions"].find({"resolved": False}).sort("tca_utc", 1)
    return await cursor.to_list(length=1000)

async def get_conjunction(db: AsyncIOMotorDatabase, event_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches details of a single collision warning profile from raw dataset indexes.
    """
    return await db["conjunctions"].find_one({"event_id": event_id})

async def get_conjunction_history(db: AsyncIOMotorDatabase, days: int = 7) -> List[Dict[str, Any]]:
    """
    Fetches historic conjunction records based on TCA within the last N days.
    Handles ISO datetime string values and database datetime instances elegantly.
    """
    threshold_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = {
        "$or": [
            {"tca_utc": {"$gte": threshold_date}},
            {"tca_utc": {"$gte": threshold_date.isoformat()}}
        ]
    }
    cursor = db["conjunctions"].find(query).sort("tca_utc", -1)
    return await cursor.to_list(length=5000)

async def mark_conjunction_resolved(
    db: AsyncIOMotorDatabase, 
    event_id: str, 
    maneuver_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Dampens an active collision alarm by checking resolution tags, and links autonomous avoidance firing operations.
    """
    update_fields = {
        "resolved": True,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "maneuvered": True if maneuver_id else False
    }
    if maneuver_id:
        update_fields["maneuver_id"] = maneuver_id

    result = await db["conjunctions"].find_one_and_update(
        {"event_id": event_id},
        {"$set": update_fields},
        return_document=True
    )
    return result

async def get_conjunction_stats(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Aggregates statistical calculations across global alerts compiled over the current day.
    Returns safe defaults if DB queries fail.
    """
    try:
        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        today_iso = today_start.isoformat()

        # Use $or to handle both datetime and string-stored tca_utc fields
        time_filter = {"$or": [
            {"tca_utc": {"$gte": today_start}},
            {"tca_utc": {"$gte": today_iso}}
        ]}

        total_today = await db["conjunctions"].count_documents(time_filter)

        resolved_query = {"$and": [{"resolved": True}, time_filter]}
        resolved_today = await db["conjunctions"].count_documents(resolved_query)

        risk_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        by_risk_level = {}
        for level in risk_levels:
            by_risk_level[level] = await db["conjunctions"].count_documents({
                "risk_level": level,
                "resolved": {"$ne": True}
            })

        return {
            "total_today": total_today,
            "resolved_today": resolved_today,
            "by_risk_level": by_risk_level
        }
    except Exception as e:
        # Return zero-state rather than 500 — frontend can display gracefully
        return {
            "total_today": 0,
            "resolved_today": 0,
            "by_risk_level": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "error": str(e)
        }

async def search_conjunctions(
    db: AsyncIOMotorDatabase, 
    q: str, 
    date_from: Optional[datetime] = None, 
    date_to: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Searches conjunction incidents using MongoDB's native full-text indexing system.
    Note: Requires the 'conjunction_text_search' index to be initialized in mongo_client.py.
    """
    query: Dict[str, Any] = {}
    
    if q:
        query["$text"] = {"$search": q}

    tca_filter: Dict[str, Any] = {}
    if date_from:
        tca_filter["$gte"] = date_from
    if date_to:
        tca_filter["$lte"] = date_to
    
    if tca_filter:
        query["tca_utc"] = tca_filter

    cursor = db["conjunctions"].find(query).sort("tca_utc", -1)
    return await cursor.to_list(length=1000)
