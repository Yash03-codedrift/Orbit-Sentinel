export interface Satellite {
  id: string;
  name: string;
  noradId: string;
  type: 'PAYLOAD' | 'ROCKET_BODY' | 'DEBRIS';
  owner: string; // e.g. "SpaceX", "ESA", "NASA", "USSPACECOM", "ISRO"
  apogee: number; // km
  perigee: number; // km
  inclination: number; // degrees
  velocity: number; // km/s
  lat: number;
  lng: number;
  alt: number; // km
  color?: string;
}

export interface ConjunctionEvent {
  id: string;
  satA: Satellite;
  satB: Satellite;
  tca: string; // Time of Closest Approach (ISO String)
  missDistance: number; // in meters or km
  riskProbability: number; // e.g. 1.42e-4
  relativeVelocity: number; // km/s
  status: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'RESOLVED';
  actionTaken?: string;
  suggestedManeuver?: string;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  ip: string;
  message: string;
  severity: 'INFO' | 'WARNING' | 'ALERT' | 'CRITICAL';
}

export interface ManeuverConfig {
  id: string;
  satelliteId: string;
  satelliteName: string;
  burnDuration: number; // seconds
  deltaVx: number; // m/s
  deltaVy: number; // m/s
  deltaVz: number; // m/s
  burnTime: string;
  estimatedRiskPostBurn: number;
  status: 'PENDING' | 'EXECUTED' | 'FAILED' | 'DOWNLOADED';
}

export interface MLModelStats {
  modelType: 'ANN' | 'LSTM' | 'MARL';
  accuracy: number;
  lastTrained: string;
  trainingSamples: number;
  predictionConfidence: number;
  status: 'OPTIMAL' | 'RETRAINING' | 'STALE';
  epochProgress?: number;
}
