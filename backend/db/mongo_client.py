"""
Database client selector for Orbit Sentinel.

Priority:
  1. If USE_TINYDB=true in env  → TinyDB (file-based, zero setup)
  2. If MONGODB_URI is reachable  → Motor (async MongoDB)
  3. Fallback                     → TinyDB automatically

TinyDB is recommended for local dev / hackathon judging.
Set USE_TINYDB=true in your .env to force it.
"""
import logging
import os
from typing import Optional, Any

logger = logging.getLogger("orbit_sentinel.db")

_client = None
_db = None


def _use_tinydb() -> bool:
    return os.environ.get("USE_TINYDB", "false").lower() in ("true", "1", "yes")


async def init_db(uri: str, db_name: str) -> Any:
    global _client, _db

    if _db is not None:
        return _db

    if _use_tinydb():
        logger.info("USE_TINYDB=true — using TinyDB (no MongoDB required).")
        from backend.db.tinydb_client import init_db as tdb_init
        _db = await tdb_init(uri, db_name)
        return _db

    # Try MongoDB; fall back to TinyDB on connection failure
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT

        logger.info(f"Connecting to MongoDB at {uri} (db: {db_name})...")
        _client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=4000,
            connectTimeoutMS=4000,
            maxPoolSize=50,
        )
        _db = _client[db_name]

        # Ping to verify connection
        await _client.admin.command("ping")

        # Create indexes
        await _db["satellites"].create_indexes([
            IndexModel([("norad_id", ASCENDING)], unique=True),
            IndexModel([("name", ASCENDING)]),
            IndexModel([("object_type", ASCENDING)]),
        ])
        await _db["conjunctions"].create_indexes([
            IndexModel([("tca_utc", ASCENDING)]),
            IndexModel([("risk_level", ASCENDING)]),
            IndexModel([("resolved", ASCENDING)]),
            IndexModel([("norad_id_a", ASCENDING)]),
            IndexModel([("norad_id_b", ASCENDING)]),
            IndexModel([("event_id", ASCENDING)], unique=True),
            IndexModel([("name_a", TEXT), ("name_b", TEXT)], name="conjunction_text_search"),
        ])
        await _db["maneuvers"].create_indexes([
            IndexModel([("conjunction_event_id", ASCENDING)]),
            IndexModel([("computed_at", DESCENDING)]),
            IndexModel([("maneuver_id", ASCENDING)], unique=True),
        ])
        await _db["audit_log"].create_indexes([
            IndexModel([("timestamp", DESCENDING)]),
            IndexModel([("action_type", ASCENDING)]),
        ])
        await _db["tle_snapshots"].create_indexes([
            IndexModel([("fetched_at", DESCENDING)]),
        ])

        logger.info("MongoDB connected and indexes initialized.")
        return _db

    except Exception as e:
        logger.warning(
            f"MongoDB connection failed ({e}). "
            f"Falling back to TinyDB (file-based). "
            f"Set USE_TINYDB=true in .env to silence this warning."
        )
        _client = None
        from backend.db.tinydb_client import init_db as tdb_init
        _db = await tdb_init(uri, db_name)
        return _db


def get_db() -> Optional[Any]:
    global _db
    if _db is None:
        logger.warning("Database accessed before initialization.")
    return _db


def close_db() -> None:
    global _client, _db
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None
    if _db is not None:
        try:
            _db.close()
        except Exception:
            pass
        _db = None
    logger.info("Database connection closed.")
