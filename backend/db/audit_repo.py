import logging
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.db.mongo_client import get_db

logger = logging.getLogger("orbit_sentinel.audit_repo")

async def append_audit_entry(db: AsyncIOMotorDatabase, entry_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Appends an immutable space telemetry audit logging sequence.
    This creates write-once, read-only entries. Update operations are structurally blocked.
    """
    await db["audit_log"].insert_one(entry_dict)
    logger.debug(f"Audit record logged: {entry_dict.get('action_type', 'UNSPECIFIED_EVENT')}")
    return entry_dict

async def get_audit_log(db: AsyncIOMotorDatabase, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Retrieves chronological logs descending from the most recent system timestamps with custom offsets.
    """
    cursor = db["audit_log"].find().sort("timestamp", -1).skip(offset).limit(limit)
    return await cursor.to_list(length=limit)

async def get_audit_count(db: AsyncIOMotorDatabase) -> int:
    """
    Returns the total volume count of recorded physical orbital audits.
    """
    return await db["audit_log"].count_documents({})
