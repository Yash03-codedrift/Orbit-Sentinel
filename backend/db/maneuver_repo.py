import logging
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.db.mongo_client import get_db

logger = logging.getLogger("orbit_sentinel.maneuver_repo")

async def insert_maneuver(db: AsyncIOMotorDatabase, maneuver_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a newly resolved delta-V chemical payload burn plan trajectory recommendation.
    """
    maneuver_id = maneuver_dict.get("maneuver_id")
    if not maneuver_id:
        raise ValueError("Missing 'maneuver_id' inside the maneuver prescription.")

    await db["maneuvers"].insert_one(maneuver_dict)
    logger.info(f"Recorded orbital maneuver suggestion protocol: {maneuver_id}")
    return maneuver_dict

async def get_maneuver(db: AsyncIOMotorDatabase, maneuver_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves details of a calculated satellite-avoidance maneuver.
    """
    return await db["maneuvers"].find_one({"maneuver_id": maneuver_id})

async def get_recent_maneuvers(db: AsyncIOMotorDatabase, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetches the latest sequence of scheduled or executed chemical payload burn configurations.
    """
    cursor = db["maneuvers"].find().sort("computed_at", -1).limit(limit)
    return await cursor.to_list(length=limit)

async def update_maneuver_verification(
    db: AsyncIOMotorDatabase, 
    maneuver_id: str, 
    verification_result_dict: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Stores independent verification telemetry confirming execution correctness post thrust.
    """
    result = await db["maneuvers"].find_one_and_update(
        {"maneuver_id": maneuver_id},
        {"$set": {"verification_result": verification_result_dict}},
        return_document=True
    )
    return result
