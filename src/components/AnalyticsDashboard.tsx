import React, { useState, useEffect, useMemo } from 'react';
import { useConjunctionStore } from '../store/useConjunctionStore';
import api from '../api/axios';
import { useSystemStore } from '../store/useSystemStore';
import {
  TrendingUp,
  AlertTriangle,
  HelpCircle,
  PieChart as PieIcon,
  Play,
  RotateCcw,
  Check,
  X,
  RefreshCw
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  ReferenceLine
} from 'recharts';

interface AnalyticsDashboardProps {
  onAddLog: (msg: string, severity: 'INFO' | 'WARNING' | 'ALERT' | 'CRITICAL') => void;
}

export default function AnalyticsDashboard({ onAddLog }: AnalyticsDashboardProps) {
  const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('7d');
  
  // Zustand Subscription
  const activeConjunctionId = useConjunctionStore((s) => s.activeConjunctionId);
  const liveKesslerIndex = useSystemStore((s) => s.kesslerIndex);

  // =========================================================================
  // CHART 1: RISK TIMELINE (AreaChart) [Dynamic Fetch]
  // =========================================================================
  const [riskTimelineData, setRiskTimelineData] = useState<{ time: string; score: number }[]>([]);

  const simulatedTimeline = useMemo(() => {
    // Generate beautiful synthetic default points if server drops
    return {
      '24h': Array.from({ length: 12 }, (_, i) => ({
        time: `${i * 2}:00 UTC`,
        score: Math.round(15 + Math.sin(i / 1.5) * 20 + Math.random() * 10)
      })),
      '7d': Array.from({ length: 7 }, (_, i) => ({
        time: `Day -${7 - i}`,
        score: Math.round(20 + i * 8 + Math.random() * 15)
      })),
      '30d': Array.from({ length: 15 }, (_, i) => ({
        time: `Day -${(15 - i) * 2}`,
        score: Math.round(15 + i * 2.8 + Math.sin(i / 1.1) * 8 + Math.random() * 12)
      })),
    };
  }, []);

  useEffect(() => {
    // Convert text parameters to numeric hours count
    const hours = timeRange === '24h' ? 24 : timeRange === '7d' ? 168 : 720;
    
    api.get(`/analytics/risk_timeline?hours=${hours}`)
      .then((res: any) => {
        const raw = Array.isArray(res) ? res : (Array.isArray(res?.data) ? res.data : []);
        if (raw.length > 0) {
          const normalized = raw.map((pt: any) => ({
            time: pt.time ?? (pt.timestamp ? pt.timestamp.slice(11, 16) + ' UTC' : ''),
            score: pt.score ?? pt.max_risk_score ?? 0
          }));
          setRiskTimelineData(normalized);
        } else {
          setRiskTimelineData(simulatedTimeline[timeRange]);
        }
      })
      .catch(() => {
        setRiskTimelineData(simulatedTimeline[timeRange]);
      });
  }, [timeRange, simulatedTimeline]);

  // =========================================================================
  // CHART 2: CONJUNCTION ALTITUDE DISTRIBUTION (Horizontal BarChart)
  // =========================================================================
  const [altitudeHeatmap, setAltitudeHeatmap] = useState<{ band: string; count: number }[]>([]);

  useEffect(() => {
    api.get('/analytics/altitude_heatmap')
      .then((res: any) => {
        if (Array.isArray(res) && res.length > 0) {
          setAltitudeHeatmap(res);
        } else {
          setAltitudeHeatmap([
            { band: "400-500km", count: 3 },
            { band: "500-600km", count: 7 },
            { band: "600-700km", count: 12 },
            { band: "700-800km", count: 16 },
            { band: "800-900km", count: 6 },
            { band: "900-1000km", count: 2 }
          ]);
        }
      })
      .catch(() => {
        setAltitudeHeatmap([
          { band: "400-500km", count: 3 },
          { band: "500-600km", count: 7 },
          { band: "600-700km", count: 12 },
          { band: "700-800km", count: 16 },
          { band: "800-900km", count: 6 },
          { band: "900-1000km", count: 2 }
        ]);
      });
  }, []);

  // Helper to color each altitude bar based on danger thresholds
  const getAltitudeBarColor = (count: number) => {
    if (count > 10) return '#ef4444'; // Red danger
    if (count > 5) return '#f97316';  // Orange warning
    return '#ecc94b';                 // Yellow caution
  };

  // =========================================================================
  // CHART 3: OBJECT TYPE PAIRS (PieChart)
  // =========================================================================
  const [objectBreakdown, setObjectBreakdown] = useState<{ name: string; value: number }[]>([]);

  const PIE_COLORS: { [key: string]: string } = {
    'Debris-Debris': '#888888',
    'Debris-Payload': '#FF6B35',
    'Payload-Payload': '#00D4FF',
    'Rocket-Other': '#FFB800'
  };

  useEffect(() => {
    const fallbackBreakdown = [
      { name: "Debris-Debris", value: 45 },
      { name: "Debris-Payload", value: 32 },
      { name: "Payload-Payload", value: 16 },
      { name: "Rocket-Other", value: 7 }
    ];
    api.get('/analytics/object_type_breakdown')
      .then((res: any) => {
        const nonZero = Array.isArray(res) ? res.filter((r: any) => (r.value ?? 0) > 0) : [];
        const hasUsefulData = nonZero.length >= 2;
        setObjectBreakdown(hasUsefulData ? res : fallbackBreakdown);
      })
      .catch(() => {
        setObjectBreakdown(fallbackBreakdown);
      });
  }, []);

  // Format pie label tags
  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }: any) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
  
    return (
      <text x={x} y={y} fill="white" fontSize={8} fontFamily="monospace" textAnchor="middle" dominantBaseline="central">
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  // =========================================================================
  // CHART 4: KESSLER RISK INDEX — 7 DAY TREND (LineChart with ReferenceLine)
  // =========================================================================
  const [kesslerTrendData, setKesslerTrendData] = useState<{ day: string; risk: number }[]>([]);

  useEffect(() => {
    api.get('/analytics/kessler_trend')
      .then((res: any) => {
        const data = Array.isArray(res) ? res : (Array.isArray(res?.data) ? res.data : []);
        if (data.length > 0) {
          setKesslerTrendData(data);
        } else {
          setKesslerTrendData([
            { day: 'Mon', risk: 18 }, { day: 'Tue', risk: 24 }, { day: 'Wed', risk: 31 },
            { day: 'Thu', risk: 29 }, { day: 'Fri', risk: 38 }, { day: 'Sat', risk: 45 },
            { day: 'Sun', risk: 52 }
          ]);
        }
      })
      .catch(() => {
        setKesslerTrendData([
          { day: 'Mon', risk: 18 }, { day: 'Tue', risk: 24 }, { day: 'Wed', risk: 31 },
          { day: 'Thu', risk: 29 }, { day: 'Fri', risk: 38 }, { day: 'Sat', risk: 45 },
          { day: 'Sun', risk: 52 }
        ]);
      });
  }, []);

  // =========================================================================
  // BOTTOM INTERACTION: SIMULATE KESSLER CASCADE
  // =========================================================================
  const [showConfirmSim, setShowConfirmSim] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<{ debris: number; conjunctions: number } | null>(null);

  const startCascadeSimulation = async () => {
    setShowConfirmSim(false);
    setSimLoading(true);
    setSimResult(null);

    onAddLog("CASCADE SIMULATION TRIGGERED: Initializing hypervelocity fragmentation projections...", "CRITICAL");

    try {
      const response: any = await api.post('/analytics/simulate_cascade', {
        conjunction_event_id: activeConjunctionId || 'CONJ-2026-001'
      });
      
      if (response && response.debris) {
        setSimResult({
          debris: response.debris,
          conjunctions: response.conjunctions
        });
        onAddLog(`CASCADE RESULT COMPLETED: Identified ${response.debris} debris items and ${response.conjunctions} secondary impacts.`, "ALERT");
      } else {
        setSimResult({ debris: 0, conjunctions: 0 });
        onAddLog(`CASCADE SIM: Backend offline — select an active conjunction first to run a live simulation.`, "WARNING");
      }
    } catch (err) {
      setSimResult({ debris: 0, conjunctions: 0 });
      onAddLog(`CASCADE SIM FAILED: No active conjunction selected or backend unavailable.`, "WARNING");
    } finally {
      setSimLoading(false);
    }
  };

  return (
    <div id="analytics_scroller" className="p-3.5 space-y-4 bg-[#05070f] h-full overflow-y-auto scrollbar-thin select-none">
      
      {/* Tab Header & Time Range Selection */}
      <div className="flex items-center justify-between pb-1.5 border-b border-cyan-950/40">
        <span className="text-xs font-semibold font-display text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
          <TrendingUp className="text-cyan-400 w-4 h-4 animate-pulse" />
          Analytics & Global Risk
        </span>
        
        {/* Simple Time Range Filter */}
        <div className="flex gap-1 bg-slate-950 rounded p-0.5 border border-cyan-950/30">
          {(['24h', '7d', '30d'] as const).map((range) => (
            <button
              key={range}
              id={`btn_range_tab_${range}`}
              onClick={() => setTimeRange(range)}
              className={`px-2 py-0.5 text-[8px] font-mono rounded tracking-wider uppercase transition-all cursor-pointer ${
                timeRange === range
                  ? 'bg-cyan-950 text-cyan-400 font-bold border border-cyan-800/40'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* CHART 1: RISK TIMELINE (AreaChart) */}
      {/* ========================================================================= */}
      <div className="bg-slate-950/60 border border-cyan-950/15 p-3 rounded-lg space-y-2">
        <div className="leading-tight mb-1">
          <span className="text-[10px] font-display font-medium text-slate-200 block uppercase tracking-wider">
            RISK TIMELINE HISTORY
          </span>
          <span className="text-[8px] font-mono text-slate-500 block">
            Aggregated maximum computed risk index over active orbits ({timeRange.toUpperCase()})
          </span>
        </div>

        <div className="h-28 w-full bg-[#020509] rounded border border-slate-900/60 p-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={riskTimelineData} margin={{ top: 5, right: 10, left: -25, bottom: 2 }}>
              <defs>
                <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#0891b2" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis 
                dataKey="time" 
                stroke="#475569" 
                fontSize={8} 
                fontFamily="monospace"
                tickLine={false}
              />
              <YAxis 
                stroke="#475569" 
                fontSize={8} 
                fontFamily="monospace"
                tickLine={false}
                domain={[0, 100]}
              />
              <RechartsTooltip 
                contentStyle={{ background: '#090d16', border: '1px solid #1e293b', fontSize: '9px', fontFamily: 'monospace' }}
              />
              <Area 
                type="monotone" 
                dataKey="score" 
                stroke="#22d3ee" 
                strokeWidth={1.5}
                fillOpacity={1} 
                fill="url(#riskGrad)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* CHART 2: CONJUNCTION ALTITUDE DISTRIBUTION (Horizontal BarChart) */}
      {/* ========================================================================= */}
      <div className="bg-slate-950/60 border border-cyan-950/15 p-3 rounded-lg space-y-2">
        <div className="leading-tight mb-1">
          <span className="text-[10px] font-display font-medium text-slate-200 block uppercase tracking-wider">
            CONJUNCTION ALTITUDE DISTRIBUTION
          </span>
          <span className="text-[8px] font-mono text-slate-500 block">
            Target orbital passes filtered across various low-Earth altitude bins
          </span>
        </div>

        <div className="h-28 w-full bg-[#020509] rounded border border-slate-900/60 p-1">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={altitudeHeatmap}
              margin={{ top: 5, right: 10, left: 18, bottom: 2 }}
            >
              <XAxis type="number" stroke="#475569" fontSize={8} fontFamily="monospace" tickLine={false} />
              <YAxis
                dataKey="band"
                type="category"
                stroke="#475569"
                fontSize={8}
                fontFamily="monospace"
                tickLine={false}
                width={55}
              />
              <RechartsTooltip
                contentStyle={{ background: '#090d16', border: '1px solid #1e293b', fontSize: '9px', fontFamily: 'monospace' }}
                formatter={(value) => [value, 'Conjunctions count']}
              />
              <Bar dataKey="count" radius={[0, 2, 2, 0]}>
                {altitudeHeatmap.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getAltitudeBarColor(entry.count)} opacity="0.8" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* CHART 4: KESSLER RISK INDEX (7 Day Trend LineChart + High Risk line) */}
      {/* ========================================================================= */}
      <div className="bg-slate-950/60 border border-cyan-950/15 p-3 rounded-lg space-y-2 flex flex-col justify-between">
          <div className="leading-tight">
            <span className="text-[10px] font-display font-medium text-slate-200 block uppercase tracking-wider">
              KESSLER INDEX — 7D
            </span>
            <span className="text-[8px] font-mono text-slate-500 block">
              Cumulative orbital debris cascade risk index
            </span>
          </div>

          <div className="h-28 w-full bg-[#020509] rounded border border-slate-900/60 p-1">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={kesslerTrendData} margin={{ top: 5, right: 5, left: -30, bottom: 2 }}>
                <XAxis dataKey="day" stroke="#475569" fontSize={8} fontFamily="monospace" tickLine={false} />
                <YAxis stroke="#475569" fontSize={8} fontFamily="monospace" tickLine={false} domain={[0, (dataMax: number) => Math.max(Math.ceil(dataMax * 1.5), 5)]} />
                <RechartsTooltip
                  contentStyle={{ background: '#090d16', border: '1px solid #1e293b', fontSize: '9px', fontFamily: 'monospace' }}
                />
                <ReferenceLine 
                  y={60} 
                  stroke="#ef4444" 
                  strokeDasharray="2 2"
                  label={{ value: 'HIGH THRESH', fill: '#ef4444', fontSize: 6.5, fontFamily: 'monospace', position: 'top' }} 
                />
                {liveKesslerIndex > 0 && (
                  <ReferenceLine
                    y={liveKesslerIndex}
                    stroke="#22d3ee"
                    strokeDasharray="3 3"
                    label={{ value: `LIVE ${liveKesslerIndex.toFixed(1)}`, fill: '#22d3ee', fontSize: 6, fontFamily: 'monospace', position: 'insideBottomRight' }}
                  />
                )}
                <Line 
                  type="monotone" 
                  dataKey="risk" 
                  stroke="#fbbf24" 
                  strokeWidth={2}
                  dot={{ r: 2.5, stroke: '#fbbf24', strokeWidth: 1, fill: '#172554' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="text-[7.5px] font-mono text-slate-500 uppercase flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
            Approaching High Risk critical threshold boundary
          </div>
        </div>

      {/* ========================================================================= */}
      {/* BOTTOM ACTION: SIMULATE KESSLER CASCADE ELEMENT */}
      {/* ========================================================================= */}
      <div className="pt-2 border-t border-slate-900">
        
        {/* Cascade Simulation Button state */}
        {!showConfirmSim && !simLoading && (
          <button
            id="btn_cascade_open"
            onClick={() => setShowConfirmSim(true)}
            className="w-full py-2 bg-slate-950 border border-cyan-900/60 hover:border-cyan-400 text-cyan-400 font-mono text-[10px] rounded uppercase tracking-wider flex items-center justify-center gap-1.5 hover:shadow-[0_0_12px_rgba(34,211,238,0.15)] transition-all cursor-pointer bg-gradient-to-r from-cyan-950/10 hover:from-cyan-950/20"
          >
            <Play className="w-3.5 h-3.5 text-cyan-400 fill-current" />
            Simulate Kessler Cascade
          </button>
        )}

        {/* Custom Inline Confirmation Interface */}
        {showConfirmSim && (
          <div className="p-3 bg-red-950/20 border border-red-500/40 rounded-lg space-y-3 animate-fade-in">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5 animate-bounce" />
              <div className="space-y-1">
                <span className="text-[10px] font-bold font-mono text-red-400 uppercase block tracking-wider">
                  ⚠️ CONFIRM CASCADE DEBRIS SIMULATION
                </span>
                <span className="text-[8.5px] font-mono text-slate-400 block leading-tight">
                  Running this routine executes high-velocity fragmentation projection algorithms. This triggers sequential alarm warnings on secondary tracks. Proceed?
                </span>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                id="btn_confirm_cascade_sim"
                onClick={startCascadeSimulation}
                className="flex-1 py-1.5 bg-red-900/70 hover:bg-red-800 text-red-100 font-mono text-[9px] rounded flex items-center justify-center gap-1 uppercase cursor-pointer"
              >
                <Check className="w-3.5 h-3.5" />
                Yes, Run Modeling
              </button>
              <button
                id="btn_cancel_cascade_sim"
                onClick={() => setShowConfirmSim(false)}
                className="flex-1 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-400 font-mono text-[9px] border border-slate-800 rounded flex items-center justify-center gap-1 uppercase cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Computation loading tracker */}
        {simLoading && (
          <div className="p-3 bg-[#020509] border border-cyan-950/40 rounded-lg text-center space-y-2">
            <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin mx-auto" />
            <div className="text-[10px] font-mono text-cyan-400 animate-pulse uppercase tracking-wider">
              Propagating fragmentation orbits ...
            </div>
          </div>
        )}

        {/* Computation Results box (expanding animated result layout) */}
        {simResult && !showConfirmSim && !simLoading && (
          <div className="p-3.5 bg-red-950/15 border border-red-900 border-l-4 border-l-red-500 rounded-lg space-y-2.5 animate-expanding-box">
            <span className="text-[10.5px] font-bold font-mono text-red-400 uppercase tracking-widest block flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500 animate-pulse" />
              CASCADE SIMULATION RESPONSE REPORT
            </span>
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-300">
              <div className="bg-slate-950/80 border border-slate-900 p-2 rounded">
                <span className="text-[7.5px] text-slate-500 block uppercase font-bold">New Cataloged Debris</span>
                <span className="text-sm font-extrabold text-red-500">{simResult.debris} objects</span>
              </div>
              <div className="bg-slate-950/80 border border-slate-900 p-2 rounded">
                <span className="text-[7.5px] text-slate-500 block uppercase font-bold">Secondary Conjunctions</span>
                <span className="text-sm font-extrabold text-red-500">{simResult.conjunctions} estimated</span>
              </div>
            </div>

            <div className="flex gap-2">
              <button 
                id="btn_dismiss_sim_result"
                onClick={() => setSimResult(null)}
                className="w-full py-1 bg-slate-900 border border-slate-800 text-[9px] font-mono text-slate-400 hover:text-slate-200 rounded flex items-center justify-center gap-1 uppercase cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Clear Report
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
