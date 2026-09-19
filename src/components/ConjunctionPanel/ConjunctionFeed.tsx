import React, { useEffect, useState } from 'react';
import { useConjunctionStore } from '../../store/useConjunctionStore';
import { useGlobeStore } from '../../store/useGlobeStore';
import { formatDistanceToNow } from 'date-fns';
import ConjunctionCard from './ConjunctionCard';
import ConjunctionDetail from './ConjunctionDetail';
import { Sparkles, ArrowRightLeft, ShieldAlert, AlertTriangle } from 'lucide-react';

export default function ConjunctionFeed() {
  const conjunctions = useConjunctionStore((s) => s.conjunctions);
  const filter = useConjunctionStore((s) => s.filter);
  const sortBy = useConjunctionStore((s) => s.sortBy);
  const setFilter = useConjunctionStore((s) => s.setFilter);
  const setSortBy = useConjunctionStore((s) => s.setSortBy);
  const loading = useConjunctionStore((s) => s.loading);
  const lastUpdated = useConjunctionStore((s) => s.lastUpdated);
  const activeId = useConjunctionStore((s) => s.activeConjunctionId);
  const setActiveConjunction = useConjunctionStore((s) => s.setActiveConjunction);
  const getFilteredConjunctions = useConjunctionStore((s) => s.getFilteredConjunctions);

  // Sync to globe store
  const setSelectedConjunctionGlobe = useGlobeStore((s) => s.setSelectedConjunction);

  // Derived filtered & sorted list from store action
  const list = getFilteredConjunctions() || [];

  // Active status count calculation (not resolved)
  const activeCount = conjunctions.filter((c: any) => !c.resolved).length;
  let activeCountColor = 'text-emerald-400';
  if (activeCount > 5) {
    activeCountColor = 'text-red-500';
  } else if (activeCount > 0) {
    activeCountColor = 'text-amber-500';
  }

  // Handle active card selection
  const handleSelectCard = (id: string) => {
    // If clicking already selected card, toggle off; otherwise select
    const nextId = activeId === id ? null : id;
    setActiveConjunction(nextId);
    setSelectedConjunctionGlobe(nextId);
  };

  const handleCloseDetail = () => {
    setActiveConjunction(null);
    setSelectedConjunctionGlobe(null);
  };

  const handleCloseKeepSelection = () => {
    // Close panel but keep the conjunction selected so ConjunctionHighlight renders on globe
    setActiveConjunction(null);
    // intentionally do NOT clear globe selection
  };

  // State to force tick of updated distance to now
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 10000);
    return () => clearInterval(interval);
  }, []);

  // Format relative time last updated
  const getRelativeLastUpdated = () => {
    if (!lastUpdated) return 'Never';
    try {
      return formatDistanceToNow(new Date(lastUpdated)) + ' ago';
    } catch (_) {
      return 'Never';
    }
  };

  return (
    <div className="relative flex flex-col h-full bg-[#05070f] divide-y divide-cyan-950/25 select-none overflow-hidden">
      
      {/* Header section */}
      <div className="p-3 bg-[#080d1a]/55 flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono tracking-wider font-extrabold text-cyan-400 uppercase select-none">
            CONJUNCTION FEED
          </span>
          <span id="active_count_tag" className={`text-[9px] font-bold font-mono tracking-wide px-1.5 py-0.5 rounded bg-slate-950 border border-cyan-950/20 ${activeCountColor}`}>
            {activeCount} ACTIVE
          </span>
        </div>

        {/* Filter chips and Sort inline */}
        <div className="flex items-center justify-between gap-2 mt-1 select-none">
          {/* Filter Chips row */}
          <div className="flex flex-wrap gap-1">
            {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'] as const).map((level) => {
              const isActive = filter === level;
              return (
                <button
                  key={level}
                  id={`chip_filter_${level}`}
                  onClick={() => setFilter(level)}
                  className={`px-1.5 py-0.5 rounded text-[8.5px] font-bold font-mono tracking-tighter transition-all ${
                    isActive
                      ? 'bg-cyan-500 text-slate-950 border border-cyan-400'
                      : 'bg-slate-950/60 text-slate-500 border border-transparent hover:text-slate-300'
                  }`}
                >
                  {level}
                </button>
              );
            })}
          </div>

          {/* Sort selection dropdown */}
          <select
            id="feed_sort_dropdown"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="text-[9.5px] font-mono font-semibold bg-slate-950 border border-cyan-950/45 rounded-md px-1.5 py-1 text-cyan-400 focus:outline-none cursor-pointer tracking-wider"
          >
            <option value="TCA">By TCA</option>
            <option value="RISK">By Risk</option>
            <option value="MISS_DISTANCE">By Miss Distance</option>
          </select>
        </div>
      </div>

      {/* List section with scroll */}
      <div className="flex-1 overflow-y-auto p-2.5 max-h-[300px] md:max-h-none scrollbar-thin">
        {loading ? (
          /* Show 3 skeleton cards */
          <div className="space-y-2">
            {[1, 2, 3].map((num) => (
              <div 
                key={num} 
                className="w-full h-[62px] bg-[#0f1629]/50 border-l-4 border-slate-800 rounded animate-pulse px-3 py-2 flex flex-col gap-2"
              >
                <div className="h-2.5 bg-slate-800 rounded w-2/3" />
                <div className="h-1.5 bg-slate-800 rounded w-1/2" />
                <div className="h-1 bg-slate-800 rounded w-1/3" />
              </div>
            ))}
          </div>
        ) : list.length === 0 ? (
          /* Empty Active state */
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <span className="text-2xl select-now text-emerald-400 mb-2">✔️</span>
            <span className="text-[10px] uppercase font-bold tracking-wider font-mono text-slate-400">
              NO ACTIVE CONJUNCTIONS
            </span>
            <span className="text-[8px] font-mono text-slate-600 mt-1 uppercase">
              All space lanes clear in tracked zone
            </span>
          </div>
        ) : (
          /* Rendered Card Stack */
          list.map((conj: any) => (
            <ConjunctionCard
              key={conj.event_id}
              conjunction={conj}
              isSelected={activeId === conj.event_id}
              onClick={handleSelectCard}
            />
          ))
        )}
      </div>

      {/* Footer log timestamp indicator */}
      <div className="p-2 px-3 bg-[#04060c] border-t border-cyan-950/20 flex items-center justify-between text-[8px] font-mono text-slate-500 uppercase shrink-0">
        <span>SGP-4 Propagator Sync</span>
        <span>Last updated: {getRelativeLastUpdated()}</span>
      </div>

      {/* Slide-over Overlay for Conjunction Details */}
      {activeId && (
        <ConjunctionDetail eventId={activeId} onClose={handleCloseDetail} onCloseKeepSelection={handleCloseKeepSelection} />
      )}

    </div>
  );
}
