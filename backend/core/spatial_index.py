import logging
import numpy as np
from scipy.spatial import KDTree

logger = logging.getLogger("orbit_sentinel.spatial_index")

def build_spatial_index(positions_at_time: dict) -> tuple[KDTree, list[str]]:
    """
    Builds a high-performance scipy.spatial.KDTree using the provided dictionary
    mapping norad_id to three-dimensional positional tuple matrices (x, y, z) in km.
    Returns the KDTree and a ordered list of norad_id strings for index mapping.
    """
    ordered_norad_ids = list(positions_at_time.keys())
    if not ordered_norad_ids:
        positions_array = np.empty((0, 3), dtype=float)
        kdtree = KDTree(positions_array)
        return kdtree, []
        
    positions_array = np.array([positions_at_time[nid] for nid in ordered_norad_ids], dtype=float)
    kdtree = KDTree(positions_array)
    return kdtree, ordered_norad_ids

def find_close_pairs(kdtree: KDTree, norad_ids: list[str], threshold_km: float) -> list[tuple]:
    """
    Finds index pairs within the threshold_km using SciPy's fast KDTree set lookup query.
    Calculates precise Euclidean clearances and returns ordered lists of (norad_id_a, norad_id_b, distance_km).
    """
    if not norad_ids or kdtree.n == 0:
        return []
        
    try:
        pairs_idx = kdtree.query_pairs(threshold_km, output_type='ndarray')
    except Exception:
        # Graceful fallback query signature if output_type is not supported on legacy environments
        pairs_idx = list(kdtree.query_pairs(threshold_km))
        
    results = []
    pos_data = kdtree.data
    
    for idx_a, idx_b in pairs_idx:
        norad_id_a = norad_ids[idx_a]
        norad_id_b = norad_ids[idx_b]
        
        pos_a = pos_data[idx_a]
        pos_b = pos_data[idx_b]
        
        distance_km = float(np.sqrt(np.sum((pos_a - pos_b) ** 2)))
        results.append((norad_id_a, norad_id_b, distance_km))
        
    # Sort results by Euclidean distance ascending
    results.sort(key=lambda x: x[2])
    return results

def filter_same_constellation(pairs: list[tuple], satellites_catalogue: dict) -> list[tuple]:
    """
    Filters conjunction candidate pairs to avoid listing false alarms due to multi-satellite constellation matches,
    while ensuring mission-critical interactions (like Payload vs Debris) are preserved even if they share a name prefix.
    """
    filtered = []
    
    for norad_a, norad_b, dist in pairs:
        sat_a = satellites_catalogue.get(norad_a, {})
        sat_b = satellites_catalogue.get(norad_b, {})
        
        type_a = sat_a.get("object_type", "")
        type_b = sat_b.get("object_type", "")
        
        # Rule 1: Exclude minor clutter debris tracking (where both items are DEBRIS with criticality < 2.0)
        crit_a = sat_a.get("criticality_score", 5.0)
        crit_b = sat_b.get("criticality_score", 5.0)
        
        if type_a == "DEBRIS" and type_b == "DEBRIS" and crit_a < 2.0 and crit_b < 2.0:
            continue
            
        # Rule 2: Exclude constellation self-conjunctions (e.g. STARLINK-1 vs STARLINK-2)
        # ONLY filter if prefixes match AND they are the same object type.
        # This prevents filtering "ISS (ZARYA)" vs "ISS DEB".
        name_a = sat_a.get("name", "")
        name_b = sat_b.get("name", "")
        
        def get_constellation_prefix(name: str) -> str:
            if not name:
                return ""
            parts = name.replace("_", "-").split("-")
            first_word = name.split()[0].strip().upper()
            prefix = parts[0].strip().split()[0].strip().upper()
            return prefix if len(prefix) <= len(first_word) else first_word
            
        pref_a = get_constellation_prefix(name_a)
        pref_b = get_constellation_prefix(name_b)
        
        if pref_a and pref_b and pref_a == pref_b:
            # If names match, only filter out if they are the same type (e.g. both PAYLOAD)
            # This keeps the "ISS" vs "ISS DEB" (PAYLOAD vs DEBRIS) case.
            if type_a == type_b:
                continue
            
        filtered.append((norad_a, norad_b, dist))
        
    return filtered

def get_positions_snapshot(propagated_states: dict, timestamp_index: int) -> dict:
    """
    Filters global propagated timelines tracking frames to partition spatial arrays
    at specific chronological timeline checkpoints.
    Returns `{norad_id: (x, y, z)}`.
    """
    snapshot = {}
    for norad_id, trajectory in propagated_states.items():
        if 0 <= timestamp_index < len(trajectory):
            pt = trajectory[timestamp_index]
            if "x" in pt and "y" in pt and "z" in pt:
                snapshot[norad_id] = (pt["x"], pt["y"], pt["z"])
    return snapshot