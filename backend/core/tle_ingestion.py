import logging
import asyncio
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx

try:
    from motor.motor_asyncio import AsyncIOMotorDatabase
except ImportError:
    AsyncIOMotorDatabase = object

from backend.config import settings
from backend.db.mongo_client import get_db
from backend.utils.time_utils import utc_now, datetime_to_iso
from backend.utils.cache import cache

logger = logging.getLogger("orbit_sentinel.tle_ingestion")

import tempfile
CACHE_FILE_PATH = os.path.join(tempfile.gettempdir(), "tle_cache.json")

def parse_tle_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    Parses raw TLE content (supporting standard 3-line format) and returns 
    a structured list of dictionaries with name, tle1, tle2, and norad_id.
    """
    tles = []
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    
    i = 0
    while i < len(lines):
        if i + 2 >= len(lines):
            break
            
        line0 = lines[i]
        line1 = lines[i+1]
        line2 = lines[i+2]
        
        if line1.startswith("1 ") and line2.startswith("2 "):
            try:
                norad_id = line1[2:7].strip()
                tles.append({
                    "name": line0,
                    "tle1": line1,
                    "tle2": line2,
                    "norad_id": norad_id
                })
                i += 3
            except Exception as e:
                logger.warning(f"Error parsing TLE lines for format alignment at chunk line {i}: {e}")
                i += 1
        else:
            i += 1
            
    logger.info(f"Parsed {len(tles)} TLE datasets from raw payload text stream.")
    return tles

async def fetch_gp_data_from_celestrak() -> List[Dict[str, Any]]:
    """
    Fetches active satellite TLEs from CelesTrak GP JSON endpoint (fast, single request).
    Falls back to SatNOGS paginated API if CelesTrak fails.
    """
    # Fast path: CelesTrak active satellites GP JSON (single request, ~6000 sats)
    celestrak_urls = [
        "https://celestrak.org/SATCAT/GP.php?GROUP=active&FORMAT=JSON",
        "https://celestrak.org/SATCAT/GP.php?GROUP=stations&FORMAT=JSON",
    ]
    tles = []
    seen = set()
    logger.info("Fetching TLE catalog from CelesTrak GP JSON endpoint...")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True,
                                  headers={"User-Agent": "OrbitSentinel/1.0"}) as client:
        for url in celestrak_urls:
            try:
                response = await client.get(url)
                response.raise_for_status()
                entries = response.json()
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    norad_id = str(entry.get("NORAD_CAT_ID", "")).strip()
                    tle1 = entry.get("TLE_LINE1", "")
                    tle2 = entry.get("TLE_LINE2", "")
                    name = entry.get("OBJECT_NAME", entry.get("SATNAME", "")).strip()
                    if tle1 and tle2 and norad_id and norad_id not in seen:
                        seen.add(norad_id)
                        tles.append({"name": name, "tle1": tle1, "tle2": tle2, "norad_id": norad_id})
            except Exception as e:
                logger.warning(f"CelesTrak GP fetch error for {url}: {e}")

    if tles:
        logger.info(f"Fetched {len(tles)} TLEs from CelesTrak GP JSON.")
        return tles

    # Slow fallback: SatNOGS paginated API
    logger.warning("CelesTrak failed, falling back to SatNOGS paginated API...")
    url = "https://db.satnogs.org/api/tle/?format=json"
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        while url:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", data) if isinstance(data, dict) else data
                for entry in results:
                    tle0 = entry.get("tle0", "").lstrip("0 ").strip()
                    tle1 = entry.get("tle1", "")
                    tle2 = entry.get("tle2", "")
                    norad_id = str(entry.get("norad_cat_id", "")).strip()
                    if tle1 and tle2 and norad_id:
                        tles.append({"name": tle0, "tle1": tle1, "tle2": tle2, "norad_id": norad_id})
                url = data.get("next") if isinstance(data, dict) else None
            except Exception as e:
                logger.warning(f"SatNOGS fetch error: {e}")
                break
    logger.info(f"Fetched {len(tles)} TLEs from SatNOGS fallback.")
    return tles

async def fetch_single_supplemental_url(client: httpx.AsyncClient, name: str, url: str) -> List[Dict[str, Any]]:
    """
    Asynchronously queries a single target supplemental TLE category file.
    """
    try:
        logger.debug(f"Fetching supplemental catalog block: {name} url: {url}")
        response = await client.get(url)
        response.raise_for_status()
        return parse_tle_text(response.text)
    except Exception as e:
        logger.warning(f"Failed loading supplemental tracking catalog stream '{name}': {e}")
        return []

async def fetch_supplemental_tles() -> List[Dict[str, Any]]:
    """
    Queries supplemental constellation/cluster lists across known active platforms.
    """
    urls = {
        "iss":           "https://celestrak.org/SATCAT/GP.php?CATNR=25544&FORMAT=TLE",
        "starlink":      "https://celestrak.org/SATCAT/GP.php?GROUP=starlink&FORMAT=TLE",
        "oneweb":        "https://celestrak.org/SATCAT/GP.php?GROUP=oneweb&FORMAT=TLE",
        "iridium":       "https://celestrak.org/SATCAT/GP.php?GROUP=iridium-NEXT&FORMAT=TLE",
        "active_geo":    "https://celestrak.org/SATCAT/GP.php?GROUP=geo&FORMAT=TLE",
        "debris_leo":    "https://celestrak.org/SATCAT/GP.php?GROUP=cosmos-1408-debris&FORMAT=TLE",
        "debris_fy1c":   "https://celestrak.org/SATCAT/GP.php?GROUP=fengyun-1c-debris&FORMAT=TLE",
        "debris_irid33": "https://celestrak.org/SATCAT/GP.php?GROUP=iridium-33-debris&FORMAT=TLE",
    }
    
    logger.info("Initializing multi-threaded supplemental network fetch pools...")
    
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (OrbitSentinel/1.0)"}) as client:
        tasks = [fetch_single_supplemental_url(client, key, val) for key, val in urls.items()]
        results = await asyncio.gather(*tasks)
        
    supplemental_tles_map = {}
    for batch in results:
        for item in batch:
            n_id = item["norad_id"]
            if n_id not in supplemental_tles_map:
                supplemental_tles_map[n_id] = item
                
    final_list = list(supplemental_tles_map.values())
    logger.info(f"Consolidated {len(final_list)} distinct supplemental satellites.")
    return final_list

def categorize_object(norad_id: str, name: str, tle_line1: str) -> Dict[str, Any]:
    """
    Examines character descriptors on a space coordinate, determining categorized 
    status classifications and overall criticality threat scores.
    """
    normalized_name = name.upper()
    
    if "DEB" in normalized_name or "DEBRIS" in normalized_name:
        object_type = "DEBRIS"
    elif "R/B" in normalized_name or "ROCKET" in normalized_name:
        object_type = "ROCKET_BODY"
    else:
        object_type = "PAYLOAD"
        
    criticality_score = 5.0
    try:
        numeric_norad = int(norad_id)
    except ValueError:
        numeric_norad = -1

    if norad_id == "25544":
        criticality_score = 10.0
    elif "GPS" in normalized_name or (22877 <= numeric_norad <= 48859):
        criticality_score = 9.0
    elif any(sat in normalized_name for sat in ["GLONASS", "GALILEO", "BEIDOU"]):
        criticality_score = 8.8
    elif any(sat in normalized_name for sat in ["NOAA", "METEOSAT", "GOES"]):
        criticality_score = 8.5
    elif any(sat in normalized_name for sat in ["STARLINK", "ONEWEB", "IRIDIUM"]):
        criticality_score = 8.0
    elif object_type == "PAYLOAD":
        criticality_score = 7.0
    elif object_type == "ROCKET_BODY":
        criticality_score = 3.0
    elif object_type == "DEBRIS":
        criticality_score = 1.0
        
    return {"object_type": object_type, "criticality_score": criticality_score}

async def store_tle_snapshot(db: AsyncIOMotorDatabase, count: int, source: str) -> str:
    """
    FIX: Caches only metadata into the snapshot logs. 
    Removing the full 'tles' list prevents document size limit (16MB) errors.
    """
    snapshot_doc = {
        "fetched_at": utc_now(),
        "count": count,
        "source": source,
        "metadata_only": True
    }
    result = await db["tle_snapshots"].insert_one(snapshot_doc)
    logger.info(f"Captured active snapshot log record. Count: {count} elements.")
    return str(result.inserted_id)

async def fetch_satcat_owner_map() -> Dict[str, str]:
    """
    Fetches CelesTrak SATCAT CSV and builds a norad_id -> country/owner map.
    Returns empty dict on failure so ingestion is never blocked.
    """
    url = "https://celestrak.org/pub/satcat.csv"
    owner_map = {}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            lines = resp.text.splitlines()
            if not lines:
                return owner_map
            header = [h.strip() for h in lines[0].split(",")]
            try:
                norad_idx = header.index("NORAD_CAT_ID")
                owner_idx = header.index("OWNER")
            except ValueError:
                logger.warning("SATCAT CSV header format unexpected, skipping owner map.")
                return owner_map
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) > max(norad_idx, owner_idx):
                    nid = parts[norad_idx].strip().lstrip("0")
                    owner = parts[owner_idx].strip()
                    if nid and owner:
                        owner_map[nid] = owner
            logger.info(f"Loaded {len(owner_map)} owner entries from SATCAT.")
    except Exception as e:
        logger.warning(f"SATCAT owner fetch failed (non-fatal): {e}")
    return owner_map


async def upsert_satellite_catalogue(db, tle_list: list) -> int:
    """Upserts satellites using the db abstraction layer (TinyDB + MongoDB compatible)."""
    if not tle_list:
        logger.info("Empty TLE list received. Bypassing catalog database sync.")
        return 0

    timestamp = utc_now()
    owner_map = await fetch_satcat_owner_map()
    total_processed = 0
    for item in tle_list:
        try:
            categories = categorize_object(item["norad_id"], item["name"], item["tle1"])
            norad_stripped = item["norad_id"].lstrip("0")
            owner = owner_map.get(norad_stripped, owner_map.get(item["norad_id"], "N/A"))
            await db["satellites"].update_one(
                {"norad_id": item["norad_id"]},
                {"$set": {
                    "norad_id": item["norad_id"],
                    "name": item["name"],
                    "tle1": item["tle1"],
                    "tle2": item["tle2"],
                    "object_type": categories["object_type"],
                    "criticality_score": categories["criticality_score"],
                    "last_updated": timestamp,
                    "maneuver_count": 0,
                    "owner": owner,
                }},
                upsert=True,
            )
            total_processed += 1
        except Exception as e:
            logger.warning(f"Failed upserting NORAD {item.get('norad_id')}: {e}")
    logger.info(f"Upserted {total_processed} satellites into catalogue.")
    return total_processed

async def get_cached_tles(db: AsyncIOMotorDatabase) -> List[Dict[str, Any]]:
    """
    FIX: Instead of pulling from the bloated snapshot document, we reconstruct 
    the list from the 'satellites' collection, which is the source of truth.
    """
    try:
        # Reconstruct the TLE list from the main satellites collection
        cursor = db["satellites"].find({}, {"_id": 0, "name": 1, "tle1": 1, "tle2": 1, "norad_id": 1})
        tles = await cursor.to_list(length=30000)
        if tles:
            logger.info(f"Successfully restored {len(tles)} TLEs from satellite collection.")
            return tles
    except Exception as e:
        logger.warning(f"Error loading TLE from satellite collection: {e}")

    # File System Fallback
    if os.path.exists(CACHE_FILE_PATH):
        try:
            logger.info(f"Searching offline fallback datasets from disk: {CACHE_FILE_PATH}")
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as disk_error:
            logger.error(f"Unreadable offline TLE fallback dataset: {disk_error}")

    return []

async def save_tle_cache_to_disk(tle_list: list[Dict[str, Any]]) -> None:
    """
    Saves clean tracking data to file storage on the system drive.
    """
    try:
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(tle_list, f, indent=2)
        logger.info(f"Saved cold-start fallback TLE copy to: {CACHE_FILE_PATH}")
    except Exception as e:
        logger.warning(f"Could not persist cold start cache backup: {e}")

async def run_tle_ingestion_job(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Primary ingestion orchestration procedure.
    """
    logger.info("Initializing TLE ingestion synchronization routine...")
    source = "live"

    gp_tles_task = fetch_gp_data_from_celestrak()
    supp_tles_task = fetch_supplemental_tles()
    
    gp_tles, supp_tles = await asyncio.gather(gp_tles_task, supp_tles_task)
    
    combined_map = {item["norad_id"]: item for item in gp_tles}
    for item in supp_tles:
        combined_map[item["norad_id"]] = item 
        
    merged_list = list(combined_map.values())
    
    if not merged_list:
        logger.warning("Empty orbital feeds. Initiating database cache fallback flow...")
        merged_list = await get_cached_tles(db)
        source = "cache"
        
    if not merged_list:
        logger.critical("No TLE tracking catalog could be parsed or loaded.")
        return {
            "success": False,
            "count": 0,
            "timestamp": datetime_to_iso(utc_now()),
            "source": "failed"
        }

    # 5. Save snapshot always — ensures /tle/status always has a timestamp
    try:
        await store_tle_snapshot(db, len(merged_list), source)
    except Exception as e:
        logger.error(f"Could not archive database snapshot: {e}")

    # 6. Bulk synchronize
    upserted_count = await upsert_satellite_catalogue(db, merged_list)
    
    # 7. Write to client file cache
    if source == "live":
        await save_tle_cache_to_disk(merged_list)

    return {
        "success": True,
        "count": len(merged_list),
        "timestamp": datetime_to_iso(utc_now()),
        "source": source
    }