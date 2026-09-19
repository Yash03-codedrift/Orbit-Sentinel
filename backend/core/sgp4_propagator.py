import logging
import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

try:
    from sgp4.api import Satrec, jday, wgs84 as WGS84
except ImportError:
    try:
        from sgp4.api import Satrec, jday, WGS84
    except ImportError:
        Satrec = None
        jday = None
        WGS84 = None

from backend.utils.time_utils import utc_now, datetime_to_iso, gast
from backend.utils.coordinate_transforms import eci_to_geodetic

logger = logging.getLogger("orbit_sentinel.sgp4_propagator")

def _propagate_batch_sync(satellites_list: List[Dict[str, Any]], timestamps_list: List[datetime]) -> Dict[str, Any]:
    """
    Optimized synchronous solver using sgp4_array for vectorized propagation.
    Reduces complexity from O(Sats * Times) calls to O(Sats) calls for orbital physics.
    """
    if Satrec is None:
        logger.error("sgp4 library is not installed.")
        return {}

    results = {}
    total_sats = len(satellites_list)
    num_timestamps = len(timestamps_list)
    
    logger.info(f"Running vectorized SGP4 batch solver: {total_sats} objects over {num_timestamps} timestamps.")

    # 1. Pre-calculate Julian Date arrays for the entire batch
    jd_list = []
    fr_list = []
    iso_timestamps = []
    gast_values = []

    for ts in timestamps_list:
        jd, fr = jday(
            ts.year, ts.month, ts.day, 
            ts.hour, ts.minute, ts.second + ts.microsecond / 1e6
        )
        jd_list.append(jd)
        fr_list.append(fr)
        iso_timestamps.append(datetime_to_iso(ts))
        # Pre-calculate GAST for coordinate transformation
        gast_values.append(gast(ts))

    jd_array = np.array(jd_list)
    fr_array = np.array(fr_list)

    # 2. Iterate through satellites
    for idx, sat_data in enumerate(satellites_list):
        if idx > 0 and idx % 1000 == 0:
            logger.info(f"Vectorized propagation progress: {idx}/{total_sats}")

        norad_id = sat_data["norad_id"]
        tle1 = sat_data.get("tle1")
        tle2 = sat_data.get("tle2")

        if not tle1 or not tle2:
            continue

        try:
            sat = Satrec.twoline2rv(tle1, tle2)
            
            # Perform vectorized propagation for all timestamps at once
            # e: error codes (array of len num_timestamps)
            # r: positions (num_timestamps, 3)
            # v: velocities (num_timestamps, 3)
            e, r, v = sat.sgp4_array(jd_array, fr_array)

            pos_history = []
            
            # 3. Post-process the results (Coordinate transformation)
            for i in range(num_timestamps):
                if e[i] != 0:
                    continue
                
                x, y, z = r[i]
                vx, vy, vz = v[i]
                
                # Convert ECI to Geodetic using pre-calculated GAST
                lat, lon, alt = eci_to_geodetic(x, y, z, gast_values[i])
                speed_kmps = float(np.sqrt(vx**2 + vy**2 + vz**2))

                pos_history.append({
                    "t": iso_timestamps[i],
                    "x": float(x),
                    "y": float(y),
                    "z": float(z),
                    "vx": float(vx),
                    "vy": float(vy),
                    "vz": float(vz),
                    "lat": float(lat),
                    "lon": float(lon),
                    "alt": float(alt),
                    "speed_kmps": speed_kmps
                })

            if pos_history:
                results[norad_id] = pos_history

        except Exception as exc:
            logger.error(f"Failed to propagate SAT {norad_id}: {exc}")
            continue

    logger.info(f"Successfully generated trajectories for {len(results)} satellites.")
    return results

# --- Keep existing helper functions but ensure they call the new sync logic ---

def get_propagation_timestamps(hours_ahead: float = 24.0, interval_minutes: float = 5.0) -> List[datetime]:
    """
    Generates a list of UTC datetime timestamps from now to hours_ahead,
    spaced interval_minutes apart, for batch SGP4 propagation.
    """
    now = utc_now()
    timestamps = []
    total_minutes = int(hours_ahead * 60)
    for i in range(0, total_minutes, int(interval_minutes)):
        timestamps.append(now + timedelta(minutes=i))
    return timestamps

def propagate_single(tle1: str, tle2: str, timestamp_utc: datetime) -> Optional[Dict[str, Any]]:
    """Remaining as a helper for single lookups if needed elsewhere."""
    if Satrec is None: return None
    try:
        sat = Satrec.twoline2rv(tle1, tle2)
        jd, fr = jday(timestamp_utc.year, timestamp_utc.month, timestamp_utc.day, 
                      timestamp_utc.hour, timestamp_utc.minute, 
                      timestamp_utc.second + timestamp_utc.microsecond / 1e6)
        e, r, v = sat.sgp4(jd, fr)
        if e != 0: return None
        x, y, z = r
        vx, vy, vz = v
        lat, lon, alt = eci_to_geodetic(x, y, z, gast(timestamp_utc))
        return {
            "t": datetime_to_iso(timestamp_utc),
            "x": float(x), "y": float(y), "z": float(z),
            "vx": float(vx), "vy": float(vy), "vz": float(vz),
            "lat": float(lat), "lon": float(lon), "alt": float(alt),
            "speed_kmps": float(np.sqrt(vx**2 + vy**2 + vz**2))
        }
    except Exception: return None

async def propagate_batch_python(satellites_list: List[Dict[str, Any]], timestamps_list: List[datetime]) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=8) as executor:
        return await loop.run_in_executor(
            executor,
            _propagate_batch_sync,
            satellites_list,
            timestamps_list
        )

# Rest of the functions (propagate_batch_rust, propagate_current_positions, etc.) remain the same...
async def propagate_batch_rust(satellites_list: List[Dict[str, Any]], timestamps_list: List[datetime]) -> Dict[str, Any]:
    """
    Attempts to project coordinate structures over massive datasets utilizing a high-efficiency Compiled Rust solver.
    Gracefully falls back to pure Python implementation if the Rust bridge binaries are uncompiled or fail to load.
    """
    try:
        from backend.core.rust_bridge import propagate_via_rust
        logger.info("Routing trajectory solver batch to high-performance native compiled Rust module...")
        return await propagate_via_rust(satellites_list, timestamps_list)
    except Exception as err:
        logger.warning(f"Rust SGP4 solver unavailable, falling back to Python. Root: {err}")
        return await propagate_batch_python(satellites_list, timestamps_list)

def _propagate_current_sync(satellites_to_propagate: List[Dict[str, Any]], ts: datetime) -> List[Dict[str, Any]]:
    """
    Synchronous inner loop to propagate active items at single-timestamp coordinates.
    """
    results = []
    for sat in satellites_to_propagate:
        tle1 = sat.get("tle1")
        tle2 = sat.get("tle2")
        if not tle1 or not tle2:
            continue
            
        pos = propagate_single(tle1, tle2, ts)
        if pos:
            pos["norad_id"] = sat.get("norad_id")
            pos["name"] = sat.get("name")
            pos["criticality_score"] = sat.get("criticality_score", 5.0)
            results.append(pos)
            
    return results

async def propagate_current_positions(satellites_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Propagates all tracking orbits synchronously at the current moment to populate live visual map displays.
    Slices the list up to 5000 records sorted by priority criticality rating.
    """
    prioritized = sorted(
        satellites_list,
        key=lambda s: s.get("criticality_score", 5.0),
        reverse=True
    )[:5000]
    
    ts = utc_now()
    loop = asyncio.get_event_loop()
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        return await loop.run_in_executor(
            executor,
            _propagate_current_sync,
            prioritized,
            ts
        )

def extract_orbit_path(position_series: List[Dict[str, Any]], max_points: int = 200) -> List[Dict[str, Any]]:
    """
    Convenience method downsampling a detailed trajectory path history into a clean set of mapping coordinate pins.
    Optimizes rendering buffers for WebGL rendering components.
    """
    if not position_series:
        return []
        
    n = len(position_series)
    if n <= max_points:
        selected_points = position_series
    else:
        indices = np.linspace(0, n - 1, max_points, dtype=int)
        selected_points = [position_series[i] for i in indices]
        
    return [
        {
            "lat": float(pt["lat"]),
            "lon": float(pt["lon"]),
            "alt": float(pt["alt"])
        }
        for pt in selected_points
    ]
