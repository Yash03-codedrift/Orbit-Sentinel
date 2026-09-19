import React, { useState, useEffect } from 'react';
import { useSystemStore } from '../store/useSystemStore';
import { triggerTleRefresh, getTleStatus } from '../api/tleApi';
import { getRecentManeuvers } from '../api/maneuverApi';
import KesslerMeter from './Dashboard/KesslerMeter';
import RiskConfigPanel from './RiskConfigPanel';
import { Radio, Shield, RefreshCw, Maximize2, Minimize2, Settings } from 'lucide-react';

interface StatsBarProps {
  systemRisk?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  onAddLog: (msg: string, severity: 'INFO' | 'WARNING' | 'ALERT' | 'CRITICAL') => void;
}

export default function StatsBar({ onAddLog }: StatsBarProps) {
  const wsConnected = useSystemStore((s) => s.wsConnected);
  const totalObjects = useSystemStore((s) => s.totalObjects);
  const activeConjunctionCount = useSystemStore((s) => s.activeConjunctionCount);
  const tleStatus = useSystemStore((s) => s.tleStatus);
  const systemStatus = useSystemStore((s) => s.systemStatus);
  const kesslerIndex = useSystemStore((s) => s.kesslerIndex);
  const setKesslerIndex = useSystemStore((s) => s.setKesslerIndex);
  const setTleStatus = useSystemStore((s) => s.setTleStatus);
  const setTleStatusRef = React.useRef(setTleStatus);
  React.useEffect(() => { setTleStatusRef.current = setTleStatus; }, [setTleStatus]);

  // HTTP fallback: poll KRI from analytics if WebSocket hasn't set it
  React.useEffect(() => {
    if (kesslerIndex > 0) return; // WS already has a live value
    const poll = async () => {
      try {
        const res = await fetch('/api/analytics/kri');
        if (res.ok) {
          const d = await res.json();
          if (d?.kessler_index !== undefined) setKesslerIndex(d.kessler_index);
        }
      } catch (_) {}
    };
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, [kesslerIndex, setKesslerIndex]);
  const lastSweepDurationS = useSystemStore((s) => s.lastSweepDurationS);
  const lastSweepSatelliteCount = useSystemStore((s) => s.lastSweepSatelliteCount);

  const [refreshing, setRefreshing] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showRiskConfig, setShowRiskConfig] = useState(false);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };
  const [maneuversCount, setManeuversCount] = useState(0);
  const [ticker, setTicker] = useState(0);

  // Poll recent maneuvers to count how many there are today
  useEffect(() => {
    let active = true;

    const fetchManeuvers = async () => {
      try {
        const list = await getRecentManeuvers(100);
        if (active && Array.isArray(list)) {
          // Count maneuvers today or total active maneuvers computed
          setManeuversCount(list.length);
        }
      } catch (err) {
        console.error('Failed to query maneuvers count feed:', err);
      }
    };

    fetchManeuvers();
    const interval = setInterval(fetchManeuvers, 45000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Update timer distance representation ticker every 10s
  useEffect(() => {
    const id = setInterval(() => {
      setTicker((t) => t + 1);
    }, 10000);
    return () => clearInterval(id);
  }, []);

  // Animated counter for tracks
  const [displayTrackedCount, setDisplayTrackedCount] = useState(0);
  useEffect(() => {
    let isMounted = true;
    const start = displayTrackedCount;
    const end = totalObjects || 0;
    if (start === end) return;

    const duration = 650;
    const startTime = Date.now();

    const tick = () => {
      if (!isMounted) return;
      const now = Date.now();
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const nextValue = Math.floor(start + (end - start) * progress);

      setDisplayTrackedCount(nextValue);

      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    };

    requestAnimationFrame(tick);

    return () => {
      isMounted = false;
    };
  }, [totalObjects]);

  // Handle human-readable distance time representation for TLE last sync
  const getTleStatusLabelAndColor = () => {
    const lastPull = tleStatus?.last_pull;
    if (!lastPull) {
      return { text: 'NEVER', color: 'text-red-500' };
    }

    try {
      const past = new Date(lastPull).getTime();
      const diffMs = Date.now() - past;
      if (isNaN(diffMs) || diffMs < 0) {
        return { text: 'Just now', color: 'text-emerald-400' };
      }

      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);

      let text = '';
      if (diffMins < 1) {
        text = 'Just now';
      } else if (diffMins < 60) {
        text = `${diffMins}m ago`;
      } else if (diffHours < 24) {
        text = `${diffHours}h ${diffMins % 60}m ago`;
      } else {
        const days = Math.floor(diffHours / 24);
        text = `${days}d ago`;
      }

      let color = 'text-red-500';
      if (diffMins < 15) {
        color = 'text-emerald-400';
      } else if (diffMins < 30) {
        color = 'text-amber-400';
      }

      return { text, color };
    } catch (e) {
      return { text: 'NEVER', color: 'text-red-500' };
    }
  };

  const { text: TleLabel, color: TleColorClass } = getTleStatusLabelAndColor();

  // Handle System Status Mapping
  const getSystemStatusLabelAndColor = () => {
    if (systemStatus === 'ACTIVE' || systemStatus === 'SENTINEL_ACTIVE') {
      return { label: 'SENTINEL ACTIVE', color: 'text-emerald-400 font-bold' };
    }
    if (systemStatus === 'CONNECTING' || systemStatus === 'DEGRADED') {
      return { label: 'DEGRADED', color: 'text-amber-400 font-bold' };
    }
    return { label: 'OFFLINE', color: 'text-red-500 font-bold animate-pulse' };
  };

  const systemStatusObj = getSystemStatusLabelAndColor();

  // Handle active conjunction count text color mapping
  const getActiveConjunctionColor = () => {
    if (activeConjunctionCount === 0) return 'text-emerald-400';
    if (activeConjunctionCount <= 5) return 'text-amber-400';
    return 'text-red-500';
  };

  // Callback to force TLE updates
  const handleForceRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    onAddLog("TLE synchronizer triggered manually. Fetching from CelesTrak...", "INFO");

    try {
      await triggerTleRefresh();
      onAddLog("TLE ingestion started. Polling for completion...", "INFO");

      // Poll every 4s up to 10 attempts (40s total)
      let freshStatus = null;
      for (let attempt = 0; attempt < 10; attempt++) {
        await new Promise((res) => setTimeout(res, 4000));
        try {
          const s = await getTleStatus() as any;
          if (s && (s.last_pull_time || s.last_pull)) {
            freshStatus = s;
            break;
          }
        } catch (_) {}
      }

      if (freshStatus) {
        setTleStatusRef.current({
          last_pull: freshStatus.last_pull_time || freshStatus.last_pull || new Date().toISOString(),
          object_count: freshStatus.object_count || 0,
          next_pull_minutes: freshStatus.next_scheduled_pull || 10,
        });
        onAddLog(`TLE sync complete. ${freshStatus.object_count || 0} objects tracked.`, "INFO");
      } else {
        setTleStatusRef.current({ last_pull: new Date().toISOString() });
        onAddLog("TLE refresh triggered. Ingestion running in background.", "INFO");
      }
    } catch (err) {
      console.error(err);
      onAddLog("TLE sync failed. Check backend is running on port 8000.", "WARNING");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div 
      id="top_stats_bar" 
      className="w-full h-14 min-h-[56px] bg-[#0a0f1e] border-b border-[#1a2340] flex items-center justify-between px-4 select-none"
    >
      {/* Left side: branding and WS heartbeats */}
      <div className="flex items-center gap-3">
        <div className="relative flex items-center shrink-0">
          <div className="w-8 h-8 rounded-lg bg-cyan-400/10 border border-cyan-400/60 flex items-center justify-center text-cyan-400">
            <Shield className="w-4 h-4" />
          </div>
          {/* Pulsing indicator when websocket is live */}
          <span 
            id="ws_pulse_node"
            className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full border border-slate-950 ${
              wsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
            }`} 
          />
        </div>

        <div className="flex flex-col">
          <span className="font-mono text-xs font-black tracking-widest text-cyan-400 flex items-center gap-1.5">
            ORBIT SENTINEL
            <span className="text-[7px] font-mono font-bold text-slate-500 bg-slate-950 border border-cyan-950/40 rounded px-1">V1.5</span>
          </span>
          <span className="text-[8px] font-mono text-slate-500 font-medium tracking-tight uppercase hidden sm:block">
            Autonomous Space Traffic Regulator
          </span>
        </div>
      </div>

      {/* Center stats grid (flex row, gap-8) */}
      <div className="hidden md:flex items-center gap-8 px-4 font-mono select-none">
        {/* Stat 1: OBJECTS TRACKED */}
        <div className="flex flex-col text-left">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider font-semibold">OBJECTS TRACKED</span>
          <span id="tracker_objects_count" className="text-xs font-semibold text-white tracking-tight">
            {displayTrackedCount.toLocaleString()}
          </span>
        </div>

        {/* Stat 2: ACTIVE CONJUNCTIONS */}
        <div className="flex flex-col text-left">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider font-semibold">ACTIVE CONJUNCTIONS</span>
          <span id="active_conjunctions_count" className={`text-xs font-semibold tracking-tight ${getActiveConjunctionColor()}`}>
            {activeConjunctionCount}
          </span>
        </div>

        {/* Stat 3: MANEUVERS TODAY */}
        <div className="flex flex-col text-left">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider font-semibold">MANEUVERS TODAY</span>
          <span id="maneuvers_today_count" className="text-xs font-semibold text-cyan-400 tracking-tight">
            {maneuversCount}
          </span>
        </div>

        {/* Stat 4: LAST TLE REFRESH */}
        <div className="flex flex-col text-left">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider font-semibold">LAST TLE REFRESH</span>
          <span id="last_tle_refresh_lbl" className={`text-xs font-semibold tracking-tight ${TleColorClass}`}>
            {TleLabel}
          </span>
        </div>

        {/* Stat 5: SYSTEM STATUS */}
        <div className="flex flex-col text-left">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider font-semibold">SYSTEM STATUS</span>
          <span id="system_status_indicator" className={`text-xs font-semibold tracking-tight uppercase ${systemStatusObj.color}`}>
            {systemStatusObj.label}
          </span>
        </div>

        {/* Stat 6: LAST SWEEP */}
        <div className="flex flex-col text-left">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider font-semibold">LAST SWEEP</span>
          <span className="text-xs font-semibold text-cyan-300 tracking-tight">
            {lastSweepDurationS !== null
              ? `${lastSweepDurationS}s · ${lastSweepSatelliteCount.toLocaleString()} obj`
              : <span className="text-slate-500 animate-pulse">SCANNING…</span>
            }
          </span>
        </div>
      </div>

      {/* Right side: Compact Kessler index meter & Quick refresh control trigger */}
      <div className="flex items-center gap-4 shrink-0">
        
        {/* Compact Meter */}
        <KesslerMeter index={kesslerIndex} showFull={false} />

        <div className="h-6 w-px bg-cyan-950/30" />

        <button
          id="btn_open_risk_config"
          onClick={() => setShowRiskConfig(true)}
          className="px-3 py-1.5 border rounded border-cyan-800/35 bg-[#0a0f1e] hover:bg-slate-900 transition-all font-mono text-[9px] font-bold text-cyan-400 uppercase flex items-center gap-1.5 cursor-pointer hover:shadow-[0_0_8px_rgba(34,211,238,0.1)] active:scale-95"
        >
          <Settings className="w-3 h-3" />
          <span>RISK CONFIG</span>
        </button>

        <button
          id="btn_fullscreen_app"
          onClick={toggleFullscreen}
          className="px-3 py-1.5 border rounded border-cyan-800/35 bg-[#0a0f1e] hover:bg-slate-900 transition-all font-mono text-[9px] font-bold text-cyan-400 uppercase flex items-center gap-1.5 cursor-pointer hover:shadow-[0_0_8px_rgba(34,211,238,0.1)] active:scale-95"
        >
          {isFullscreen ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
          <span>{isFullscreen ? 'EXIT FULL' : 'FULLSCREEN'}</span>
        </button>

        <button
          id="btn_stats_bar_refresh"
          onClick={handleForceRefresh}
          disabled={refreshing}
          className={`px-3 py-1.5 border rounded border-cyan-800/35 bg-[#0a0f1e] hover:bg-slate-900 transition-all font-mono text-[9px] font-bold text-cyan-400 uppercase flex items-center gap-1.5 cursor-pointer hover:shadow-[0_0_8px_rgba(34,211,238,0.1)] active:scale-95 ${
            refreshing ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
          <span>FORCE REFRESH</span>
        </button>
      </div>

      {showRiskConfig && <RiskConfigPanel onClose={() => setShowRiskConfig(false)} />}

    </div>
  );
}
