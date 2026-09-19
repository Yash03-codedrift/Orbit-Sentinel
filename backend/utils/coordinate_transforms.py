import numpy as np

def eci_to_ecef(x: float, y: float, z: float, gast_rad: float) -> tuple:
    """
    Rotates position components from the Earth-Centered Inertial (ECI) coordinate frame
    to the Earth-Centered Earth-Fixed (ECEF) rotational frame around the Z axis by GAST angle.
    """
    c = np.cos(gast_rad)
    s = np.sin(gast_rad)
    x_ecef = c * x + s * y
    y_ecef = -s * x + c * y
    z_ecef = z
    return (float(x_ecef), float(y_ecef), float(z_ecef))

def ecef_to_geodetic(x_km: float, y_km: float, z_km: float) -> tuple:
    """
    Converts ECEF Cartesian coordinates (in km) to geodetic latitude, longitude, and altitude
    relative to the WGS84 reference ellipsoid using Bowring's method.
    WGS84 Reference ellipsoid: 
      - semi-major axis (a) = 6378.137 km
      - inverse flattening (1/f) = 298.257223563
    Returns: (lat_deg, lon_deg, alt_km)
    """
    a = 6378.137
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e_sq = 2.0 * f - f**2
    e_prime_sq = e_sq / (1.0 - e_sq)
    
    p = np.sqrt(x_km**2 + y_km**2)
    
    if p < 1e-10:  # Handle extreme polar alignment
        lat_rad = np.pi / 2.0 if z_km >= 0 else -np.pi / 2.0
        lon_rad = 0.0
        alt_km = np.abs(z_km) - b
    else:
        theta = np.arctan2(z_km * a, p * b)
        lat_rad = np.arctan2(
            z_km + e_prime_sq * b * (np.sin(theta)**3),
            p - e_sq * a * (np.cos(theta)**3)
        )
        lon_rad = np.arctan2(y_km, x_km)
        N = a / np.sqrt(1.0 - e_sq * np.sin(lat_rad)**2)
        alt_km = p / np.cos(lat_rad) - N
        
    return (float(np.degrees(lat_rad)), float(np.degrees(lon_rad)), float(alt_km))

def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_km: float) -> tuple:
    """
    Inverse transform mapping geodetic parameters relative to the WGS84 ellipsoid
    back down into ECEF coordinates (km).
    """
    a = 6378.137
    f = 1.0 / 298.257223563
    e_sq = 2.0 * f - f**2
    
    lat_rad = np.radians(lat_deg)
    lon_rad = np.radians(lon_deg)
    
    N = a / np.sqrt(1.0 - e_sq * np.sin(lat_rad)**2)
    x = (N + alt_km) * np.cos(lat_rad) * np.cos(lon_rad)
    y = (N + alt_km) * np.cos(lat_rad) * np.sin(lon_rad)
    z = (N * (1.0 - e_sq) + alt_km) * np.sin(lat_rad)
    
    return (float(x), float(y), float(z))

def eci_to_geodetic(x: float, y: float, z: float, gast_rad: float) -> tuple:
    """
    Composite transform piping coordinate vectors structural alignment from
    Inertial (ECI) directly to Geodetic (Lat, Lon, Alt) via intermediate ECEF projections.
    """
    x_ecef, y_ecef, z_ecef = eci_to_ecef(x, y, z, gast_rad)
    return ecef_to_geodetic(x_ecef, y_ecef, z_ecef)

def compute_range(pos_a: tuple, pos_b: tuple) -> float:
    """
    Calculates standard Euclidean Euclidean metric distance displacement between two objects.
    All position components are in kilometers.
    """
    return float(np.sqrt((pos_a[0] - pos_b[0])**2 + (pos_a[1] - pos_b[1])**2 + (pos_a[2] - pos_b[2])**2))

def compute_relative_velocity(vel_a: tuple, vel_b: tuple) -> float:
    """
    Calculates absolute scalar relative velocity velocity difference magnitude between two objects.
    All velocity components are in kilometers/second.
    """
    return float(np.sqrt((vel_a[0] - vel_b[0])**2 + (vel_a[1] - vel_b[1])**2 + (vel_a[2] - vel_b[2])**2))

def keplerian_to_cartesian(
    a_km: float, 
    e: float, 
    i_rad: float, 
    raan_rad: float, 
    argp_rad: float, 
    nu_rad: float, 
    mu: float = 398600.4418
) -> tuple:
    """
    Transforms classical Keplerian orbital orbital parameters to standard Earth-Centered Inertial (ECI) 
    position and velocity state vectors.
    """
    if e >= 1.0:
        e = 0.99999  # Clamp hyperbola/parabola configurations to highly eccentric closed bounds
        
    p = a_km * (1.0 - e**2)
    if p < 1e-6:
        p = 1e-6
        
    r = p / (1.0 + e * np.cos(nu_rad))
    
    # Standard position vector coordinates in perifocal PQW frame
    r_pqw = np.array([r * np.cos(nu_rad), r * np.sin(nu_rad), 0.0])
    
    # Velocity parameters in perifocal PQW frame
    v_pqw = np.array([
        -np.sqrt(mu / p) * np.sin(nu_rad),
        np.sqrt(mu / p) * (e + np.cos(nu_rad)),
        0.0
    ])
    
    # Rotation angles projection matrices setup (Right-to-Left chain equivalent of: Rz(-RAAN) * Rx(-Inc) * Rz(-Argp))
    c_raan = np.cos(raan_rad)
    s_raan = np.sin(raan_rad)
    c_ap = np.cos(argp_rad)
    s_ap = np.sin(argp_rad)
    c_i = np.cos(i_rad)
    s_i = np.sin(i_rad)
    
    # Transformation matrix
    rot = np.array([
        [
            c_raan * c_ap - s_raan * s_ap * c_i,
            -c_raan * s_ap - s_raan * c_ap * c_i,
            s_raan * s_i
        ],
        [
            s_raan * c_ap + c_raan * s_ap * c_i,
            -s_raan * s_ap + c_raan * c_ap * c_i,
            -c_raan * s_i
        ],
        [
            s_ap * s_i,
            c_ap * s_i,
            c_i
        ]
    ])
    
    pos_eci = rot.dot(r_pqw)
    vel_eci = rot.dot(v_pqw)
    
    return (
        float(pos_eci[0]), float(pos_eci[1]), float(pos_eci[2]),
        float(vel_eci[0]), float(vel_eci[1]), float(vel_eci[2])
    )

def cartesian_to_keplerian(
    x: float, 
    y: float, 
    z: float, 
    vx: float, 
    vy: float, 
    vz: float, 
    mu: float = 398600.4418
) -> tuple:
    """
    Transforms standard Earth-Centered Inertial (ECI) position and velocity state vectors
    into classical Keplerian elements: semi-major axis (a_km), eccentricity (e), inclination (i_rad),
    RAAN (raan_rad), argument of perigee (argp_rad), and true anomaly (nu_rad).
    """
    r_vec = np.array([x, y, z])
    v_vec = np.array([vx, vy, vz])
    
    r = np.linalg.norm(r_vec)
    v = np.linalg.norm(v_vec)
    
    if r < 1e-9:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        
    h_vec = np.cross(r_vec, v_vec)
    h = np.linalg.norm(h_vec)
    
    # Ascending node vector direction
    n_vec = np.array([-h_vec[1], h_vec[0], 0.0])
    n = np.linalg.norm(n_vec)
    
    # Eccentricity vector
    e_vec = ((v**2 - mu/r) * r_vec - np.dot(r_vec, v_vec) * v_vec) / mu
    e = np.linalg.norm(e_vec)
    
    # Specific orbital mechanical energy calculation
    energy = (v**2) / 2.0 - mu/r
    if np.abs(energy) > 1e-9:
        a_km = -mu / (2.0 * energy)
    else:
        a_km = float('inf')
        
    # Inclination
    if h > 1e-9:
        cos_i = h_vec[2] / h
        cos_i = np.clip(cos_i, -1.0, 1.0)
        i_rad = np.arccos(cos_i)
    else:
        i_rad = 0.0
        
    # Right Ascension of Ascending Node (RAAN)
    if n > 1e-9:
        cos_raan = n_vec[0] / n
        cos_raan = np.clip(cos_raan, -1.0, 1.0)
        raan_rad = np.arccos(cos_raan)
        if n_vec[1] < 0:
            raan_rad = 2.0 * np.pi - raan_rad
    else:
        raan_rad = 0.0
        
    # Argument of Perigee
    if n > 1e-9 and e > 1e-9:
        cos_argp = np.dot(n_vec, e_vec) / (n * e)
        cos_argp = np.clip(cos_argp, -1.0, 1.0)
        argp_rad = np.arccos(cos_argp)
        if e_vec[2] < 0:
            argp_rad = 2.0 * np.pi - argp_rad
    else:
        argp_rad = 0.0
        
    # True Anomaly (nu)
    if e > 1e-9:
        cos_nu = np.dot(e_vec, r_vec) / (e * r)
        cos_nu = np.clip(cos_nu, -1.0, 1.0)
        nu_rad = np.arccos(cos_nu)
        if np.dot(r_vec, v_vec) < 0:
            nu_rad = 2.0 * np.pi - nu_rad
    else:
        if n > 1e-9:
            # Fall back to circular inclined trajectory true argument of latitude
            cos_lat = np.dot(n_vec, r_vec) / (n * r)
            cos_lat = np.clip(cos_lat, -1.0, 1.0)
            nu_rad = np.arccos(cos_lat)
            if r_vec[2] < 0:
                nu_rad = 2.0 * np.pi - nu_rad
        else:
            # Equatorial circular trajectory polar true longitude mapping
            nu_rad = np.arctan2(r_vec[1], r_vec[0])
            if nu_rad < 0:
                nu_rad += 2 * np.pi
                
    return (float(a_km), float(e), float(i_rad), float(raan_rad), float(argp_rad), float(nu_rad))
