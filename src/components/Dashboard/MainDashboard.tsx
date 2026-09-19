import React, { useState, useEffect, useMemo } from 'react';
import { INITIAL_CONJUNCTIONS, INITIAL_ML_MODELS, INITIAL_AUDIT_LOGS } from '../../data';
import { ConjunctionEvent, MLModelStats, AuditLog as AuditLogType, Satellite } from '../../types';
import StatsBar from '../StatsBar';
import { lazy, Suspense } from 'react';
import ConjunctionFeed from '../ConjunctionPanel/ConjunctionFeed';
const GlobeScene = lazy(() => import('../GlobeScene'));
const MLPanel = lazy(() => import('../MLPanel'));
import ManeuverPanel from '../ManeuverPanel';
import AnalyticsDashboard from '../AnalyticsDashboard';
import AuditLog from '../AuditLog/AuditLog';
import DemoModeBanner from './DemoModeBanner';
import { useConjunctionStore } from '../../store/useConjunctionStore';
import { useGlobeStore } from '../../store/useGlobeStore';
import {
  ListFilter,
  Brain,
  Rocket,
  TrendingUp,
  Terminal,
  Download,
  Tv,
  Maximize2,
  Minimize2,
  Lock,
  Activity,
  Globe,
  Compass,
  RotateCcw,
} from 'lucide-react';

export default function MainDashboard() {
  const storeConjunctions = useConjunctionStore((s) => s.conjunctions);
  const satellitePositions = useGlobeStore((s) => s.satellitePositions);

  const activeConjunctions = Array.isArray(storeConjunctions) ? storeConjunctions : [];

  const activeConjunctionId = useConjunctionStore((s) => s.activeConjunctionId);

  useEffect(() => {
    if (!activeConjunctionId && activeConjunctions.length > 0) {
      const firstId = activeConjunctions[0].id;
      useConjunctionStore.getState().setActiveConjunction(firstId);
      useGlobeStore.getState().setSelectedConjunction(firstId);
    }
  }, [activeConjunctions, activeConjunctionId]);

  const selectedConjunction = activeConjunctions.find((c) => c.id === activeConjunctionId) || null;
  const setSelectedConjunction = (conj: ConjunctionEvent | null) => {
    const id = conj ? conj.id : null;
    useConjunctionStore.getState().setActiveConjunction(id);
    useGlobeStore.getState().setSelectedConjunction(id);
  };

  const selectedSatelliteId = useGlobeStore((s) => s.selectedSatelliteId);
  const setSelectedSatellite = useGlobeStore((s) => s.setSelectedSatellite);
  const cinematicMode = useGlobeStore((s) => s.cinematicMode);
  const setCinematicMode = useGlobeStore((s) => s.setCinematicMode);

  // Interval timer to force reactive re-renders showing live spinning lat/lon coordinates
  const [, setMilliTicker] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => {
      setMilliTicker((t) => t + 1);
    }, 250);
    return () => clearInterval(interval);
  }, []);

  // models state removed — ML metrics fetched live in MLPanel directly

  const [leftTab, setLeftTab] = useState<'CONJUNCTIONS' | 'ML_STATUS'>('CONJUNCTIONS');
  const [rightTab, setRightTab] = useState<'MANEUVER' | 'ANALYTICS'>('MANEUVER');
  const resetCameraRef = React.useRef<() => void>(() => {});

  const [layers, setLayers] = useState({
    satellites: true,
    orbits: true,
    conjunctions: true,
  });

  const [auditLogCollapsed, setAuditLogCollapsed] = useState(true);
  const [satelliteSearch, setSatelliteSearch] = useState('');

  const systemRisk = activeConjunctions.some((c) => c.status === 'CRITICAL')
    ? 'CRITICAL'
    : activeConjunctions.some((c) => c.status === 'HIGH')
    ? 'HIGH'
    : 'LOW';

  // Find selected satellite info from dynamic store list
  const activeSelectedSatellite = useMemo(() => {
    if (!selectedSatelliteId) return null;
    return (satellitePositions as any[]).find(
      (s) => s.id === selectedSatelliteId || s.noradId === selectedSatelliteId || s.norad_id === selectedSatelliteId
    );
  }, [selectedSatelliteId, satellitePositions]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        backgroundColor: '#030611',
      }}
      className="text-slate-300 font-sans select-none overflow-hidden antialiased relative"
    >
      {/* 56px height, fixed top - Hidden in Cinematic View */}
      {!cinematicMode && <StatsBar systemRisk={systemRisk} onAddLog={(msg, sev) => console.log('[AUDIT]', sev, msg)} />}

      {/* Main viewport area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }} className="relative">
        {/* LeftPanel - Hidden in Cinematic View */}
        {!cinematicMode && (
          <div
            id="left_panel"
            style={{ width: '320px', flexShrink: 0 }}
            className="bg-[#060a15] border-r border-[#151f38]/60 flex flex-col overflow-hidden transition-all duration-300"
          >
            {/* Tab Switchers */}
            <div className="flex border-b border-[#141d33]/55 h-10 shrink-0 bg-[#040710]/80">
              <button
                id="tab_conjunctions"
                onClick={() => setLeftTab('CONJUNCTIONS')}
                className={`flex-1 flex items-center justify-center gap-1.5 text-[9px] uppercase font-mono font-bold tracking-wider transition-all h-full ${
                  leftTab === 'CONJUNCTIONS'
                    ? 'text-cyan-400 bg-[#060a15] border-b-2 border-cyan-400'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <ListFilter className="w-3.5 h-3.5" />
                CONJUNCTIONS
              </button>
              <button
                id="tab_ml_status"
                onClick={() => setLeftTab('ML_STATUS')}
                className={`flex-1 flex items-center justify-center gap-1.5 text-[9px] uppercase font-mono font-bold tracking-wider transition-all h-full ${
                  leftTab === 'ML_STATUS'
                    ? 'text-cyan-400 bg-[#060a15] border-b-2 border-cyan-400'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <Brain className="w-3.5 h-3.5" />
                ML STATUS
              </button>
            </div>

            {/* Left Contents Panel */}
            <div className="flex-1 overflow-y-auto">
              {leftTab === 'CONJUNCTIONS' ? <ConjunctionFeed /> : (
                <Suspense fallback={<div>Loading ML panel...</div>}>
                  <MLPanel onAddLog={(msg, sev) => console.log('[AUDIT]', sev, msg)} />
                </Suspense>
              )}
            </div>
          </div>
        )}

        {/* Center Section: Earth Globe Viewport */}
        <div
          style={{ flex: 1 }}
          className={`overflow-hidden flex flex-col min-w-0 bg-[#030611] relative transition-all duration-500 ${
            cinematicMode ? 'p-0' : 'p-2'
          }`}
        >
          {/* Top Panel Bar with Cinematic toggle inside non-cinematic view */}
          {!cinematicMode ? (
            <div className="flex items-center justify-between px-3 py-1.5 bg-[#070c1b]/80 border border-[#141d33]/40 rounded font-mono text-[9px] uppercase tracking-wider text-slate-400 shrink-0 mb-1.5">
              <span className="flex items-center gap-1.5 font-bold">
                <span className="w-1.5 h-1.5 bg-cyan-400 animate-pulse rounded-full inline-block"></span>
                ACTIVE SGP4 ORBITAL CORE
              </span>

              <div className="flex items-center gap-4">
                <span className="text-cyan-600/70 font-semibold italic hidden sm:inline">
                  LEO DEBRIS DOCK ACTIVE
                </span>
                <button
                  id="btn_toggle_cinematic"
                  onClick={() => setCinematicMode(true)}
                  className="px-2.5 py-1 border border-cyan-500/20 hover:border-cyan-400/60 hover:bg-cyan-500/10 rounded font-mono text-[8px] font-bold text-cyan-400 transition-all flex items-center gap-1 cursor-pointer"
                >
                  <Tv className="w-3 h-3 text-cyan-400" />
                  CINEMATIC VIEW
                </button>
              </div>
            </div>
          ) : null}

          {/* Core scene window */}
          <div className="flex-1 min-h-0 relative">
            <Suspense fallback={<div>Loading globe...</div>}>
              <GlobeScene
                conjunctions={activeConjunctions}
                selectedConjunction={selectedConjunction}
                onSelectConjunction={setSelectedConjunction}
                onResetCamera={(fn) => { resetCameraRef.current = fn; }}
                layers={layers}
                setLayers={setLayers}
              />
            </Suspense>

            {/* Cinematic Floating Head-up display (HUDs) */}
            {cinematicMode && (
              <>
                {/* Top Cinematic Navigation Overlay */}
                {/* Top-left HUD branding */}
                <div className="absolute top-8 left-4 pointer-events-none z-20">
                  <div className="flex flex-col bg-[#040813]/85 backdrop-blur-md border border-[#142340]/50 p-3 rounded shadow-2xl">
                    <span className="font-mono text-[10px] font-black tracking-widest text-cyan-400 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                      ORBIT SENTINEL // TELEMETRY CINEMATIC DECK
                    </span>
                    <span className="text-[8px] font-mono text-slate-400 mt-1 uppercase">
                      Ground Station Uplink Stable • Stream: CelesTrak JSON Live Feed
                    </span>
                  </div>
                </div>

                {/* Top-right controls */}
                <div className="absolute top-4 right-4 z-20 flex items-center gap-2 pointer-events-auto">
                  <button
                    onClick={() => resetCameraRef.current()}
                    className="p-1.5 px-2 bg-[#040813]/85 backdrop-blur-md border border-cyan-800/30 hover:border-cyan-500/50 hover:bg-slate-900/80 rounded font-mono text-[9px] text-slate-400 hover:text-cyan-400 transition-all cursor-pointer shadow-xl uppercase tracking-wider flex items-center gap-1.5"
                  >
                    <RotateCcw className="w-3 h-3" />
                    RESET CAMERA
                  </button>
                  <button
                    onClick={() => {
                      setCinematicMode(false);
                      setSelectedSatellite(null);
                    }}
                    className="px-4 py-2 bg-[#040813]/85 backdrop-blur-md border border-cyan-500/40 hover:border-cyan-400 hover:bg-cyan-500/20 rounded font-mono text-[9px] font-extrabold text-cyan-400 transition-all cursor-pointer shadow-xl uppercase tracking-wider flex items-center gap-2"
                  >
                    <Minimize2 className="w-3.5 h-3.5 text-cyan-400" />
                    EXIT SPACEFEED
                  </button>
                </div>

                {/* Left/Bottom Cinematic Tab - Telemetry glass index card */}
                <div className="absolute bottom-16 left-6 z-20 pointer-events-auto max-w-sm w-80">
                  {activeSelectedSatellite ? (
                    <div className="bg-[#030713]/90 backdrop-blur-xl border border-cyan-500/40 p-4 rounded-lg shadow-[0_0_25px_rgba(6,182,212,0.15)] select-none">
                      <div className="flex items-center justify-between pb-2 border-b border-[#142340] mb-3">
                        <div className="flex items-center gap-1.5 font-mono text-[11px] font-extrabold text-cyan-400 uppercase">
                          <Activity className="w-4 h-4 text-cyan-500 animate-pulse" />
                          <span>🛰️ asset locked</span>
                        </div>
                        <button
                          onClick={() => setSelectedSatellite(null)}
                          className="text-slate-500 hover:text-slate-300 font-mono text-[8px] uppercase font-bold px-1.5 py-0.5 border border-slate-800 hover:border-slate-600 rounded"
                        >
                          Unlock
                        </button>
                      </div>

                      <h3 className="font-mono text-base font-extrabold text-white uppercase tracking-tight flex items-center gap-1.5">
                        {activeSelectedSatellite.name}
                      </h3>
                      

                      {/* Hardware details Grid */}
                      <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-[#142340]/40 font-mono text-[9px]">
                        <div className="bg-[#060b19]/60 p-1.5 rounded border border-[#142340]/25">
                          <span className="text-slate-500 block truncate text-[7.5px]">NORAD CATALOG ID</span>
                          <span className="text-cyan-400 font-bold text-[10px]">
                            {activeSelectedSatellite.noradId || activeSelectedSatellite.norad_id || activeSelectedSatellite.id}
                          </span>
                        </div>
                        <div className="bg-[#060b19]/60 p-1.5 rounded border border-[#142340]/25">
                          <span className="text-slate-500 block truncate text-[7.5px]">INCLINATION DEG</span>
                          <span className="text-white font-semibold">
                            {activeSelectedSatellite.inclination != null ? Number(activeSelectedSatellite.inclination).toFixed(2) : '—'}°
                          </span>
                        </div>
                        <div className="bg-[#060b19]/60 p-1.5 rounded border border-[#142340]/25">
                          <span className="text-slate-500 block truncate text-[7.5px]">APOGEE / PERIGEE</span>
                          <span className="text-white font-semibold">
                            {activeSelectedSatellite.apogee != null ? activeSelectedSatellite.apogee : '—'}km / {activeSelectedSatellite.perigee != null ? activeSelectedSatellite.perigee : '—'}km
                          </span>
                        </div>
                        <div className="bg-[#060b19]/60 p-1.5 rounded border border-[#142340]/25">
                          <span className="text-slate-500 block truncate text-[7.5px]">VELOCITY VALUE</span>
                          <span className="text-emerald-400 font-semibold">
                            {activeSelectedSatellite.velocity != null ? Number(activeSelectedSatellite.velocity).toFixed(2) : (activeSelectedSatellite.speed_kmps != null ? Number(activeSelectedSatellite.speed_kmps).toFixed(2) : '—')} km/s
                          </span>
                        </div>
                      </div>

                      {/* Dynamic coordinate propagation ticker */}
                      <div className="bg-[#040815] border border-cyan-950/70 rounded p-2.5 mt-3">
                        <div className="flex justify-between font-mono text-[8.5px] text-slate-400">
                          <span>LAT:</span>
                          <span className="text-emerald-400 font-bold block">
                            {activeSelectedSatellite.lat !== undefined
                              ? activeSelectedSatellite.lat.toFixed(5)
                              : '0.000'}°
                          </span>
                        </div>
                        <div className="flex justify-between font-mono text-[8.5px] text-slate-400 mt-1">
                          <span>LON:</span>
                          <span className="text-emerald-400 font-bold block">
                            {activeSelectedSatellite.lng !== undefined || activeSelectedSatellite.lon !== undefined
                              ? (activeSelectedSatellite.lng ?? activeSelectedSatellite.lon).toFixed(5)
                              : '0.000'}°
                          </span>
                        </div>
                        <div className="flex justify-between font-mono text-[8.5px] text-slate-400 mt-1">
                          <span>ALT:</span>
                          <span className="text-white font-bold block">{activeSelectedSatellite.alt || '0'} km</span>
                        </div>
                      </div>

                      {/* Live sensor check statuses */}
                      <div className="flex items-center gap-1.5 mt-4 text-[7px] font-mono uppercase bg-[#00f2fe]/5 border border-[#00f2fe]/20 p-2 rounded">
                        <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce shrink-0" />
                        <span className="text-slate-400">
                          PROPAGATION STREAM: OK // SGP4 RESOLUTION IN SYNC
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-[#030713]/85 backdrop-blur-md border border-[#151f38]/60 p-4 rounded shadow-lg">
                      <div className="flex items-center gap-2 font-mono text-[10px] text-cyan-400 font-semibold uppercase">
                        <Compass className="w-4 h-4 text-cyan-400 animate-spin-slow" />
                        <span>Radar Scope Active</span>
                      </div>
                      <p className="font-mono text-[8.5px] text-slate-500 mt-2 uppercase leading-relaxed">
                        Click on any dynamic orbiting satellite node inside the space viewport to dock and download holographic telemetry grids.
                      </p>
                    </div>
                  )}
                </div>

                {/* Right Cinematic Overlay Links to scroll satellite array */}
                <div className="absolute bottom-16 right-6 z-20 pointer-events-auto bg-[#030713]/85 backdrop-blur-md border border-[#151f38]/60 p-3.5 rounded shadow-xl w-64 max-h-72 overflow-y-auto font-mono text-[9px]">
                  <div className="text-[10px] font-bold text-cyan-400 mb-2 border-b border-[#142340] pb-1 uppercase">
                    🔭 ORBITING ASSETS ({satellitePositions.length})
                  </div>
                  <input
                    type="text"
                    value={satelliteSearch}
                    onChange={(e) => setSatelliteSearch(e.target.value)}
                    placeholder="Search satellites..."
                    className="w-full mb-2 px-2 py-1 bg-[#040710] border border-[#142340] rounded text-[9px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 uppercase"
                  />
                  <div className="space-y-1">
                    {(Array.isArray(satellitePositions) ? satellitePositions : [])
                      .filter((sat: any) =>
                        (sat.name || '').toLowerCase().includes(satelliteSearch.toLowerCase())
                      )
                      .map((sat: any) => {
                        const id = sat.id || sat.noradId || sat.norad_id;
                        const isActive = selectedSatelliteId === id;
                        return (
                          <button
                            key={id}
                            onClick={() => setSelectedSatellite(isActive ? null : id)}
                            className={`w-full text-left px-2 py-1 rounded transition-colors uppercase truncate block cursor-pointer ${
                              isActive
                                ? 'bg-cyan-500/20 text-cyan-400 font-black border border-cyan-500/30'
                                : 'text-slate-400 hover:bg-[#060b19] border border-transparent hover:text-white'
                            }`}
                          >
                            ⚙️ {sat.name}
                          </button>
                        );
                      })}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* RightPanel - Hidden in Cinematic View */}
        {!cinematicMode && (
          <div
            id="right_panel"
            style={{ width: '320px', flexShrink: 0 }}
            className="bg-[#060a15] border-l border-[#151f38]/60 flex flex-col overflow-hidden transition-all duration-300"
          >
            {/* Tab Switchers */}
            <div className="flex border-b border-[#141d33]/55 h-10 shrink-0 bg-[#040710]/80">
              <button
                id="tab_maneuver"
                onClick={() => setRightTab('MANEUVER')}
                className={`flex-1 flex items-center justify-center gap-1.5 text-[9px] uppercase font-mono font-bold tracking-wider transition-all h-full ${
                  rightTab === 'MANEUVER'
                    ? 'text-cyan-400 bg-[#060a15] border-b-2 border-cyan-400'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <Rocket className="w-3.5 h-3.5" />
                MANEUVER
              </button>
              <button
                id="tab_analytics"
                onClick={() => setRightTab('ANALYTICS')}
                className={`flex-1 flex items-center justify-center gap-1.5 text-[9px] uppercase font-mono font-bold tracking-wider transition-all h-full ${
                  rightTab === 'ANALYTICS'
                    ? 'text-cyan-400 bg-[#060a15] border-b-2 border-cyan-400'
                    : 'text-slate-500 hover:text-slate-300 font-semibold'
                }`}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                ANALYTICS
              </button>
            </div>

            {/* Right Contents Panel */}
            <div className="flex-1 overflow-y-auto">
              {rightTab === 'MANEUVER' ? (
                <ManeuverPanel />
              ) : (
                <AnalyticsDashboard onAddLog={(msg, sev) => console.log('[AUDIT]', sev, msg)} />
              )}
            </div>
          </div>
        )}
      </div>

      {/* AuditLogStrip: collapsible bottom - Hidden in Cinematic View */}
      {!cinematicMode && (
        <div
          id="audit_log_collapsible_strip"
          className={`bg-[#03050c] border-t border-[#151f38]/50 flex flex-col shrink-0 select-none transition-all duration-300 ${
            auditLogCollapsed ? 'h-9' : 'h-[220px]'
          }`}
        >
          {/* Strip Header controls */}
          <div className="h-9 w-full flex items-center justify-between px-4 bg-[#050916] border-b border-[#151f38]/20 shrink-0">
            <div className="flex items-center gap-2 font-mono text-[9px] font-bold tracking-wider text-slate-300 uppercase">
              <Terminal className="w-3.5 h-3.5 text-cyan-500 animate-pulse" />
              <span>SYSTEM SECURITY AUDIT LOG</span>
            </div>

            <div className="flex items-center gap-3">
              <button
                id="btn_toggle_audit_log"
                onClick={() => setAuditLogCollapsed(!auditLogCollapsed)}
                className="p-1 text-slate-400 hover:text-cyan-400 transition-colors cursor-pointer"
              >
                {auditLogCollapsed ? (
                  <span className="text-[10px] font-mono hover:text-cyan-400 font-bold">▲</span>
                ) : (
                  <span className="text-[10px] font-mono hover:text-cyan-400 font-bold">▼</span>
                )}
              </button>
            </div>
          </div>

          {/* Scrollable AuditLog panel when open */}
          {!auditLogCollapsed && (
            <div className="flex-1 overflow-hidden">
              <AuditLog />
            </div>
          )}
        </div>
      )}
    </div>
  );
}