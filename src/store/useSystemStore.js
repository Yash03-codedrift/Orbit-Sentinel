import { create } from 'zustand'

export const useSystemStore = create((set) => ({
  systemStatus: 'CONNECTING',
  tleStatus: {
    last_pull: null,
    object_count: 0,
    next_pull_minutes: 10
  },
  schedulerStatus: 'UNKNOWN',
  kesslerIndex: 0,
  totalObjects: 0,
  activeConjunctionCount: 0,
  wsConnected: false,
  demoMode: false,
  lastSweepDurationS: null,
  lastSweepSatelliteCount: 0,

  setSystemStatus: (status) => set({ systemStatus: status }),
  setTleStatus: (status) => set((state) => ({ tleStatus: { ...state.tleStatus, ...status } })),
  setKesslerIndex: (index) => set({ kesslerIndex: index }),
  setTotalObjects: (count) => set({ totalObjects: count }),
  setActiveConjunctionCount: (count) => set({ activeConjunctionCount: count }),
  setWsConnected: (connected) => set({ wsConnected: connected }),
  setDemoMode: (demo) => set({ demoMode: demo }),
  setLastSweep: (durationS, satelliteCount) => set({ lastSweepDurationS: durationS, lastSweepSatelliteCount: satelliteCount }),
  
  updateFromHealth: (healthData) => {
    if (!healthData || typeof healthData !== 'object' || Array.isArray(healthData)) return
    console.log('Health data received:', healthData)
    set({
      tleStatus: {
        last_pull: healthData.last_tle_pull || healthData.last_pull_time || healthData.last_pull,
        object_count: healthData.total_objects_tracked || 0,
        next_pull_minutes: healthData.next_scheduled_pull ?? 10
      },
      schedulerStatus: healthData.scheduler_status || 'UNKNOWN',
      totalObjects: healthData.total_objects_tracked || 0,
      activeConjunctionCount: healthData.active_conjunctions || 0,
      systemStatus: healthData.status === 'SENTINEL_ACTIVE' ? 'ACTIVE' : 'ERROR'
    })
  }
}))
