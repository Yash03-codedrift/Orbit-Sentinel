import math
from datetime import datetime, timezone, timedelta
from typing import Union

def utc_now() -> datetime:
    """
    Returns the current UTC datetime with tzinfo set to UTC.
    """
    return datetime.now(timezone.utc)

def iso_to_datetime(iso_str: str) -> datetime:
    """
    Parses an ISO 8601 string to a datetime object with UTC timezone.
    Handles 'Z' suffix replacement for python <= 3.10 compatibility.
    """
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(iso_str)
    except ValueError:
        # Fallback parsing format
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S.%f")
    
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def datetime_to_iso(dt: datetime) -> str:
    """
    Converts a datetime object to an ISO 8601 string representation.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Ensure it ends with 'Z' instead of '+00:00'
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def time_until(dt_utc: datetime) -> timedelta:
    """
    Returns the timedelta from the current moment to the specified target UTC time.
    """
    now = utc_now()
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc - now

def format_relative_time(dt_utc: datetime) -> str:
    """
    Formats the given UTC date relative to current time in a human-friendly format.
    E.g. "3h 22m", "in 45s", "2 days ago".
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        
    diff = dt_utc - utc_now()
    seconds = diff.total_seconds()
    abs_seconds = abs(seconds)
    
    if abs_seconds < 60:
        val = f"{int(abs_seconds)}s"
        return f"in {val}" if seconds > 0 else f"{val} ago"
    
    minutes = abs_seconds / 60
    if minutes < 60:
        val = f"{int(minutes)}m"
        return f"in {val}" if seconds > 0 else f"{val} ago"
        
    hours = minutes / 60
    if hours < 24:
        val = f"{int(hours)}h {int(minutes % 60)}m"
        return f"in {val}" if seconds > 0 else f"{val} ago"
        
    days = hours / 24
    val = f"{int(days)}d" if days < 30 else f"{int(days / 30)}mo"
    return f"in {val}" if seconds > 0 else f"{val} ago"

def datetime_to_jd(dt_utc: datetime) -> float:
    """
    Converts a datetime object to Julian Date.
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        
    year = dt_utc.year
    month = dt_utc.month
    day = dt_utc.day + (dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0 + dt_utc.microsecond / 3600000000.0) / 24.0
    
    if month <= 2:
        year -= 1
        month += 12
        
    # Gregorian calendar check offset
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    
    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
    return jd

def gast(dt_utc: datetime) -> float:
    """
    Calculates Greenwich Apparent Sidereal Time (GAST) in radians using the J2000 epoch formula.
    θ_GMST = 280.46061837 + 360.98564736629 × (JD - 2451545.0) degrees.
    Wraps the return value tightly in the range [0, 2π].
    """
    jd = datetime_to_jd(dt_utc)
    jd0 = 2451545.0 # J2000 Epoch reference day
    
    # Calculate Greenwich Mean Sidereal Time in degrees
    gmst_degrees = 280.46061837 + 360.98564736629 * (jd - jd0)
    
    # Wrap to 360 degrees
    gmst_degrees = gmst_degrees % 360.0
    
    # Convert GMST basic degrees to radians
    gmst_rad = math.radians(gmst_degrees)
    
    # Equation of the equinoxes approximation (using standard mean obliquity of ecliptic + longitude of ascending node)
    t = (jd - 2451545.0) / 36525.0
    omega = math.radians(125.04452 - 1934.13626 * t)
    asc_node = math.radians(280.4665 + 36000.7698 * t)
    eq_eq = math.radians(0.00029 * math.sin(omega) + 0.00002 * math.sin(2 * asc_node))
    
    # GAST = GMST + Equation of Equinoxes
    gast_rad = (gmst_rad + eq_eq) % (2 * math.pi)
    if gast_rad < 0:
        gast_rad += 2 * math.pi
        
    return gast_rad
