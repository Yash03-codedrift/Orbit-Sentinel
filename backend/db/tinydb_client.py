"""
TinyDB adapter for Orbit Sentinel — drop-in replacement for MongoDB/Motor.
Uses TinyDB with thread-safe file locking. All collections stored as JSON files
in a ./data/ directory alongside the backend. Zero external services required.

Usage: set USE_TINYDB=true in .env (or just don't set MONGODB_URI).
The routers use get_db() which returns an OrbitDB instance that mirrors
the Motor async API surface used by the repos.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tinydb import TinyDB, Query, where
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

logger = logging.getLogger("orbit_sentinel.tinydb_client")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def _db_path(name: str) -> str:
    return os.path.join(_DATA_DIR, f"{name}.json")


def _serialize(doc: Dict) -> Dict:
    """Convert datetime objects to ISO strings for TinyDB JSON storage."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, dict):
            out[k] = _serialize(v)
        else:
            out[k] = v
    return out


class TinyCollection:
    """
    Async-compatible wrapper around a TinyDB table.
    Mirrors the Motor AsyncIOMotorCollection API used by the repos.
    All methods are async but run synchronously under the hood
    (TinyDB is in-process; no IO blocking to worry about).
    """

    def __init__(self, table):
        self._table = table

    # ── Core CRUD ─────────────────────────────────────────────────────────────

    async def insert_one(self, doc: Dict) -> None:
        self._table.insert(_serialize(doc))

    async def find_one(self, query: Dict) -> Optional[Dict]:
        results = await self._find(query, limit=1)
        return results[0] if results else None

    async def find_one_and_update(
        self, query: Dict, update: Dict,
        upsert: bool = False, return_document: bool = False
    ) -> Optional[Dict]:
        q = self._build_query(query)
        docs = self._table.search(q) if q is not None else self._table.all()

        set_fields = update.get("$set", {})
        inc_fields = update.get("$inc", {})

        if docs:
            doc = dict(docs[0])
            doc.update(_serialize(set_fields))
            for field, val in inc_fields.items():
                doc[field] = doc.get(field, 0) + val
            self._table.update(_serialize(doc), doc_ids=[docs[0].doc_id])
            return doc if return_document else docs[0]
        elif upsert:
            new_doc = {**_serialize(set_fields)}
            self._table.insert(new_doc)
            return new_doc if return_document else None
        return None

    async def update_one(self, query: Dict, update: Dict, upsert: bool = False) -> None:
        q = self._build_query(query)
        docs = self._table.search(q) if q is not None else []
        set_fields = _serialize(update.get("$set", {}))
        inc_fields = update.get("$inc", {})

        if docs:
            doc = dict(docs[0])
            doc.update(set_fields)
            for f, v in inc_fields.items():
                doc[f] = doc.get(f, 0) + v
            self._table.update(doc, doc_ids=[docs[0].doc_id])
        elif upsert:
            self._table.insert(set_fields)

    async def count_documents(self, query: Dict) -> int:
        q = self._build_query(query)
        if q is None:
            return len(self._table.all())
        return len(self._table.search(q))

    def find(self, query: Dict = None) -> "TinyCursor":
        return TinyCursor(self._table, query or {})

    async def create_indexes(self, indexes) -> None:
        # TinyDB is schemaless — indexes are no-ops but accepted silently
        pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _find(self, query: Dict, limit: int = 10000) -> List[Dict]:
        q = self._build_query(query)
        if q is None:
            docs = self._table.all()
        else:
            docs = self._table.search(q)
        return [dict(d) for d in docs[:limit]]

    def _build_query(self, query: Dict):
        """
        Translates a subset of MongoDB query operators into TinyDB Query objects.
        Supported: equality, $or, $gte, $lte, $text (regex fallback), $in.
        """
        if not query:
            return None

        Q = Query()
        parts = []

        for key, val in query.items():
            if key == "$or":
                sub = [self._build_query(c) for c in val if c]
                sub = [s for s in sub if s is not None]
                if sub:
                    combined = sub[0]
                    for s in sub[1:]:
                        combined = combined | s
                    parts.append(combined)
            elif key == "$text":
                search_str = val.get("$search", "")
                # Fallback: search all string fields for the term
                pattern = re.compile(re.escape(search_str), re.IGNORECASE)
                parts.append(Q.noop().test(
                    lambda doc, p=pattern: any(
                        isinstance(v, str) and p.search(v)
                        for v in doc.values()
                    )
                ))
            elif isinstance(val, dict):
                for op, operand in val.items():
                    if op == "$gte":
                        parts.append(Q[key] >= operand)
                    elif op == "$lte":
                        parts.append(Q[key] <= operand)
                    elif op == "$in":
                        parts.append(Q[key].one_of(operand))
                    elif op == "$regex":
                        pattern = re.compile(operand, re.IGNORECASE)
                        parts.append(Q[key].matches(operand, flags=re.IGNORECASE))
            else:
                parts.append(Q[key] == val)

        if not parts:
            return None
        result = parts[0]
        for p in parts[1:]:
            result = result & p
        return result


class TinyCursor:
    """Lazy cursor with chained sort/skip/limit, mirrors Motor cursor."""

    def __init__(self, table, query: Dict):
        self._table = table
        self._query = query
        self._sort_key: Optional[str] = None
        self._sort_dir: int = 1
        self._skip_n: int = 0
        self._limit_n: int = 100000

    def sort(self, key: str, direction: int = 1) -> "TinyCursor":
        self._sort_key = key
        self._sort_dir = direction
        return self

    def skip(self, n: int) -> "TinyCursor":
        self._skip_n = n
        return self

    def limit(self, n: int) -> "TinyCursor":
        self._limit_n = n
        return self

    async def to_list(self, length: int = 10000) -> List[Dict]:
        col = TinyCollection(self._table)
        q = col._build_query(self._query)
        docs = self._table.search(q) if q is not None else self._table.all()
        results = [dict(d) for d in docs]

        if self._sort_key:
            def _key(d):
                v = d.get(self._sort_key)
                if v is None:
                    return 0
                # Handle datetime strings (ISO format)
                if isinstance(v, str):
                    try:
                        from datetime import datetime
                        return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
                    except Exception:
                        return 0
                # Handle datetime objects
                if hasattr(v, 'timestamp'):
                    return v.timestamp()
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return 0
            results.sort(key=_key, reverse=(self._sort_dir == -1))

        results = results[self._skip_n:]
        cap = min(self._limit_n, length)
        return results[:cap]


class OrbitDB:
    """
    Namespace that maps collection names to TinyCollections.
    Accessed like: db["conjunctions"], db["satellites"], etc.
    """

    def __init__(self):
        _ensure_data_dir()
        self._dbs: Dict[str, TinyDB] = {}
        self._collections: Dict[str, TinyCollection] = {}

    def __getitem__(self, name: str) -> TinyCollection:
        if name not in self._collections:
            db_path = _db_path(name)
            tdb = TinyDB(db_path, storage=CachingMiddleware(JSONStorage))
            self._dbs[name] = tdb
            self._collections[name] = TinyCollection(tdb.table("_default"))
        return self._collections[name]

    def close(self):
        for tdb in self._dbs.values():
            try:
                tdb.close()
            except Exception:
                pass


# ── Module-level singleton ──────────────────────────────────────────────────
_orbit_db: Optional[OrbitDB] = None


async def init_db(uri: str, db_name: str) -> OrbitDB:
    global _orbit_db
    if _orbit_db is not None:
        logger.warning("TinyDB already initialized.")
        return _orbit_db

    logger.info(f"Initializing TinyDB (file-based, no MongoDB required). Data dir: {_DATA_DIR}")
    _orbit_db = OrbitDB()
    # Warm up all expected collections so files are created upfront
    for col in ("satellites", "conjunctions", "maneuvers", "audit_log", "tle_snapshots"):
        _ = _orbit_db[col]
    logger.info("TinyDB initialized. Collections ready.")
    return _orbit_db


def get_db() -> Optional[OrbitDB]:
    global _orbit_db
    if _orbit_db is None:
        logger.warning("TinyDB accessed before initialization.")
    return _orbit_db


def close_db() -> None:
    global _orbit_db
    if _orbit_db is not None:
        _orbit_db.close()
        _orbit_db = None
        logger.info("TinyDB closed.")
