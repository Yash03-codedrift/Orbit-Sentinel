import { Satellite, ConjunctionEvent, AuditLog, MLModelStats, ManeuverConfig } from './types';

export const INITIAL_SATELLITES: Satellite[] = [
  {
    id: "SAT-LINK-01",
    name: "STARLINK-3211",
    noradId: "48212",
    type: "PAYLOAD",
    owner: "SpaceX",
    apogee: 552,
    perigee: 548,
    inclination: 53.2,
    velocity: 7.58,
    lat: 34.0522,
    lng: -118.2437,
    alt: 550,
    color: "#38bdf8"
  },
  {
    id: "SAT-LINK-02",
    name: "STARLINK-1904",
    noradId: "44910",
    type: "PAYLOAD",
    owner: "SpaceX",
    apogee: 549,
    perigee: 547,
    inclination: 53.0,
    velocity: 7.59,
    lat: 51.5074,
    lng: -0.1278,
    alt: 548,
    color: "#38bdf8"
  },
  {
    id: "SAT-ISS",
    name: "ISS (ZARYA)",
    noradId: "25544",
    type: "PAYLOAD",
    owner: "NASA/Roscosmos",
    apogee: 422,
    perigee: 418,
    inclination: 51.64,
    velocity: 7.66,
    lat: -23.5505,
    lng: -46.6333,
    alt: 420,
    color: "#22c55e"
  },
  {
    id: "SAT-SENTINEL",
    name: "SENTINEL-6",
    noradId: "46984",
    type: "PAYLOAD",
    owner: "ESA",
    apogee: 1338,
    perigee: 1334,
    inclination: 66.04,
    velocity: 7.12,
    lat: 35.6762,
    lng: 139.6503,
    alt: 1336,
    color: "#a855f7"
  },
  {
    id: "SAT-DEBRIS-01",
    name: "COSMOS 2251 DEBRIS",
    noradId: "36114",
    type: "DEBRIS",
    owner: "USSPACECOM",
    apogee: 790,
    perigee: 760,
    inclination: 74.0,
    velocity: 7.48,
    lat: -33.8688,
    lng: 151.2093,
    alt: 775,
    color: "#ef4444"
  },
  {
    id: "SAT-DEBRIS-02",
    name: "FENGYUN-1C FRAGMENT",
    noradId: "31154",
    type: "DEBRIS",
    owner: "USSPACECOM",
    apogee: 850,
    perigee: 810,
    inclination: 98.6,
    velocity: 7.41,
    lat: 40.7128,
    lng: -74.0060,
    alt: 830,
    color: "#ef4444"
  },
  {
    id: "SAT-DEBRIS-03",
    name: "ENVISAT BOOM DEBRIS",
    noradId: "38921",
    type: "DEBRIS",
    owner: "ESA",
    apogee: 785,
    perigee: 781,
    inclination: 98.54,
    velocity: 7.44,
    lat: 48.8566,
    lng: 2.3522,
    alt: 783,
    color: "#f97316"
  },
  {
    id: "SAT-ONEWEB",
    name: "ONEWEB-0243",
    noradId: "47521",
    type: "PAYLOAD",
    owner: "OneWeb",
    apogee: 1202,
    perigee: 1198,
    inclination: 87.9,
    velocity: 7.19,
    lat: -1.2921,
    lng: 36.8219,
    alt: 1200,
    color: "#eab308"
  }
];

export const INITIAL_CONJUNCTIONS: ConjunctionEvent[] = [
  {
    id: "CONJ-2026-001",
    satA: INITIAL_SATELLITES[0], // STARLINK-3211
    satB: INITIAL_SATELLITES[4], // COSMOS 2251 DEBRIS
    tca: "2026-06-08T04:12:33Z",
    missDistance: 342, // meters
    riskProbability: 3.82e-4, // CRITICAL
    relativeVelocity: 14.2, // km/s
    status: "CRITICAL",
    suggestedManeuver: "Prograde impulse ΔV_x = +0.45 m/s",
  },
  {
    id: "CONJ-2026-002",
    satA: INITIAL_SATELLITES[2], // ISS
    satB: INITIAL_SATELLITES[6], // ENVISAT BOOM DEBRIS
    tca: "2026-06-08T11:45:02Z",
    missDistance: 782, // meters
    riskProbability: 7.41e-5, // HIGH
    relativeVelocity: 11.8, // km/s
    status: "HIGH",
    suggestedManeuver: "Radial Burn ΔV_z = -0.22 m/s",
  },
  {
    id: "CONJ-2026-003",
    satA: INITIAL_SATELLITES[1], // STARLINK-1904
    satB: INITIAL_SATELLITES[5], // FENGYUN-1C FRAGMENT
    tca: "2026-06-09T02:08:14Z",
    missDistance: 1420, // meters
    riskProbability: 1.25e-5, // MEDIUM
    relativeVelocity: 13.9, // km/s
    status: "MEDIUM",
    suggestedManeuver: "Retrograde impulse ΔV_x = -0.15 m/s",
  },
  {
    id: "CONJ-2026-004",
    satA: INITIAL_SATELLITES[3], // SENTINEL-6
    satB: INITIAL_SATELLITES[7], // ONEWEB-0243
    tca: "2026-06-09T18:30:00Z",
    missDistance: 2950, // meters
    riskProbability: 8.92e-6, // MEDIUM
    relativeVelocity: 5.6, // km/s
    status: "MEDIUM",
    suggestedManeuver: "None required - monitoring orbital envelope",
  },
  {
    id: "CONJ-2026-005",
    satA: INITIAL_SATELLITES[2], // ISS
    satB: INITIAL_SATELLITES[4], // COSMOS 2251 DEBRIS
    tca: "2026-06-07T08:15:22Z", // in past relative to 2026-06-07T14:54Z
    missDistance: 4210, // meters
    riskProbability: 4.81e-8,
    relativeVelocity: 14.8,
    status: "RESOLVED",
    actionTaken: "De-escalated - post-conjunction window elapsed safely."
  }
];

export const INITIAL_ML_MODELS: MLModelStats[] = [
  {
    modelType: "ANN",
    accuracy: 94.82,
    lastTrained: "2026-06-07T06:00:00Z",
    trainingSamples: 142050,
    predictionConfidence: 91.5,
    status: "OPTIMAL"
  },
  {
    modelType: "LSTM",
    accuracy: 97.41,
    lastTrained: "2026-06-07T00:30:00Z",
    trainingSamples: 89300,
    predictionConfidence: 96.2,
    status: "OPTIMAL"
  },
  {
    modelType: "MARL",
    accuracy: 91.13,
    lastTrained: "2026-06-06T18:00:00Z",
    trainingSamples: 245000,
    predictionConfidence: 89.4,
    status: "STALE"
  }
];

export const INITIAL_AUDIT_LOGS: AuditLog[] = [
  {
    id: "LOG-101",
    timestamp: "2026-06-07T14:48:12Z",
    ip: "10.142.0.4",
    message: "TLE feed synchronized successfully with Space-Track API. Retrieved 4,812 objects.",
    severity: "INFO"
  },
  {
    id: "LOG-102",
    timestamp: "2026-06-07T14:49:05Z",
    ip: "10.142.12.82",
    message: "SGP4 batch propagation initialized on 8 worker-threads. Window: 72h ahead.",
    severity: "INFO"
  },
  {
    id: "LOG-103",
    timestamp: "2026-06-07T14:50:00Z",
    ip: "10.142.12.82",
    message: "CRITICAL hazard detected: Starlink STARLINK-3211 is projected to pass 342m from COSMOS 2251 DEBRIS.",
    severity: "CRITICAL"
  },
  {
    id: "LOG-104",
    timestamp: "2026-06-07T14:51:24Z",
    ip: "127.0.0.1",
    message: "ANN collision-risk validation executed. Adjusted risk ratio to 3.82e-4.",
    severity: "ALERT"
  },
  {
    id: "LOG-105",
    timestamp: "2026-06-07T14:52:19Z",
    ip: "10.142.0.5",
    message: "Webhook transmission test skipped. Waiting for operator maneuver payload instruction.",
    severity: "WARNING"
  }
];
