from datetime import datetime, timezone
from backend.db.mongo_client import get_db

async def record_daily_snapshot(kessler_index: float) -> None:
    """Persist today's live Kessler Index once, so future trend charts
    show the real historical value instead of a retroactive estimate."""
    db = get_db()
    if db is None:
        return
    today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db["kessler_history"].update_one(
        {"date": today_key},
        {"$set": {"date": today_key, "risk": round(kessler_index, 2)}},
        upsert=True
    )

async def get_recent_snapshots(days: int = 7) -> dict:
    db = get_db()
    if db is None:
        return {}
    cursor = db["kessler_history"].find({}).sort("date", -1).limit(days)
    docs = await cursor.to_list(length=days)
    return {d["date"]: d["risk"] for d in docs}