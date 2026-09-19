import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from backend.db.mongo_client import get_db
from backend.db import satellite_repo
from backend.core.tle_ingestion import run_tle_ingestion_job, get_cached_tles
from backend.core.sgp4_propagator import propagate_single, propagate_current_positions
from backend.core.scheduler import sentinel_scheduler
from backend.utils.auth import verify_api_key

router = APIRouter()

_COUNTRY_HINTS = {
    # --- MULTINATIONAL ---
    "ISS": "MULTINATIONAL", "ZARYA": "MULTINATIONAL", "NAUKA": "MULTINATIONAL",
    "COLUMBUS": "MULTINATIONAL", "HARMONY": "MULTINATIONAL", "UNITY": "MULTINATIONAL",
    "DESTINY": "MULTINATIONAL", "TRANQUILITY": "MULTINATIONAL",

    # --- USA ---
    "STARLINK": "USA", "NAVSTAR": "USA", "GPS": "USA", "GOES": "USA",
    "TERRA": "USA", "AQUA": "USA", "LANDSAT": "USA", "NOAA": "USA",
    "IRIDIUM": "USA", "GLOBALSTAR": "USA", "WORLDVIEW": "USA", "GEOEYE": "USA",
    "QUICKBIRD": "USA", "DIGITALGLOBE": "USA", "PLANET": "USA", "DOVE": "USA",
    "FLOCK": "USA", "SPIRE": "USA", "LEMUR": "USA", "CAPELLA": "USA",
    "ICESAT": "USA", "AURA": "USA", "GRACE": "USA", "CALIPSO": "USA",
    "CLOUDSAT": "USA", "SORCE": "USA", "TIMED": "USA", "RHESSI": "USA",
    "SWIFT": "USA", "FERMI": "USA", "CHANDRA": "USA", "HUBBLE": "USA",
    "TDRS": "USA", "WGS": "USA", "MUOS": "USA", "AEHF": "USA",
    "SBIRS": "USA", "DSP": "USA", "MILSTAR": "USA", "UFO": "USA",
    "ORBCOMM": "USA", "O3B": "USA", "TELSTAR": "USA", "ECHOSTAR": "USA",
    "DIRECTV": "USA", "HUGHES": "USA", "VIASAT": "USA", "AMC": "USA",
    "SIRIUS": "USA", "XM-": "USA", "GALAXY": "USA",

    # --- RUSSIA ---
    "COSMOS": "RUSSIA", "GLONASS": "RUSSIA", "METEOR": "RUSSIA",
    "RESURS": "RUSSIA", "PROGRESS": "RUSSIA", "SOYUZ": "RUSSIA",
    "MOLNIYA": "RUSSIA", "RADUGA": "RUSSIA", "GORIZONT": "RUSSIA",
    "EXPRESS": "RUSSIA", "LUCH": "RUSSIA", "MERIDIAN": "RUSSIA",
    "GONETS": "RUSSIA", "STRELA": "RUSSIA", "ROKOT": "RUSSIA",
    "KONDOR": "RUSSIA", "KANOPUS": "RUSSIA", "ELECTRO": "RUSSIA",
    "LOTOS": "RUSSIA", "PIRS": "RUSSIA", "POISK": "RUSSIA",
    "RASSVET": "RUSSIA", "ZVEZDA": "RUSSIA", "ZARIA": "RUSSIA",
    "FOTON": "RUSSIA", "BION": "RUSSIA", "PERSONA": "RUSSIA",

    # --- CHINA ---
    "YAOGAN": "CHINA", "BEIDOU": "CHINA", "FENGYUN": "CHINA",
    "TIANGONG": "CHINA", "SHIJIAN": "CHINA", "CHINASAT": "CHINA",
    "ZHONGXING": "CHINA", "HAIYANG": "CHINA", "ZIYUAN": "CHINA",
    "TANSUO": "CHINA", "CBERS": "CHINA/BRAZIL", "TIANZHOU": "CHINA",
    "SHENZHOU": "CHINA", "WENTIAN": "CHINA", "MENGTIAN": "CHINA",
    "LUDI": "CHINA", "HUANJING": "CHINA", "GAOFEN": "CHINA",
    "JILIN": "CHINA", "BEIJING": "CHINA", "CUBESAT-CN": "CHINA",
    "TIANMU": "CHINA", "HONGYAN": "CHINA", "XINGYUN": "CHINA",
    "QUEQIAO": "CHINA", "SHIYAN": "CHINA", "TAIKONAUTS": "CHINA",

    # --- ESA / EUROPE ---
    "SENTINEL": "ESA", "ENVISAT": "ESA", "CRYOSAT": "ESA", "AEOLUS": "ESA",
    "SWARM": "ESA", "GOCE": "ESA", "SMOS": "ESA", "PROBA": "ESA",
    "GAIA": "ESA", "INTEGRAL": "ESA", "XMM": "ESA", "CLUSTER": "ESA",
    "METOP": "ESA/EUMETSAT", "MSG": "ESA/EUMETSAT", "METEOSAT": "ESA",
    "GALILEO": "ESA", "GIOVE": "ESA",

    # --- FRANCE ---
    "SPOT": "FRANCE", "PLEIADES": "FRANCE", "SYRACUSE": "FRANCE",
    "HELIOS": "FRANCE", "PHAROS": "FRANCE", "CSO": "FRANCE",
    "JASON": "FRANCE/USA", "TOPEX": "FRANCE/USA",

    # --- GERMANY ---
    "TERRASAR": "GERMANY", "TANDEM": "GERMANY", "RAPIDEYE": "GERMANY",
    "BIRD": "GERMANY", "CHAMP": "GERMANY", "GRACE-FO": "GERMANY/USA",
    "SAR-LUPE": "GERMANY", "HEINRICH": "GERMANY",

    # --- ITALY ---
    "COSMO": "ITALY", "SKYMED": "ITALY", "SICRAL": "ITALY",
    "ATHENA": "ITALY", "MIOSAT": "ITALY",

    # --- UK ---
    "ONEWEB": "UK", "SKYNET": "UK", "INMARSAT": "UK",
    "UKTUBE": "UK", "SSTL": "UK", "SURREY": "UK",
    "TOPSAT": "UK", "BILSAT": "UK",

    # --- JAPAN ---
    "ALOS": "JAPAN", "HIMAWARI": "JAPAN", "IGS": "JAPAN", "QZSS": "JAPAN",
    "DAICHI": "JAPAN", "MICHIBIKI": "JAPAN", "MTSAT": "JAPAN",
    "HAYABUSA": "JAPAN", "AKARI": "JAPAN", "SUZAKU": "JAPAN",
    "KOUNOTORI": "JAPAN", "HTV": "JAPAN", "GCOM": "JAPAN",
    "ETS": "JAPAN", "OICETS": "JAPAN", "SERVIS": "JAPAN",

    # --- INDIA ---
    "CARTOSAT": "INDIA", "RISAT": "INDIA", "RESOURCESAT": "INDIA",
    "INSAT": "INDIA", "IRNSS": "INDIA", "GSAT": "INDIA", "NAVIC": "INDIA",
    "EMISAT": "INDIA", "ASTROSAT": "INDIA", "SARAL": "INDIA",
    "OCEANSAT": "INDIA", "MEGHATROPIQUES": "INDIA", "SCATSAT": "INDIA",
    "MICROSAT": "INDIA", "PRATIGYAN": "INDIA", "EOS": "INDIA",

    # --- SOUTH KOREA ---
    "KOMPSAT": "S.KOREA", "ARIRANG": "S.KOREA", "COMS": "S.KOREA",
    "ANASIS": "S.KOREA", "CHEOLLIAN": "S.KOREA",

    # --- ISRAEL ---
    "AMOS": "ISRAEL", "OFEQ": "ISRAEL", "TECSAR": "ISRAEL",
    "VENUS": "ISRAEL/FRANCE", "SHALOM": "ISRAEL",

    # --- IRAN ---
    "NOOR": "IRAN", "SINA": "IRAN", "ZAFAR": "IRAN",
    "PARS": "IRAN", "NAHID": "IRAN",

    # --- NORTH KOREA ---
    "KWANGMYONGSONG": "N.KOREA", "MALLIGYONG": "N.KOREA",

    # --- UAE ---
    "KHALIFASAT": "UAE", "YAHSAT": "UAE", "THURAYA": "UAE",
    "HOPE": "UAE", "DUBAISAT": "UAE",

    # --- TURKEY ---
    "TURKSAT": "TURKEY", "RASAT": "TURKEY", "GÖKTÜRK": "TURKEY",
    "GOKTURK": "TURKEY", "BILSAT": "TURKEY",

    # --- BRAZIL ---
    "SGDC": "BRAZIL", "AMAZONIA": "BRAZIL", "CBERS": "BRAZIL/CHINA",
    "SACI": "BRAZIL", "UNOSAT": "BRAZIL",

    # --- CANADA ---
    "RADARSAT": "CANADA", "ANIK": "CANADA", "NIMIQ": "CANADA",
    "SCISAT": "CANADA", "CASCADE": "CANADA", "M3MSAT": "CANADA",

    # --- AUSTRALIA ---
    "OPTUS": "AUSTRALIA", "AUSSAT": "AUSTRALIA", "FEDSAT": "AUSTRALIA",

    # --- ARGENTINA ---
    "ARSAT": "ARGENTINA", "NUSAT": "ARGENTINA", "SAOCOM": "ARGENTINA",
    "SAC-": "ARGENTINA",

    # --- INDONESIA ---
    "PALAPA": "INDONESIA", "TELKOM": "INDONESIA", "BRISat": "INDONESIA",

    # --- NIGERIA ---
    "NIGCOMSAT": "NIGERIA", "NIGERIASAT": "NIGERIA",

    # --- EGYPT ---
    "EGYPTSAT": "EGYPT", "NILESAT": "EGYPT",

    # --- SAUDI ARABIA ---
    "ARABSAT": "SAUDI ARABIA", "SAUDISAT": "SAUDI ARABIA",
    "SAUDI": "SAUDI ARABIA",

    # --- INTERNATIONAL / COMMERCIAL ---
    "INTELSAT": "INTL", "SES-": "INTL", "EUTELSAT": "INTL",
    "LEOSAT": "INTL", "TELEDESIC": "INTL", "O3B": "INTL",
    "HISPASAT": "SPAIN", "AMAZONAS": "SPAIN",
    "HELLAS": "GREECE", "HELLASAT": "GREECE",
    "NILESAT": "EGYPT", "BADR": "SAUDI ARABIA",
    "PAKSAT": "PAKISTAN", "MEASAT": "MALAYSIA",
    "THAICOM": "THAILAND", "APSTAR": "HONG KONG",
    "ASIASAT": "HONG KONG", "JCSAT": "JAPAN",
    "N-STAR": "JAPAN", "SUPERBIRD": "JAPAN",
    "KOREASAT": "S.KOREA",

    # --- DEBRIS / UNKNOWN ---
    "DEBRIS": "N/A", "DEB": "N/A", "R/B": "N/A",
    "ROCKET": "N/A", "OBJECT": "N/A", "UNKNOWN": "N/A",
}

def _resolve_owner(name_or_owner: str) -> str:
    if not name_or_owner:
        return "N/A"
    val = name_or_owner.upper()
    for keyword, country in _COUNTRY_HINTS.items():
        if keyword in val:
            return country
    return "N/A"

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

@router.get("/status")
async def get_tle_status(db = Depends(get_db)):
    """
    Retrieve current TLE cache status, count, scheduled pull times, and offline indicators.
    """
    # 1. Last pull time
    last_pull_time = None
    try:
        snapshots = await db["tle_snapshots"].find({}).sort("fetched_at", -1).to_list(length=1)
        latest_snapshot = snapshots[0] if snapshots else None
        if latest_snapshot:
            fetched = latest_snapshot.get("fetched_at")
            if isinstance(fetched, datetime):
                last_pull_time = fetched.isoformat()
            elif isinstance(fetched, str):
                last_pull_time = fetched
    except Exception:
        pass

    # Fallback — read last_updated from satellites (always written during ingestion)
    if not last_pull_time:
        try:
            sats = await db["satellites"].find({}).sort("last_updated", -1).to_list(length=1)
            if sats:
                lu = sats[0].get("last_updated")
                if isinstance(lu, datetime):
                    last_pull_time = lu.isoformat()
                elif isinstance(lu, str):
                    last_pull_time = lu
        except Exception:
            pass

    # 2. Object count
    try:
        object_count = await db["satellites"].count_documents({})
    except Exception:
        object_count = 0

    # 3. Next scheduled pull (in X minutes)
    next_scheduled_pull = 10
    try:
        if sentinel_scheduler and sentinel_scheduler.scheduler:
            job = sentinel_scheduler.scheduler.get_job("job_ingest_tles")
            if job and job.next_run_time:
                now_utc = datetime.now(timezone.utc)
                diff = job.next_run_time - now_utc
                next_scheduled_pull = max(0, int(diff.total_seconds() / 60))
    except Exception:
        pass

    # 4. Cache file indicator
    cache_file_exists = os.path.exists("tle_cache.json")

    return {
        "last_pull_time": last_pull_time,
        "object_count": object_count,
        "next_scheduled_pull": next_scheduled_pull,
        "cache_file_exists": cache_file_exists
    }

@router.get("/objects")
async def get_tracked_objects(
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db = Depends(get_db)
):
    """
    Retrieve cached TLE elements using limit, offset pagination, and target classifications.
    """
    query = {}
    if type:
        query["object_type"] = type

    try:
        cursor = db["satellites"].find(query).skip(offset).limit(limit)
        objects = await cursor.to_list(length=limit)
        return [serialize_mongo_doc(obj) for obj in objects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database retrieval failed: {e}")

@router.get("/object/{norad_id}")
async def get_tracked_object_detail(norad_id: str, db = Depends(get_db)):
    """
    Fetch a single satellite tracking profile mapped with real time propagated position coordinates.
    """
    sat = await db["satellites"].find_one({"norad_id": norad_id})
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found.")

    tle1 = sat.get("tle1")
    tle2 = sat.get("tle2")
    position_data = None
    if tle1 and tle2:
        try:
            now_utc = datetime.now(timezone.utc)
            position_data = propagate_single(tle1, tle2, now_utc)
        except Exception:
            pass

    serialized_sat = serialize_mongo_doc(sat)
    serialized_sat["position"] = position_data
    return serialized_sat

async def _run_tle_and_log(db):
    from datetime import datetime, timezone
    from backend.db import audit_repo
    try:
        result = await run_tle_ingestion_job(db)
        await audit_repo.append_audit_entry(db, {
            "timestamp": datetime.now(timezone.utc),
            "action_type": "TLE_REFRESH",
            "actor": "ORBIT_SENTINEL_AUTONOMOUS",
            "outcome": "SUCCESS" if result.get("success") else "FAILED",
            "severity": "INFO" if result.get("success") else "WARNING",
            "details": f"TLE ingestion complete. {result.get('count', 0)} objects synced from {result.get('source', 'unknown')}.",
            "notes": f"source={result.get('source')} count={result.get('count', 0)}"
        })
    except Exception as e:
        from datetime import datetime, timezone
        from backend.db import audit_repo
        await audit_repo.append_audit_entry(db, {
            "timestamp": datetime.now(timezone.utc),
            "action_type": "TLE_REFRESH",
            "actor": "ORBIT_SENTINEL_AUTONOMOUS",
            "outcome": "FAILED",
            "severity": "WARNING",
            "details": f"TLE ingestion failed: {str(e)}",
            "notes": str(e)
        })

@router.post("/refresh", dependencies=[Depends(verify_api_key)])
async def trigger_refresh_job(background_tasks: BackgroundTasks, db = Depends(get_db)):
    """
    Trigger standard CelesTrak and Supplemental satellite synchronization in the background.
    """
    background_tasks.add_task(_run_tle_and_log, db)
    return {
        "status": "refresh_triggered",
        "message": "Background TLE refresh job has been scheduled."
    }

@router.get("/positions/current")
async def get_current_world_positions(db = Depends(get_db)):
    """
    Propagates top 5000 tracked targets to current system clock time to paint map visuals.
    """
    try:
        satellites_list = await db["satellites"].find({}).sort("criticality_score", -1).limit(5000).to_list(length=5000)
        if not satellites_list:
            return []

        # Strip non-serializable MongoDB _id before passing to thread executor
        clean_sats = [{k: v for k, v in s.items() if k != "_id"} for s in satellites_list]

        # Propagate batch — catch propagation errors separately for clearer logs
        try:
            positions = await propagate_current_positions(clean_sats)
        except Exception as prop_err:
            raise HTTPException(status_code=500, detail=f"SGP4 propagation engine error: {prop_err}")

        if not positions:
            return []

        # Build index maps to enrich missing values from database copies
        sats_map = {s["norad_id"]: s for s in clean_sats if "norad_id" in s}

        enriched = []
        for pos in positions:
            n_id = pos.get("norad_id")
            lat = pos.get("lat")
            lon = pos.get("lon")
            alt = pos.get("alt")
            # Skip satellites with NaN or None positions (degenerate TLE)
            if lat is None or lon is None or alt is None:
                continue
            try:
                if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and isinstance(alt, (int, float))):
                    continue
                import math
                if math.isnan(lat) or math.isnan(lon) or math.isnan(alt):
                    continue
            except Exception:
                continue
            orig_sat = sats_map.get(n_id, {})

            # Derive orbital elements from TLE line 2
            tle2 = orig_sat.get("tle2", "")
            incl_deg = None
            apogee_km = None
            perigee_km = None
            try:
                if len(tle2) > 60:
                    incl_deg = round(float(tle2[8:16].strip()), 4)
                    mean_motion = float(tle2[52:63].strip())  # rev/day
                    ecc_str = "0." + tle2[26:33].strip()
                    ecc = float(ecc_str)
                    MU = 398600.4418  # km^3/s^2
                    n_rad = mean_motion * 2 * 3.141592653589793 / 86400
                    a = (MU / (n_rad ** 2)) ** (1/3)
                    RE = 6371.0
                    apogee_km = round(a * (1 + ecc) - RE, 1)
                    perigee_km = round(a * (1 - ecc) - RE, 1)
            except Exception:
                pass

            enriched.append({
                "norad_id": n_id,
                "name": pos.get("name", orig_sat.get("name", "SAT")),
                "object_type": orig_sat.get("object_type", "PAYLOAD"),
                "criticality_score": pos.get("criticality_score", orig_sat.get("criticality_score", 5.0)),
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "speed_kmps": pos.get("speed_kmps"),
                "velocity": pos.get("speed_kmps"),
                "inclination": incl_deg,
                "apogee": apogee_km,
                "perigee": perigee_km,
                "owner": _resolve_owner(orig_sat.get("owner") or orig_sat.get("country_code") or pos.get("name", orig_sat.get("name", ""))),
                "country": _resolve_owner(orig_sat.get("owner") or orig_sat.get("country_code") or pos.get("name", orig_sat.get("name", ""))),
                "x": pos.get("x"),
                "y": pos.get("y"),
                "z": pos.get("z"),
                "vx": pos.get("vx"),
                "vy": pos.get("vy"),
                "vz": pos.get("vz"),
                "t": pos.get("t")
            })
        return enriched
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to propagate current positions: {e}")

@router.get("/object/{norad_id}/orbit")
async def get_full_orbit_path(norad_id: str, db = Depends(get_db)):
    """
    Calculates detailed geographic trajectory nodes tracing a complete 90 minutes low-orbit cycle.
    """
    sat = await db["satellites"].find_one({"norad_id": norad_id})
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found.")

    tle1 = sat.get("tle1")
    tle2 = sat.get("tle2")
    if not tle1 or not tle2:
        raise HTTPException(status_code=400, detail="Missing baseline TLE parameters to compute propagation paths.")

    try:
        now_utc = datetime.now(timezone.utc)
        orbit_nodes = []
        for i in range(91):  # 90 minutes full orbit cycle, +1 to close the loop
            ts = now_utc + timedelta(minutes=i)
            pos = propagate_single(tle1, tle2, ts)
            if pos:
                orbit_nodes.append({
                    "lat": pos.get("lat"),
                    "lon": pos.get("lon"),
                    "alt": pos.get("alt")
                })
        return orbit_nodes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to propagate orbit coordinates: {e}")
