import { create } from 'zustand'

const normalizeManeuver = (maneuver) => {
  if (!maneuver || typeof maneuver !== 'object') return maneuver

  const dvVector = Array.isArray(maneuver.delta_v_vector)
    ? maneuver.delta_v_vector
    : Array.isArray(maneuver.delta_v_vector_ms)
      ? maneuver.delta_v_vector_ms
      : Array.isArray(maneuver.deltaVVector)
        ? maneuver.deltaVVector
        : [0, 0, 0]

  const magnitude =
    maneuver.computed_delta_v_magnitude_mps ??
    maneuver.delta_v_magnitude_ms ??
    maneuver.deltaVMagnitude ??
    (Array.isArray(dvVector) && dvVector.length >= 3
      ? Math.sqrt(dvVector.reduce((sum, val) => sum + (Number(val) || 0) ** 2, 0))
      : 0)

  const targetName =
    maneuver.target_satellite?.name ??
    maneuver.satellite_name ??
    maneuver.targetSatellite?.name ??
    'TARGET SATELLITE'

  const fuelCostKg = maneuver.fuel_cost_kg ?? maneuver.estimated_fuel_cost_kg ?? 0
  const fuelCostPct = maneuver.fuel_cost_pct ?? (fuelCostKg > 0 ? Math.min(100, fuelCostKg * 10) : 0)
  const confidence = maneuver.confidence ?? maneuver.confidence_score ?? 0

  return {
    ...maneuver,
    target_satellite: maneuver.target_satellite ?? { name: targetName },
    targetSatellite: maneuver.targetSatellite ?? { name: targetName },
    delta_v_vector: dvVector.map((v) => Number(v) || 0),
    deltaVVector: dvVector.map((v) => Number(v) || 0),
    computed_delta_v_magnitude_mps: Number(magnitude) || 0,
    deltaVMagnitude: Number(magnitude) || 0,
    fuel_cost_kg: Number(fuelCostKg) || 0,
    fuel_cost_pct: Number(fuelCostPct) || 0,
    estimated_fuel_cost_kg: Number(fuelCostKg) || 0,
    confidence: Number(confidence) || 0,
    confidence_score: Number(confidence) || 0,
    satellite_name: maneuver.satellite_name ?? targetName,
    burn_duration_seconds: maneuver.burn_duration_seconds ?? maneuver.burnDuration ?? 0,
    post_maneuver_miss_km: maneuver.post_maneuver_miss_km ?? maneuver.postBurnMissKm ?? 0,
    pre_maneuver_miss_km: maneuver.pre_maneuver_miss_km ?? maneuver.preBurnMissKm ?? maneuver.miss_distance_km ?? 0
  }
}

export const useManeuverStore = create((set) => ({
  maneuvers: [],
  activeManeuver: null,
  webhookPayload: null,
  verificationResult: null,
  computing: false,

  setManeuvers: (maneuvers) => set({ maneuvers: (maneuvers || []).map(normalizeManeuver) }),
  setActiveManeuver: (maneuver) => set({ activeManeuver: normalizeManeuver(maneuver) }),
  setWebhookPayload: (payload) => set({ webhookPayload: payload }),
  setVerificationResult: (result) => set({ verificationResult: result }),
  setComputing: (computing) => set({ computing }),
  addManeuver: (maneuver) => set((state) => ({
    maneuvers: [normalizeManeuver(maneuver), ...state.maneuvers]
  }))
}))
