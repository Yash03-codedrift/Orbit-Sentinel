use std::collections::HashMap;
use std::io::{self, Read};
use chrono::{DateTime, Utc, TimeZone, Datelike, Timelike};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct SatInput {
    norad_id: String,
    name: String,
    tle1: String,
    tle2: String,
}

#[derive(Deserialize)]
struct Input {
    satellites: Vec<SatInput>,
    timestamps: Vec<String>,
}

#[derive(Serialize)]
struct PositionRecord {
    t: String,
    x: f64,
    y: f64,
    z: f64,
    vx: f64,
    vy: f64,
    vz: f64,
    lat: f64,
    lon: f64,
    alt: f64,
    speed_kmps: f64,
}

#[derive(Serialize)]
struct Output {
    results: HashMap<String, Vec<PositionRecord>>,
}

// 1949-12-31 UTC is the reference point.
pub fn datetime_to_epoch_days(dt: &DateTime<Utc>) -> f64 {
    let ref_date = Utc.with_ymd_and_hms(1949, 12, 31, 0, 0, 0).unwrap();
    let duration = dt.signed_duration_since(ref_date);
    duration.num_seconds() as f64 / 86400.0 + (duration.num_milliseconds() % 1000) as f64 / 86400_000.0
}

fn datetime_to_jd(dt: &DateTime<Utc>) -> f64 {
    let year = dt.year() as f64;
    let month = dt.month() as f64;
    let mut y = year;
    let mut m = month;
    if month <= 2.0 {
        y -= 1.0;
        m += 12.0;
    }
    let a = (y / 100.0).floor();
    let b = 2.0 - a + (a / 4.0).floor();
    
    // convert day + time fractional
    let day = dt.day() as f64 + (dt.hour() as f64 + dt.minute() as f64 / 60.0 + dt.second() as f64 / 3600.0 + dt.nanosecond() as f64 / 3_600_000_000_000.0) / 24.0;
    
    let jd = (365.25 * (y + 4716.0)).floor() + (30.6001 * (m + 1.0)).floor() + day + b - 1524.5;
    jd
}

fn gast(dt: &DateTime<Utc>) -> f64 {
    let jd = datetime_to_jd(dt);
    let jd0 = 2451545.0;
    let mut gmst_degrees = 280.46061837 + 360.98564736629 * (jd - jd0);
    gmst_degrees %= 360.0;
    if gmst_degrees < 0.0 {
        gmst_degrees += 360.0;
    }
    let gmst_rad = gmst_degrees.to_radians();
    let t = (jd - 2451545.0) / 36525.0;
    let omega = (125.04452 - 1934.13626 * t).to_radians();
    let asc_node = (280.4665 + 36000.7698 * t).to_radians();
    let eq_eq = (0.00029 * omega.sin() + 0.00002 * (2.0 * asc_node).sin()).to_radians();
    let mut gast_rad = (gmst_rad + eq_eq) % (2.0 * std::f64::consts::PI);
    if gast_rad < 0.0 {
        gast_rad += 2.0 * std::f64::consts::PI;
    }
    gast_rad
}

fn eci_to_ecef(x: f64, y: f64, z: f64, gast_rad: f64) -> (f64, f64, f64) {
    let c = gast_rad.cos();
    let s = gast_rad.sin();
    let x_ecef = c * x + s * y;
    let y_ecef = -s * x + c * y;
    let z_ecef = z;
    (x_ecef, y_ecef, z_ecef)
}

fn ecef_to_geodetic(x_km: f64, y_km: f64, z_km: f64) -> (f64, f64, f64) {
    let a = 6378.137;
    let f = 1.0 / 298.257223563;
    let b = a * (1.0 - f);
    let e_sq = 2.0 * f - f * f;
    let e_prime_sq = e_sq / (1.0 - e_sq);
    
    let p = (x_km * x_km + y_km * y_km).sqrt();
    
    let (lat_deg, lon_deg, alt_km) = if p < 1e-10 {
        let lat_rad = if z_km >= 0.0 { std::f64::consts::FRAC_PI_2 } else { -std::f64::consts::FRAC_PI_2 };
        let lon_rad = 0.0;
        let alt_km = z_km.abs() - b;
        (lat_rad.to_degrees(), lon_rad.to_degrees(), alt_km)
    } else {
        let theta = (z_km * a).atan2(p * b);
        let lat_rad = (z_km + e_prime_sq * b * theta.sin().powi(3)).atan2(
            p - e_sq * a * theta.cos().powi(3)
        );
        let lon_rad = y_km.atan2(x_km);
        let n = a / (1.0 - e_sq * lat_rad.sin().sin()).sqrt();
        let alt_km = p / lat_rad.cos() - n;
        (lat_rad.to_degrees(), lon_rad.to_degrees(), alt_km)
    };
    
    (lat_deg, lon_deg, alt_km)
}

fn eci_to_geodetic(x: f64, y: f64, z: f64, gast_rad: f64) -> (f64, f64, f64) {
    let (x_ecef, y_ecef, z_ecef) = eci_to_ecef(x, y, z, gast_rad);
    ecef_to_geodetic(x_ecef, y_ecef, z_ecef)
}

fn parse_timestamp(ts_str: &str) -> Option<DateTime<Utc>> {
    // 1. Try direct parse matching DateTime<Utc>
    if let Ok(dt) = ts_str.parse::<DateTime<Utc>>() {
        return Some(dt);
    }
    // 2. Try parse matching DateTime<FixedOffset>
    if let Ok(dt) = DateTime::parse_from_rfc3339(ts_str) {
        return Some(dt.with_timezone(&Utc));
    }
    // 3. Try with-or-without fractional digits
    let cleaned = ts_str.trim_end_matches('Z');
    for fmt in &["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%.3f", "%Y-%m-%dT%H:%M:%S%.6f", "%Y-%m-%d %H:%M:%S"] {
        if let Ok(naive) = chrono::NaiveDateTime::parse_from_str(cleaned, fmt) {
            #[allow(deprecated)]
            return Some(DateTime::<Utc>::from_utc(naive, Utc));
        }
    }
    None
}

fn main() {
    let mut buffer = String::new();
    if let Err(err) = io::stdin().read_to_string(&mut buffer) {
        eprintln!("Failed to read stdin: {}", err);
        std::process::exit(1);
    }

    let input: Input = match serde_json::from_str(&buffer) {
        Ok(parsed) => parsed,
        Err(err) => {
            eprintln!("Failed to parse input JSON: {}", err);
            std::process::exit(1);
        }
    };

    // Pre-parse timestamps sequentially or in parallel
    let parsed_timestamps: Vec<(String, DateTime<Utc>)> = input
        .timestamps
        .iter()
        .filter_map(|ts| {
            parse_timestamp(ts).map(|dt| (ts.clone(), dt))
        })
        .collect();

    // Use Rayon to propagate all satellites in parallel
    let results: HashMap<String, Vec<PositionRecord>> = input
        .satellites
        .par_iter()
        .filter_map(|sat| {
            let elements = match sgp4::Elements::from_tle(
                Some(&sat.name),
                sat.tle1.as_bytes(),
                sat.tle2.as_bytes(),
            ) {
                Ok(el) => el,
                Err(err) => {
                    eprintln!("Failed to parse TLE for Norad ID {}: {:?}", sat.norad_id, err);
                    return None;
                }
            };

            let constants = match sgp4::Constants::from_elements(&elements) {
                Ok(c) => c,
                Err(err) => {
                    eprintln!("Failed to build SGP4 Constants for Norad ID {}: {:?}", sat.norad_id, err);
                    return None;
                }
            };

            let mut trajectory = Vec::new();
            for (ts_str, dt) in &parsed_timestamps {
                match constants.propagate_from_datetime(*dt) {
                    Ok(prediction) => {
                        let x = prediction.position[0];
                        let y = prediction.position[1];
                        let z = prediction.position[2];
                        let vx = prediction.velocity[0];
                        let vy = prediction.velocity[1];
                        let vz = prediction.velocity[2];

                        let speed = (vx * vx + vy * vy + vz * vz).sqrt();
                        let gast_val = gast(dt);
                        let (lat, lon, alt) = eci_to_geodetic(x, y, z, gast_val);

                        trajectory.push(PositionRecord {
                            t: ts_str.clone(),
                            x,
                            y,
                            z,
                            vx,
                            vy,
                            vz,
                            lat,
                            lon,
                            alt,
                            speed_kmps: speed,
                        });
                    }
                    Err(_) => {
                        // Skip timestep on prediction error silently
                    }
                }
            }

            if trajectory.is_empty() {
                None
            } else {
                Some((sat.norad_id.clone(), trajectory))
            }
        })
        .collect();

    let output = Output { results };
    match serde_json::to_string(&output) {
        Ok(json_str) => {
            println!("{}", json_str);
        }
        Err(err) => {
            eprintln!("Failed to serialize output JSON: {}", err);
            std::process::exit(1);
        }
    }
}
