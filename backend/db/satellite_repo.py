import logging
from typing import List, Dict, Any, Optional
try:
    from motor.motor_asyncio import AsyncIOMotorDatabase
except ImportError:
    AsyncIOMotorDatabase = object
from backend.db.mongo_client import get_db

logger = logging.getLogger("orbit_sentinel.satellite_repo")

async def upsert_satellite(db: AsyncIOMotorDatabase, satellite_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upserts a tracked space object (active satellite, payload, or scrap debris) by its unique NORAD tracking number.
    """
    norad_id = satellite_dict.get("norad_id")
    if not norad_id:
        raise ValueError("Missing 'norad_id' attribute inside the satellite payload.")

    await db["satellites"].update_one(
        {"norad_id": norad_id},
        {"$set": satellite_dict},
        upsert=True
    )
    logger.debug(f"Upserted satellite: NORAD {norad_id}")
    return satellite_dict

async def get_satellite(db: AsyncIOMotorDatabase, norad_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single satellite payload using its NORAD Catalog Number. Standard ISO format strings return empty dictionaries if not matched.
    """
    satellite = await db["satellites"].find_one({"norad_id": norad_id})
    return satellite

async def get_all_satellites(db: AsyncIOMotorDatabase, limit: int = 5000, object_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches all tracked catalog bodies in orbit up to a custom limit. Allows optional filtering on LEO classifications (e.g. 'PAYLOAD', 'DEBRIS').
    """
    query = {}
    if object_type:
        query["object_type"] = object_type

    cursor = db["satellites"].find(query).limit(limit)
    satellites = await cursor.to_list(length=limit)
    return satellites

async def search_satellites(db: AsyncIOMotorDatabase, query_str: str) -> List[Dict[str, Any]]:
    """
    Executes a regex search against satellite human-readable designations. Case insensitive matching.
    """
    if not query_str:
        return []

    cursor = db["satellites"].find({
        "name": {"$regex": query_str, "$options": "i"}
    })
    satellites = await cursor.to_list(length=100)
    return satellites

async def update_satellite_maneuver_count(db: AsyncIOMotorDatabase, norad_id: str) -> Optional[Dict[str, Any]]:
    """
    Increments the historical thruster activation firing counter on the tracking matrix block.
    """
    result = await db["satellites"].find_one_and_update(
        {"norad_id": norad_id},
        {"$inc": {"maneuver_count": 1}},
        return_document=True
    )
    return result
