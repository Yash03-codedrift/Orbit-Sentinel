"""
Conjunction screening for Orbit Sentinel.

Why this module exists
----------------------
The old broad phase looked at positions every 25 minutes inside a 5 km ball. Two objects that
cross at 7-15 km/s move thousands of km between looks, so it could only ever "see" pairs that
fly together for 25+ minutes (formation flyers) and it missed real crossings.

What this version does
----------------------
1. Keeps every 5-minute frame and looks at the WHOLE interval between two frames, not just the
   frames themselves. Inside an interval the motion is rebuilt with cubic Hermite interpolation
   (positions AND velocities from SGP4), which is accurate to a few hundred metres at 5-minute
   spacing (linear interpolation is off by tens of km).
2. Uses rigorous distance bounds so no pair that can come within the threshold is ever thrown
   away (cheap tests first, finer tests only on the few pairs that survive).
3. Finds the exact time and distance of closest approach on the same curve, and returns state
   vectors that agree with that miss distance.
"""
import logging
import time
import warnings
from datetime import timedelta
from typing import Any, Dict, List, Sequence, Set, Tuple

import numpy as np

from backend.core.spatial_index import filter_same_constellation
from backend.utils.coordinate_transforms import eci_to_geodetic
from backend.utils.time_utils import datetime_to_iso, gast

logger = logging.getLogger("orbit_sentinel.screening")

A_REL_MAX_KMPS2 = 0.02   # bound on the relative acceleration of two LEO objects (about 2 x g)
MARGIN_KM = 25.0         # extra slack in the cheap tests so interpolation error can never cause a miss
ACCEPT_SLACK_KM = 1.0    # a pair is kept if its refined miss distance is below threshold + this
EARTH_RADIUS_KM = 6378.137
MAX_ORBITAL_SPEED_KMPS = 12.0   # anything faster than this near Earth is a corrupt state, not an orbit
PROGRESS_EVERY = 100            # log progress every N five-minute intervals


# ── helpers ────────────────────────────────────────────────────────────────

def _series_to_arrays(series: Sequence[Dict[str, Any]], iso_index: Dict[str, int], k: int):
    """
    Turns one satellite's list of state dicts into (k,3) position and velocity arrays.
    If the propagator dropped some timestamps (SGP4 error) the missing rows stay NaN, so every
    row still lines up with the timestamp grid.
    """
    P = np.full((k, 3), np.nan)
    V = np.full((k, 3), np.nan)
    if len(series) == k:
        arr = np.array([[p["x"], p["y"], p["z"], p["vx"], p["vy"], p["vz"]] for p in series], dtype=float)
        P[:] = arr[:, :3]
        V[:] = arr[:, 3:]
        return P, V
    for p in series:
        idx = iso_index.get(p.get("t"))
        if idx is not None:
            P[idx] = (p["x"], p["y"], p["z"])
            V[idx] = (p["vx"], p["vy"], p["vz"])
    return P, V


def _hermite(p0, v0, p1, v1, s, h):
    """
    Cubic Hermite interpolation between two states h seconds apart.
    s is the fraction of the interval (0..1). Returns position (km) and velocity (km/s).
    """
    s2 = s * s
    s3 = s2 * s
    pos = ((2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * h * v0
           + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * h * v1)
    vel = ((6 * s2 - 6 * s) * p0 + (3 * s2 - 4 * s + 1) * h * v0
           + (-6 * s2 + 6 * s) * p1 + (3 * s2 - 2 * s) * h * v1) / h
    return pos, vel


def _pair_dist(Pt: np.ndarray, I: np.ndarray, J: np.ndarray) -> np.ndarray:
    d = Pt[I] - Pt[J]
    return np.sqrt(np.einsum("ij,ij->i", d, d))


def _sample_min(p0, v0, p1, v1, h, s_grid):
    """Closest sampled distance along the relative Hermite path, and where it happened."""
    pos, _ = _hermite(p0[:, None, :], v0[:, None, :], p1[:, None, :], v1[:, None, :],
                      s_grid[None, :, None], h)
    d = np.sqrt(np.einsum("ijk,ijk->ij", pos, pos))
    arg = np.argmin(d, axis=1)
    return d[np.arange(d.shape[0]), arg], arg


def _refine_min(p0, v0, p1, v1, h, s_center, half_width):
    """
    Sub-sample refinement: 9 samples around s_center, then a parabola through the best three
    (the squared distance of a fast fly-by is almost exactly a parabola in time).
    """
    offs = np.linspace(-half_width, half_width, 9)
    s = np.clip(s_center[:, None] + offs[None, :], 0.0, 1.0)
    pos, _ = _hermite(p0[:, None, :], v0[:, None, :], p1[:, None, :], v1[:, None, :], s[:, :, None], h)
    d2 = np.einsum("ijk,ijk->ij", pos, pos)
    m = d2.shape[0]
    j = np.clip(np.argmin(d2, axis=1), 1, 7)
    rows = np.arange(m)
    y0, y1, y2 = d2[rows, j - 1], d2[rows, j], d2[rows, j + 1]
    denom = y0 - 2.0 * y1 + y2
    with np.errstate(divide="ignore", invalid="ignore"):
        vertex = y1 - (y0 - y2) ** 2 / (8.0 * denom)
    vertex = np.where(denom > 0, vertex, np.minimum(np.minimum(y0, y1), y2))
    vertex = np.minimum(vertex, d2.min(axis=1))  # never report worse than the best sample
    return np.sqrt(np.maximum(vertex, 0.0))


# ── broad phase ────────────────────────────────────────────────────────────

def find_candidate_pairs(
    propagated_states: Dict[str, List[Dict[str, Any]]],
    timestamps: Sequence,
    threshold_km: float,
    satellites_catalogue: Dict[str, Dict[str, Any]],
) -> Set[Tuple[str, str]]:
    """
    Returns {(norad_a, norad_b)} for every pair whose closest approach inside the
    propagation window is (or may be) below threshold_km. CPU heavy: call it in a thread.
    """
    t_start = time.monotonic()
    k = len(timestamps)
    if not propagated_states or k < 2:
        return set()

    h = (timestamps[1] - timestamps[0]).total_seconds()
    iso_index = {datetime_to_iso(ts): i for i, ts in enumerate(timestamps)}
    ids = list(propagated_states.keys())
    n = len(ids)

    P = np.empty((k, n, 3))
    V = np.empty((k, n, 3))
    for j, nid in enumerate(ids):
        p, v = _series_to_arrays(propagated_states[nid], iso_index, k)
        P[:, j, :] = p
        V[:, j, :] = v

    # Corrupt states (underground, or faster than any bound orbit) would wreck the distance
    # bounds below, so they are dropped. A dropped frame simply means "no data" for that object.
    R = np.linalg.norm(P, axis=2)
    S = np.linalg.norm(V, axis=2)
    with np.errstate(invalid="ignore"):
        bad = (R < EARTH_RADIUS_KM) | (S > MAX_ORBITAL_SPEED_KMPS)
    if bad.any():
        logger.warning("Screening: ignoring %d corrupt propagated states", int(bad.sum()))
        P[bad] = np.nan
        V[bad] = np.nan
        R[bad] = np.nan
        S[bad] = np.nan

    # Static filter: two objects can only meet if their altitude ranges overlap.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r_lo = np.nanmin(R, axis=0)
        r_hi = np.nanmax(R, axis=0)
        v_obj = np.nanmax(S, axis=0)
    pad = threshold_km + MARGIN_KM
    with np.errstate(invalid="ignore"):
        overlap = (r_lo[:, None] <= r_hi[None, :] + pad) & (r_lo[None, :] <= r_hi[:, None] + pad)
    I, J = np.nonzero(np.triu(overlap, 1))
    total_pairs = n * (n - 1) // 2
    if I.size == 0:
        return set()

    # Drop pairs that would be discarded anyway (same constellation, debris vs debris) BEFORE the
    # expensive loop, using the very same rule as the rest of the system.
    n_band = int(I.size)
    index_of = {nid: i for i, nid in enumerate(ids)}
    kept = filter_same_constellation([(ids[a], ids[b], 0.0) for a, b in zip(I.tolist(), J.tolist())],
                                     satellites_catalogue)
    if not kept:
        return set()
    I = np.fromiter((index_of[a] for a, _, _ in kept), dtype=np.int64, count=len(kept))
    J = np.fromiter((index_of[b] for _, b, _ in kept), dtype=np.int64, count=len(kept))
    del kept

    # Per-pair bound on relative speed (rigorous: |va - vb| <= |va| + |vb|, plus a little slack).
    with np.errstate(invalid="ignore"):
        vrel = 1.05 * (v_obj[I] + v_obj[J]) + A_REL_MAX_KMPS2 * h / 2.0
    sum_cut = 2.0 * pad + vrel * h                     # test 0: endpoints of one interval
    accept = threshold_km + ACCEPT_SLACK_KM
    s1 = np.linspace(0.0, 1.0, 9)
    s2 = np.linspace(0.0, 1.0, 61)
    logger.info("Screening: %d objects, %d pairs share an altitude band, %d left after constellation "
                "filter (of %d total)", n, n_band, I.size, total_pairs)

    best: Dict[Tuple[int, int], float] = {}
    d_prev = _pair_dist(P[0], I, J)
    for t in range(k - 1):
        d_next = _pair_dist(P[t + 1], I, J)
        with np.errstate(invalid="ignore"):
            keep = np.nonzero(d_prev + d_next <= sum_cut)[0]
        d_prev = d_next
        if t % PROGRESS_EVERY == 0:
            logger.info("Screening progress: interval %d of %d, %.0fs elapsed, %d candidate pairs so far",
                        t, k - 1, time.monotonic() - t_start, len(best))
        if keep.size == 0:
            continue

        Ik, Jk, vk = I[keep], J[keep], vrel[keep]
        p0 = P[t][Ik] - P[t][Jk]
        v0 = V[t][Ik] - V[t][Jk]
        p1 = P[t + 1][Ik] - P[t + 1][Jk]
        v1 = V[t + 1][Ik] - V[t + 1][Jk]

        d1, _ = _sample_min(p0, v0, p1, v1, h, s1)            # test 1: 9 samples per interval
        with np.errstate(invalid="ignore"):
            q = np.nonzero(d1 <= pad + vk * (h / 16.0))[0]
        if q.size == 0:
            continue
        Ik, Jk, vk, p0, v0, p1, v1 = Ik[q], Jk[q], vk[q], p0[q], v0[q], p1[q], v1[q]

        d2, arg = _sample_min(p0, v0, p1, v1, h, s2)          # test 2: 61 samples per interval
        with np.errstate(invalid="ignore"):
            q = np.nonzero(d2 <= pad + vk * (h / 120.0))[0]
        if q.size == 0:
            continue
        Ik, Jk, p0, v0, p1, v1, arg = Ik[q], Jk[q], p0[q], v0[q], p1[q], v1[q], arg[q]

        est = _refine_min(p0, v0, p1, v1, h, s2[arg], 1.0 / 60.0)
        hit = est <= accept
        for a, b, e in zip(Ik[hit], Jk[hit], est[hit]):
            key = (int(a), int(b))
            if e < best.get(key, 1e18):
                best[key] = float(e)

    result = {tuple(sorted((ids[a], ids[b]))) for (a, b) in best}
    logger.info(
        "Screening finished: %d candidate pairs in %.1fs", len(result), time.monotonic() - t_start,
    )
    return result


# ── narrow phase ───────────────────────────────────────────────────────────

def _hermite_at(P: np.ndarray, V: np.ndarray, t_sec: np.ndarray, h: float):
    """Position and velocity of one object at arbitrary times (seconds from the first timestamp)."""
    k = P.shape[0]
    idx = np.clip(np.floor(t_sec / h).astype(int), 0, k - 2)
    s = (t_sec / h - idx)[:, None]
    return _hermite(P[idx], V[idx], P[idx + 1], V[idx + 1], s, h)


def _state_dict(pos: np.ndarray, vel: np.ndarray, when) -> Dict[str, float]:
    x, y, z = (float(c) for c in pos)
    vx, vy, vz = (float(c) for c in vel)
    try:
        lat, lon, alt = eci_to_geodetic(x, y, z, gast(when))
    except Exception:
        lat, lon, alt = 0.0, 0.0, float(np.sqrt(x * x + y * y + z * z) - EARTH_RADIUS_KM)
    return {"x": x, "y": y, "z": z, "vx": vx, "vy": vy, "vz": vz,
            "lat": float(lat), "lon": float(lon), "alt": float(alt)}


def find_tca_between_pair(positions_a, positions_b, timestamps):
    """
    Exact time and distance of closest approach for one pair over the whole window.
    Same call signature as the old function: returns (tca_datetime, miss_km, state_a, state_b).
    """
    k = len(timestamps)
    if k < 2:
        raise ValueError("need at least two timestamps")
    h = (timestamps[1] - timestamps[0]).total_seconds()
    iso_index = {datetime_to_iso(ts): i for i, ts in enumerate(timestamps)}
    Pa, Va = _series_to_arrays(positions_a, iso_index, k)
    Pb, Vb = _series_to_arrays(positions_b, iso_index, k)

    p, v = Pa - Pb, Va - Vb
    ok = np.isfinite(p).all(axis=1) & np.isfinite(v).all(axis=1)
    ok_int = ok[:-1] & ok[1:]
    if not ok_int.any():
        raise ValueError("no interval with valid states for both objects")

    # 1. every interval: 61 samples (5 s apart). A fast crossing can sit up to ~45 km away from
    #    the nearest sample, so several encounters may look alike here. Refine every interval that
    #    is close to the best one and pick the true winner after refinement.
    s = np.linspace(0.0, 1.0, 61)
    p0, v0, p1, v1 = p[:-1], v[:-1], p[1:], v[1:]
    dmin, arg = _sample_min(p0, v0, p1, v1, h, s)
    dmin = np.where(ok_int, dmin, np.inf)
    cand = np.nonzero(dmin <= dmin.min() + 100.0)[0]
    est = _refine_min(p0[cand], v0[cand], p1[cand], v1[cand], h, s[arg[cand]], 1.0 / 60.0)
    best = int(cand[int(np.argmin(est))])
    t_center = (best + s[arg[best]]) * h

    # 2. fine: 0.25 s grid over +-30 s (the two intervals around the best sample)
    t_max = (k - 1) * h
    grid = np.clip(t_center + np.linspace(-30.0, 30.0, 241), 0.0, t_max)
    pa, _ = _hermite_at(Pa, Va, grid, h)
    pb, _ = _hermite_at(Pb, Vb, grid, h)
    dd = np.einsum("ij,ij->i", pa - pb, pa - pb)
    g = int(np.nanargmin(dd)) if np.isfinite(dd).any() else 120

    # 3. parabola through the best three samples for sub-grid accuracy
    t_star = float(grid[g])
    if 0 < g < len(grid) - 1 and np.isfinite(dd[g - 1:g + 2]).all():
        y0, y1, y2 = dd[g - 1], dd[g], dd[g + 1]
        denom = y0 - 2.0 * y1 + y2
        if denom > 0:
            delta = float(np.clip(0.5 * (y0 - y2) / denom, -1.0, 1.0))
            t_star = float(grid[g] + delta * (grid[1] - grid[0]))
    t_star = float(np.clip(t_star, 0.0, t_max))

    # 4. states at the refined time; the miss distance is measured between exactly these states
    tt = np.array([t_star])
    pos_a, vel_a = _hermite_at(Pa, Va, tt, h)
    pos_b, vel_b = _hermite_at(Pb, Vb, tt, h)
    if not (np.isfinite(pos_a).all() and np.isfinite(pos_b).all()):
        raise ValueError("non-finite state at closest approach")
    miss_km = float(np.linalg.norm(pos_a[0] - pos_b[0]))
    when = timestamps[0] + timedelta(seconds=t_star)
    return when, miss_km, _state_dict(pos_a[0], vel_a[0], when), _state_dict(pos_b[0], vel_b[0], when)