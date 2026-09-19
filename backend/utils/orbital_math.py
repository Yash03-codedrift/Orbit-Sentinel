import numpy as np
try:
    import scipy
except ImportError:
    scipy = None

def compute_altitude(x: float, y: float, z: float) -> float:
    """
    Computes altitude of an object in orbit by subtracting Earth's mean radius
    (defined as 6371.0 km) from the magnitude of the position vector.
    """
    pos_magnitude = np.sqrt(x**2 + y**2 + z**2)
    return float(pos_magnitude - 6371.0)

def compute_orbital_period(a_km: float, mu: float = 398600.4418) -> float:
    """
    Computes Keplerian orbital period in seconds matching:
    T = 2π * sqrt(a³ / μ)
    """
    if a_km <= 0:
        return 0.0
    return float(2.0 * np.pi * np.sqrt((a_km ** 3) / mu))

def compute_vis_viva(r_km: float, a_km: float, mu: float = 398600.4418) -> float:
    """
    Computes orbital velocity (km/s) using the Vis-Viva energy equation.
    v = sqrt(μ * (2/r - 1/a))
    """
    if r_km <= 0 or a_km <= 0:
        return 0.0
    inside = (2.0 / r_km) - (1.0 / a_km)
    if inside < 0:
        inside = 0.0
    return float(np.sqrt(mu * inside))

def chan_collision_probability(
    miss_km: float, 
    sigma_km: float = 1.0, 
    combined_cross_section_m2: float = 20.0
) -> float:
    """
    Computes collision probability using F. Kenneth Chan's analytical formulation for spherical bodies.
    Formula:
    P_c = (A_c / (2π * σ_r * σ_t)) * exp(-0.5 * (miss² / σ²))
    Where combined_cross_section_m2 is converted to km².
    """
    # Convert cross-sectional area of collision from m² to km²
    Ac = combined_cross_section_m2 * 1e-6
    
    if sigma_km <= 0:
        sigma_km = 1e-6
        
    term1 = Ac / (2.0 * np.pi * (sigma_km ** 2))
    exponent = -0.5 * (miss_km ** 2) / (sigma_km ** 2)
    p_c = term1 * np.exp(exponent)
    
    return float(np.clip(p_c, 0.0, 1.0))

def compute_kessler_index(
    active_conjunctions: int, 
    debris_count: int, 
    leo_object_count: int
) -> float:
    """
    Aggregates a generalized status threat risk scoring representing Kessler Cascade conditions.
    Formula:
      base = (debris_count / LEO_object_count) * 100
      score = base * (1 + (active_conjunctions * 0.05))
    Clamped tightly between [0.0, 100.0].
    """
    if leo_object_count <= 0:
        return 0.0
        
    base = (debris_count / leo_object_count) * 100.0
    # Inflate base index score dynamically using current high threat conjunction levels
    multiplier = 1.0 + (active_conjunctions * 0.05)
    score = base * multiplier
    
    return float(np.clip(score, 0.0, 100.0))

def gaussian_delta_v(
    state_vector: list, 
    target_miss_km: float, 
    current_miss_km: float, 
    time_to_tca_s: float
) -> np.ndarray:
    """
    Calculates estimated Delta-V burn velocity vectors (in meters/second) aligned with the in-track orbital direction.
    Formula:
      dv = (target_miss - current_miss) * 1000 / (time_to_tca_s * 0.5)
    Returns: (dv_x, dv_y, dv_z) numpy array matching velocity unit vectors.
    """
    # state_vector: [x, y, z, vx, vy, vz] (velocity components are 3,4,5)
    vx = state_vector[3]
    vy = state_vector[4]
    vz = state_vector[5]
    
    vel = np.array([vx, vy, vz])
    vel_magnitude = np.linalg.norm(vel)
    
    if vel_magnitude < 1e-9:
        velocity_unit_direction = np.array([1.0, 0.0, 0.0])
    else:
        velocity_unit_direction = vel / vel_magnitude
        
    if time_to_tca_s <= 0:
        time_to_tca_s = 1.0  # Safe guard fallback divisor limit
        
    # Calculate scalar delta_V magnitude needed to adjust altitude/trajectory in-track
    dv_magnitude = (target_miss_km - current_miss_km) * 1000.0 / (time_to_tca_s * 0.5)
    
    # Project final delta-V vector along target direction
    dv_vector = dv_magnitude * velocity_unit_direction
    return dv_vector
