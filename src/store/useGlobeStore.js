import { create } from 'zustand'

export const useGlobeStore = create((set) => ({
  selectedSatelliteId: null,
  selectedConjunctionId: null,
  highlightedOrbitIds: [],
  cameraPosition: [0, 0, 3],
  isAnimatingManeuver: false,
  showOrbits: true,
  showSatellites: true,
  showConjunctions: true,
  satellitePositions: [],
  cinematicMode: false,
  satelliteSpeed: 1.0,

  setSelectedSatellite: (id) => set({ selectedSatelliteId: id }),
  setSelectedConjunction: (id) => set({ selectedConjunctionId: id }),
  setHighlightedOrbits: (ids) => set({ highlightedOrbitIds: ids }),
  startManeuverAnimation: () => set({ isAnimatingManeuver: true }),
  stopManeuverAnimation: () => set({ isAnimatingManeuver: false }),
  toggleOrbits: (show) => set((state) => ({ showOrbits: show !== undefined ? show : !state.showOrbits })),
  toggleSatellites: (show) => set((state) => ({ showSatellites: show !== undefined ? show : !state.showSatellites })),
  toggleConjunctions: (show) => set((state) => ({ showConjunctions: show !== undefined ? show : !state.showConjunctions })),
  setSatellitePositions: (positions) => set({ satellitePositions: positions || [] }),
  setCinematicMode: (mode) => set({ cinematicMode: mode }),
  setSatelliteSpeed: (speed) => set({ satelliteSpeed: speed }),
}))
