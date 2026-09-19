import { create } from 'zustand'

const normalizeConjunction = (c) => {
  if (!c) return c;
  const id = c.event_id || c.id || "";
  const satA = c.satA || {
    id: c.norad_id_a || "",
    name: c.name_a || "UNKNOWN",
    type: c.object_type_a || "PAYLOAD",
    owner: c.owner_a || c.owner || "UNKNOWN",
    noradId: c.norad_id_a || "",
    apogee: c.altitude_km || 500,
    perigee: c.altitude_km || 500,
    inclination: 0,
    velocity: 7.5,
    lat: 0,
    lng: 0,
    alt: c.altitude_km || 500
  };
  const satB = c.satB || {
    id: c.norad_id_b || "",
    name: c.name_b || "UNKNOWN",
    type: c.object_type_b || "DEBRIS",
    owner: c.owner_b || "USSPACECOM",
    noradId: c.norad_id_b || "",
    apogee: c.altitude_km || 500,
    perigee: c.altitude_km || 500,
    inclination: 0,
    velocity: 7.5,
    lat: 0,
    lng: 0,
    alt: c.altitude_km || 500
  };
  const tca = c.tca_utc || c.tca || new Date().toISOString();
  const missDistance = c.miss_distance_km !== undefined ? c.miss_distance_km * 1000 : (c.missDistance !== undefined ? c.missDistance : 1000);
  const miss_distance_km = c.miss_distance_km !== undefined ? c.miss_distance_km : (missDistance / 1000);
  const riskProbability = c.collision_probability_chan !== undefined ? c.collision_probability_chan : (c.riskProbability !== undefined ? c.riskProbability : 1e-5);
  const collision_probability_chan = riskProbability;
  
  // Normalize STATUS ('CRITICAL' | 'HIGH' | 'MEDIUM' | 'RESOLVED')
  let status = c.status || 'MEDIUM';
  if (c.resolved || c.status === 'RESOLVED') {
    status = 'RESOLVED';
  } else if (c.risk_level === 'CRITICAL' || c.status === 'CRITICAL') {
    status = 'CRITICAL';
  } else if (c.risk_level === 'HIGH' || c.status === 'HIGH') {
    status = 'HIGH';
  } else if (c.risk_level === 'MEDIUM' || c.status === 'MEDIUM') {
    status = 'MEDIUM';
  }

  const risk_level = status === 'RESOLVED' ? (c.risk_level || 'MEDIUM') : status;
  const resolved = c.resolved !== undefined ? c.resolved : (status === 'RESOLVED');
  const risk_score = c.risk_score !== undefined ? c.risk_score : (status === 'CRITICAL' ? 85 : status === 'HIGH' ? 62 : status === 'MEDIUM' ? 35 : 5);

  return {
    ...c,
    id,
    event_id: id,
    satA,
    satB,
    tca,
    tca_utc: tca,
    missDistance,
    miss_distance_km,
    riskProbability,
    collision_probability_chan,
    status,
    risk_level,
    resolved,
    risk_score,
    relativeVelocity: c.relative_velocity_kmps !== undefined ? c.relative_velocity_kmps : (c.relativeVelocity !== undefined ? c.relativeVelocity : 7.5),
    relative_velocity_kmps: c.relative_velocity_kmps !== undefined ? c.relative_velocity_kmps : (c.relativeVelocity !== undefined ? c.relativeVelocity : 7.5),
    suggestedManeuver: c.suggestedManeuver || `Maneuver ΔV = 0.5 m/s`
  };
};

export const useConjunctionStore = create((set, get) => ({
  conjunctions: [],
  activeConjunctionId: null,
  lastUpdated: null,
  loading: false,
  filter: 'ALL',
  sortBy: 'TCA',

  setConjunctions: (conjunctions) => {
    let list = [];
    if (Array.isArray(conjunctions)) {
      list = conjunctions;
    } else if (conjunctions && Array.isArray(conjunctions.conjunctions)) {
      list = conjunctions.conjunctions;
    } else if (conjunctions && typeof conjunctions === 'object') {
      const possibleList = conjunctions.data || conjunctions.items || conjunctions.results;
      if (Array.isArray(possibleList)) {
        list = possibleList;
      }
    }
    const normalized = list.map(normalizeConjunction);
    set({ 
      conjunctions: normalized, 
      lastUpdated: new Date().toISOString() 
    });
  },
  
  addConjunction: (conjunction) => set((state) => {
    const fresh = normalizeConjunction(conjunction);
    const list = Array.isArray(state.conjunctions) ? state.conjunctions : [];
    return { 
      conjunctions: [fresh, ...list],
      lastUpdated: new Date().toISOString()
    };
  }),
  
  updateConjunction: (updated) => set((state) => {
    const list = Array.isArray(state.conjunctions) ? state.conjunctions : [];
    return {
      conjunctions: list.map((c) => {
        if (c.event_id === updated.event_id || c.id === updated.id || (updated.event_id && c.event_id === updated.event_id)) {
          return normalizeConjunction({ ...c, ...updated });
        }
        return c;
      }),
      lastUpdated: new Date().toISOString()
    };
  }),
  
  setActiveConjunction: (id) => set({ activeConjunctionId: id }),
  setLoading: (loading) => set({ loading }),
  setFilter: (filter) => set({ filter }),
  setSortBy: (sortBy) => set({ sortBy }),
  
  getFilteredConjunctions: () => {
    const { conjunctions, filter, sortBy } = get()
    let result = Array.isArray(conjunctions) ? [...conjunctions] : []

    // Apply Filter
    if (filter === 'CRITICAL') {
      result = result.filter((c) => c.status === 'CRITICAL' || c.risk_level === 'CRITICAL')
    } else if (filter === 'HIGH') {
      result = result.filter((c) => c.status === 'CRITICAL' || c.risk_level === 'CRITICAL' || c.status === 'HIGH' || c.risk_level === 'HIGH')
    } else if (filter === 'MEDIUM') {
      result = result.filter((c) => c.status === 'MEDIUM' || c.risk_level === 'MEDIUM')
    } else if (filter === 'ACTIVE') {
      result = result.filter((c) => !c.resolved)
    } else if (filter === 'RESOLVED') {
      result = result.filter((c) => c.resolved)
    }

    // Apply Sort
    if (sortBy === 'TCA') {
      result.sort((a, b) => new Date(a.tca || 0).getTime() - new Date(b.tca || 0).getTime())
    } else if (sortBy === 'RISK_SCORE' || sortBy === 'RISK') {
      result.sort((a, b) => (b.riskProbability || 0) - (a.riskProbability || 0))
    } else if (sortBy === 'MISS_DISTANCE') {
      result.sort((a, b) => (a.missDistance || 0) - (b.missDistance || 0))
    }

    return result
  }
}))
