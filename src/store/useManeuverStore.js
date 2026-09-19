import { create } from 'zustand'

export const useManeuverStore = create((set) => ({
  maneuvers: [],
  activeManeuver: null,
  webhookPayload: null,
  verificationResult: null,
  computing: false,

  setManeuvers: (maneuvers) => set({ maneuvers: maneuvers || [] }),
  setActiveManeuver: (maneuver) => set({ activeManeuver: maneuver }),
  setWebhookPayload: (payload) => set({ webhookPayload: payload }),
  setVerificationResult: (result) => set({ verificationResult: result }),
  setComputing: (computing) => set({ computing }),
  addManeuver: (maneuver) => set((state) => ({ 
    maneuvers: [maneuver, ...state.maneuvers] 
  }))
}))
