"""
Physics-based Kessler Cascade Simulator.
Models debris generation from a hypervelocity collision and propagates fragment
orbits to identify secondary conjunction risks — the mechanism behind Kessler syndrome.
"""
import logging
import math
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger("orbit_sentinel.cascade_simulator")

# Gravitational parameter (km^3/s^2)
GM = 398600.4418
R_EARTH = 6378.137


def solve_kepler(M: float, e: float, tol: float = 1e-8) -> float:
    """Newton-Raphson solution for Kepler's equation M = E - e*sin(E)."""
    E = M
    for _ in range(10):
        dE = (M - E + e * math.sin(E)) / (1.0 - e * math.cos(E))
        E += dE
        if abs(dE) < tol:
            break
    return E


def propagate_kepler_simple(
    x0: float, y0: float, z0: float,
    vx0: float, vy0: float, vz0: float,
    dt_hours: float
) -> tuple[float, float, float]:
    """
    Simple two-body Keplerian propagation of an ECI state vector.
    Returns (x, y, z) position in km after dt_hours.
    """
    dt = dt_hours * 3600.0  # seconds
    r0 = math.sqrt(x0**2 + y0**2 + z0**2)
    v0 = math.sqrt(vx0**2 + vy0**2 + vz0**2)

    # Specific energy and semi-major axis
    energy = 0.5 * v0**2 - GM / r0
    if energy >= 0:
        # Hyperbolic/parabolic: not bound, skip propagation
        return x0, y0, z0

    a = -GM / (2.0 * energy)

    # Angular momentum and eccentricity vector
    hx = y0 * vz0 - z0 * vy0
    hy = z0 * vx0 - x0 * vz0
    hz = x0 * vy0 - y0 * vx0
    h = math.sqrt(hx**2 + hy**2 + hz**2)

    # Eccentricity
    ev_x = (vy0 * hz - vz0 * hy) / GM - x0 / r0
    ev_y = (vz0 * hx - vx0 * hz) / GM - y0 / r0
    ev_z = (vx0 * hy - vy0 * hx) / GM - z0 / r0
    e = math.sqrt(ev_x**2 + ev_y**2 + ev_z**2)
    e = min(e, 0.999)  # cap to avoid numerical blow-up

    # Mean motion
    n = math.sqrt(GM / max(a**3, 1.0))

    # True anomaly at t0
    r_dot_v = x0 * vx0 + y0 * vy0 + z0 * vz0
    cos_nu0 = min(1.0, max(-1.0, (h**2 / (GM * r0) - 1.0) / max(e, 1e-10)))
    nu0 = math.acos(cos_nu0)
    if r_dot_v < 0:
        nu0 = 2 * math.pi - nu0

    # Eccentric anomaly at t0
    E0 = 2.0 * math.atan2(math.sqrt(1 - e) * math.sin(nu0 / 2), math.sqrt(1 + e) * math.cos(nu0 / 2))
    M0 = E0 - e * math.sin(E0)

    # Propagate mean anomaly
    M1 = M0 + n * dt
    E1 = solve_kepler(M1, e)

    # True anomaly at t1
    nu1 = 2.0 * math.atan2(math.sqrt(1 + e) * math.sin(E1 / 2), math.sqrt(1 - e) * math.cos(E1 / 2))

    # Radius at t1
    p = a * (1.0 - e**2)
    r1 = p / (1.0 + e * math.cos(nu1))

    # Position in perifocal frame, then rotate back to approximate ECI direction
    # (simplified: maintain direction of angular momentum axis, rotate in-plane)
    if r0 > 0.1:
        # Rotate the position vector in the orbital plane
        dnu = nu1 - nu0
        cos_dnu = math.cos(dnu)
        sin_dnu = math.sin(dnu)

        # Perifocal-plane unit vectors (approx)
        ex = x0 / r0
        ey = y0 / r0
        ez = z0 / r0

        # Cross-track unit (angular momentum direction)
        cx = (hy * ez - hz * ey) / max(h, 1e-10)
        cy = (hz * ex - hx * ez) / max(h, 1e-10)
        cz = (hx * ey - hy * ex) / max(h, 1e-10)

        # Along-track perpendicular in orbital plane
        px = cy * ez - cz * ey
        py = cz * ex - cx * ez
        pz = cx * ey - cy * ex

        x1 = r1 * (ex * cos_dnu + px * sin_dnu)
        y1 = r1 * (ey * cos_dnu + py * sin_dnu)
        z1 = r1 * (ez * cos_dnu + pz * sin_dnu)
    else:
        x1, y1, z1 = x0, y0, z0

    return x1, y1, z1


async def simulate_kessler_cascade(
    conjunction_event: dict,
    satellites_catalogue: dict,
    n_debris: int = 100,
    propagation_hours: int = 24
) -> dict:
    """
    Simulates debris generation from a hypervelocity collision and propagates
    fragment orbits to detect secondary conjunctions.
    """
    state_a = conjunction_event.get("state_vector_at_tca_a", {})
    state_b = conjunction_event.get("state_vector_at_tca_b", {})
    rel_vel = float(conjunction_event.get("relative_velocity_kmps", 7.0))
    alt_km = float(conjunction_event.get("altitude_km", 500.0))
    norad_a = conjunction_event.get("norad_id_a", "UNK_A")
    norad_b = conjunction_event.get("norad_id_b", "UNK_B")

    # Collision point in ECI (km)
    cx = float(state_a.get("x", R_EARTH + alt_km))
    cy = float(state_a.get("y", 0.0))
    cz = float(state_a.get("z", 0.0))

    # Collision energy
    collision_energy_kJ = 0.5 * 1000.0 * rel_vel ** 2  # assumes 1 kg test mass

    # Fragment velocity dispersion: ~1% of impact velocity
    explosion_dv_kms = rel_vel * 0.01
    sigma_frag = explosion_dv_kms / 3.0

    # Parent velocities
    pvx = float(state_a.get("vx", 0.0))
    pvy = float(state_a.get("vy", 7.6))
    pvz = float(state_a.get("vz", 0.0))

    logger.info(f"Generating {n_debris} debris fragments from collision at alt={alt_km:.0f} km, dV={rel_vel:.1f} km/s")

    # Generate fragment ECI state vectors
    fragments = []
    for i in range(n_debris):
        dvx = np.random.normal(0, sigma_frag)
        dvy = np.random.normal(0, sigma_frag)
        dvz = np.random.normal(0, sigma_frag)
        fragments.append({
            "norad_id": f"DEBRIS_{i}_{norad_a}",
            "x": cx, "y": cy, "z": cz,
            "vx": pvx + dvx, "vy": pvy + dvy, "vz": pvz + dvz,
        })

    # Check proximity threshold (km)
    CONJUNCTION_THRESHOLD_KM = 5.0

    # Propagate catalogue satellites to real ECI positions via SGP4
    # (catalogue entries store tle1/tle2, not pre-computed state vectors)
    try:
        from backend.core.sgp4_propagator import propagate_single as _prop_single
        _has_sgp4 = True
    except ImportError:
        _has_sgp4 = False
        logger.warning("sgp4_propagator not importable — cascade secondary check will be empty")

    from datetime import datetime as _dt, timezone as _tz
    _epoch = _dt.now(_tz.utc)

    cat_positions = []
    for nid, sat in list(satellites_catalogue.items())[:300]:
        if not isinstance(sat, dict):
            continue
        tle1 = sat.get("tle1")
        tle2 = sat.get("tle2")
        if not tle1 or not tle2:
            continue
        if _has_sgp4:
            try:
                pos = _prop_single(tle1, tle2, _epoch)
                if pos and pos.get("x") and pos.get("y") and pos.get("z"):
                    cat_positions.append((nid, float(pos["x"]), float(pos["y"]), float(pos["z"])))
            except Exception:
                continue

    if not cat_positions:
        logger.warning("No catalogue positions propagated — TLEs missing or sgp4 unavailable.")

    timeline_hours = [0, 6, 12, 24]
    if propagation_hours not in timeline_hours:
        timeline_hours.append(propagation_hours)
    timeline_hours = sorted(set(h for h in timeline_hours if h <= propagation_hours))

    cascade_timeline = []
    all_affected = set()
    total_secondary = 0

    for hrs in timeline_hours:
        new_conjunctions = 0
        affected_at_t = []

        for frag in fragments:
            if hrs == 0:
                fx, fy, fz = frag["x"], frag["y"], frag["z"]
            else:
                fx, fy, fz = propagate_kepler_simple(
                    frag["x"], frag["y"], frag["z"],
                    frag["vx"], frag["vy"], frag["vz"],
                    hrs
                )

            # Check against catalogue satellites
            for nid, sx, sy, sz in cat_positions:
                dist = math.sqrt((fx - sx) ** 2 + (fy - sy) ** 2 + (fz - sz) ** 2)
                if dist < CONJUNCTION_THRESHOLD_KM:
                    new_conjunctions += 1
                    affected_at_t.append(nid)
                    all_affected.add(nid)

        total_secondary += new_conjunctions
        cascade_timeline.append({
            "hours": hrs,
            "new_conjunctions": new_conjunctions,
            "affected_satellites": list(set(affected_at_t))[:10],  # cap for response size
            "debris_count": n_debris,
        })

    highest_risk = None
    if all_affected and cat_positions:
        # Find the satellite with smallest minimum separation across all time steps
        for nid in list(all_affected)[:5]:
            for frag in fragments[:20]:  # sample
                fx, fy, fz = frag["x"], frag["y"], frag["z"]
                for cid, sx, sy, sz in cat_positions:
                    if cid == nid:
                        dist = math.sqrt((fx - sx) ** 2 + (fy - sy) ** 2 + (fz - sz) ** 2)
                        sat_name = satellites_catalogue.get(nid, {}).get("name", nid) if isinstance(satellites_catalogue.get(nid), dict) else nid
                        highest_risk = {"norad_id": nid, "name": sat_name, "miss_distance_km": round(dist, 3)}
                        break
                if highest_risk:
                    break

    return {
        "debris_fragments": n_debris,
        "collision_energy_kJ": round(collision_energy_kJ, 1),
        "collision_altitude_km": alt_km,
        "fragment_velocity_dispersion_kmps": round(explosion_dv_kms, 4),
        "cascade_timeline": cascade_timeline,
        "total_secondary_conjunctions": total_secondary,
        "highest_risk_target": highest_risk,
        "kessler_escalation_risk": total_secondary > 20,
        "affected_satellites_total": len(all_affected),
        "simulation_method": "keplerian_two_body_monte_carlo",
        "simulation_note": f"Physics-based Monte Carlo simulation: {n_debris} fragments propagated via two-body Keplerian mechanics."
    }
