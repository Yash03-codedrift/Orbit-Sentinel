import { create } from 'zustand'
import { getRiskThresholds } from '../api/riskConfigApi'

export const useRiskConfigStore = create((set) => ({
  bandsByKey: {},   // { CRITICAL: { min_score, color }, ... }
  bands: [],        // ordered array, highest severity first
  loaded: false,

  hydrate: async () => {
    try {
      const res = await getRiskThresholds()
      const bands = res.bands || []
      const byKey = {}
      bands.forEach((b) => { byKey[b.key] = b })
      set({ bands, bandsByKey: byKey, loaded: true })
    } catch (err) {
      console.error('Failed to load risk bands:', err)
      set({ loaded: true })
    }
  },

  setBands: (bands) => {
    const byKey = {}
    bands.forEach((b) => { byKey[b.key] = b })
    set({ bands, bandsByKey: byKey })
  },
}))