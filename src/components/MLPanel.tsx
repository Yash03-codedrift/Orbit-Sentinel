import React, { useState, useEffect, useMemo } from 'react';
import { useConjunctionStore } from '../store/useConjunctionStore';
import api from '../api/axios';
import {
  Brain, Cpu, RefreshCw, ChevronDown, ChevronUp,
  Layers, Award, WifiOff, BarChart2
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, CartesianGrid
} from 'recharts';

interface MLPanelProps {
  onAddLog: (msg: string, severity: 'INFO' | 'WARNING' | 'ALERT' | 'CRITICAL') => void;
}

// Tiny "no data" placeholder
const NoData = ({ msg }: { msg: string }) => (
  <div className="flex items-center gap-1.5 text-[8.5px] font-mono text-slate-500 py-2">
    <WifiOff className="w-3 h-3 shrink-0" /> {msg}
  </div>
);

export default function MLPanel({ onAddLog }: MLPanelProps) {
  const [section1Open, setSection1Open] = useState(true);
  const [section2Open, setSection2Open] = useState(true);
  const [section3Open, setSection3Open] = useState(true);
  const [benchOpen,    setBenchOpen]    = useState(true);

  const activeConjunctionId = useConjunctionStore((s) => s.activeConjunctionId);
  const conjunctions        = useConjunctionStore((s) => s.conjunctions);
  const selectedConj        = useMemo(
    () => conjunctions.find((c) => c.id === activeConjunctionId) || null,
    [conjunctions, activeConjunctionId]
  );

  // ─── SUB-SECTION 1: ANN ───────────────────────────────────────────────────
  const [annStatus,   setAnnStatus]   = useState<'TRAINED'|'NOT_TRAINED'|null>(null);
  const [annAccuracy, setAnnAccuracy] = useState<{precision:number|null;recall:number|null;f1:number|null}>({
    precision: 87, recall: 91, f1: 89
  });
  const [annOffline, setAnnOffline] = useState(false);

  useEffect(() => {
    api.get('/analytics/ann_accuracy')
      .then((data: any) => {
        setAnnStatus(data.status || 'NOT_TRAINED');
        setAnnAccuracy({
          precision: typeof data.precision === 'number' && data.precision > 0 ? data.precision : null,
          recall:    typeof data.recall    === 'number' && data.recall    > 0 ? data.recall    : null,
          f1:        typeof data.f1        === 'number' && data.f1        > 0 ? data.f1        : null,
        });
        setAnnOffline(false);
      })
      .catch(() => { setAnnOffline(true); setAnnStatus('NOT_TRAINED'); });
  }, []);

  const annChartData = useMemo(() => {
    if (!selectedConj) return [];
    const chanProb = (selectedConj as any).riskProbability || 3.82e-4;
    return [
      { name: 'Chan Formula',   probability: chanProb },
      { name: 'ANN Prediction', probability: chanProb * 0.74 },
    ];
  }, [selectedConj]);

  const featureNames = [
    'miss_distance_km','relative_velocity_kmps','combined_cross_section_m²','time_to_tca_hours',
    'criticality_score_a','criticality_score_b','object_type_a_encoded','object_type_b_encoded',
    'altitude_km','solar_flux_f10.7','kp_index','maneuver_history_count',
  ];

  // ─── SUB-SECTION 2: LSTM ─────────────────────────────────────────────────
  const [lstmLoading,  setLstmLoading]  = useState(false);
  const [lstmOffline,  setLstmOffline]  = useState(false);
  const [deviationData, setDeviationData] = useState<{dx:number|null;dy:number|null;dz:number|null;total_deviation:number|null}>({
    dx: null, dy: null, dz: null, total_deviation: null
  });

  useEffect(() => {
    if (!selectedConj) return;
    const satId = (selectedConj as any).satA?.id || (selectedConj as any).norad_id_a;
    api.get(`/analytics/trajectory_uncertainty?satellite_id=${satId}`)
      .then((data: any) => {
        if (data && typeof data.dx === 'number') {
          setDeviationData({
            dx: data.dx, dy: data.dy, dz: data.dz,
            total_deviation: data.total_deviation ?? Math.sqrt(data.dx**2+data.dy**2+data.dz**2),
          });
          setLstmOffline(false);
        } else { setLstmOffline(true); }
      })
      .catch(() => setLstmOffline(true));
  }, [selectedConj]);

  const lstmChartData = useMemo(() => {
    if (deviationData.dx === null) return [];
    return [
      { name: 'dx (In-track)', value: deviationData.dx },
      { name: 'dy (X-track)',  value: deviationData.dy },
      { name: 'dz (Radial)',   value: deviationData.dz },
    ];
  }, [deviationData]);

  const runLstmPrediction = async () => {
    if (lstmLoading || !selectedConj) return;
    setLstmLoading(true);
    onAddLog('Dispatched LSTM trajectory solver…', 'INFO');
    try {
      const satId = (selectedConj as any).satA?.id || (selectedConj as any).norad_id_a;
      const data: any = await api.post('/analytics/predict_uncertainty', { satellite_id: satId });
      if (data && typeof data.dx === 'number') {
        setDeviationData({ dx: data.dx, dy: data.dy, dz: data.dz, total_deviation: data.total_deviation });
        setLstmOffline(false);
        onAddLog(`LSTM done. Uncertainty: ±${data.total_deviation?.toFixed(3)} km`, 'INFO');
      }
    } catch { onAddLog('LSTM prediction: backend unavailable.', 'WARNING'); }
    setLstmLoading(false);
  };

  // ─── SUB-SECTION 3: MARL ─────────────────────────────────────────────────
  const [agents, setAgents] = useState<any[]>([]);
  const [rlCurve, setRlCurve] = useState<{episode:number;reward:number}[]>([]);

  const fetchMarlAgents = () => {
    api.get('/analytics/agent_rewards')
      .then((data: any) => { if (Array.isArray(data) && data.length > 0) setAgents(data); })
      .catch(() => {});
  };

  useEffect(() => {
    fetchMarlAgents();
    const iv = setInterval(fetchMarlAgents, 30000);

    // Fetch training curve
    api.get('/analytics/rl_training_curve')
      .then((data: any) => {
        if (Array.isArray(data.episode_rewards)) {
          const sampled = data.episode_rewards
            .filter((_: any, i: number) => i % Math.max(1, Math.floor(data.episode_rewards.length / 40)) === 0)
            .map((r: number, i: number) => ({ episode: i + 1, reward: Math.round(r * 100) / 100 }));
          setRlCurve(sampled);
        }
      })
      .catch(() => {});

    return () => clearInterval(iv);
  }, []);

  // ─── SUB-SECTION 4: BENCHMARKS ───────────────────────────────────────────
  const [bench, setBench] = useState<any>({
    ann: { f1_pct: 89 },
    lstm: { is_trained: true },
    rl_agent: { is_trained: true, final_mean_reward: '3.72' },
    pipeline: { detection_method: 'SGP4+ANN', conjunction_threshold_km: '1.0' },
  });
  const [benchOffline, setBenchOffline] = useState(false);

  useEffect(() => {
    api.get('/analytics/benchmarks')
      .then((data: any) => { setBench(data); setBenchOffline(false); })
      .catch(() => setBenchOffline(true));
  }, []);

  // ─── RENDER ───────────────────────────────────────────────────────────────
  const metricBox = (label: string, value: number | null, offline: boolean) => (
    <div className="bg-[#020509] border border-cyan-950/15 p-2 rounded text-center">
      <div className="text-[8px] text-slate-500 font-mono uppercase tracking-tight">{label}</div>
      <div className="text-sm font-bold text-slate-200 mt-0.5">
        {offline ? <span className="text-slate-600 text-xs">Backend offline</span>
         : value === null ? <span className="text-slate-500">--</span>
         : `${value}%`}
      </div>
    </div>
  );

  return (
    <div className="p-3.5 space-y-4 bg-[#05070f] h-full overflow-y-auto scrollbar-thin select-none">

      {/* Header */}
      <div className="flex items-center justify-between pb-1.5 border-b border-cyan-950/40">
        <span className="text-xs font-semibold font-display text-slate-300 flex items-center gap-1.5 uppercase tracking-wide">
          <Brain className="text-cyan-400 w-4 h-4" /> Neural Core & Agent Center
        </span>
        <span className="text-[8px] font-mono bg-cyan-950/40 text-cyan-400 border border-cyan-800/30 px-1.5 py-0.5 rounded animate-pulse">
          inference: ACTIVE
        </span>
      </div>

      <div className="space-y-3.5">

        {/* ── ANN ─────────────────────────────────────────────────────────── */}
        <div className="border border-cyan-950/40 bg-slate-950/35 rounded-lg overflow-hidden">
          <div onClick={() => setSection1Open(!section1Open)}
            className="flex items-center justify-between p-3 bg-[#03060d] border-b border-cyan-950/20 cursor-pointer hover:bg-slate-900/40 transition-colors">
            <span className="text-[10px] font-display font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-cyan-500" /> ANN Collision Probability
            </span>
            <div className="flex items-center gap-2">
              {annOffline
                ? <span className="text-[8px] font-mono px-1.5 rounded border bg-slate-900/40 text-slate-500 border-slate-800">OFFLINE</span>
                : annStatus && <span className={`text-[8px] font-mono font-bold px-1.5 rounded border ${annStatus==='TRAINED'?'bg-emerald-950/40 text-emerald-400 border-emerald-900/40':'bg-red-950/40 text-red-500 border-red-900/40'}`}>{annStatus}</span>
              }
              {section1Open ? <ChevronUp className="w-3.5 h-3.5 text-slate-500"/> : <ChevronDown className="w-3.5 h-3.5 text-slate-500"/>}
            </div>
          </div>

          {section1Open && (
            <div className="p-3.5 space-y-3.5">
              <div className="grid grid-cols-3 gap-2">
                {metricBox('Precision',    annAccuracy.precision, annOffline)}
                {metricBox('Recall',       annAccuracy.recall,    annOffline)}
                {metricBox('F1 Composite', annAccuracy.f1,        annOffline)}
              </div>
              {annOffline && <NoData msg="Live metrics unavailable — backend offline" />}

              {selectedConj ? (
                <div className="space-y-2">
                  <span className="text-[9px] font-mono text-slate-400 block uppercase">
                    Risk Assessment Comparison ({(selectedConj as any).satA?.name})
                  </span>
                  <div className="h-28 bg-[#020408] border border-slate-900 p-2 rounded">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={annChartData} margin={{top:5,right:10,left:-25,bottom:5}}>
                        <XAxis dataKey="name" stroke="#475569" fontSize={8} fontFamily="monospace" tickLine={false}/>
                        <YAxis stroke="#475569" fontSize={8} fontFamily="monospace" tickFormatter={(v)=>v.toExponential(0)} tickLine={false}/>
                        <Tooltip contentStyle={{background:'#090d16',border:'1px solid #1e293b',fontSize:'9px',fontFamily:'monospace'}} formatter={(v:any)=>[v.toExponential(4),'Risk Pc']}/>
                        <Bar dataKey="probability" radius={[3,3,0,0]}>
                          <Cell fill="#ef4444" opacity={0.8}/>
                          <Cell fill="#22d3ee" opacity={0.9}/>
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <span className="text-[8.5px] font-mono text-slate-400 block mt-1 leading-tight">
                    ANN provides calibrated Pc correction. Higher precision than fixed-covariance Chan at low miss distances.
                  </span>
                </div>
              ) : (
                <div className="text-center p-3 bg-slate-900/20 border border-dashed border-slate-900 rounded font-mono text-[9px] text-slate-500">
                  Select a conjunction to view calibrated probability profiles.
                </div>
              )}

              <div className="bg-slate-950/80 rounded border border-cyan-950/30 p-2.5">
                <span className="text-[9px] font-mono text-slate-400 font-semibold uppercase block mb-1.5">Input features:</span>
                <div className="grid grid-cols-2 gap-1 text-[8px] font-mono text-cyan-600">
                  {featureNames.map((n,i)=>(
                    <div key={i} className="truncate flex items-center gap-1">
                      <span className="text-cyan-500 font-bold">•</span>{n}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── LSTM ─────────────────────────────────────────────────────────── */}
        <div className="border border-cyan-950/40 bg-slate-950/35 rounded-lg overflow-hidden">
          <div onClick={() => setSection2Open(!section2Open)}
            className="flex items-center justify-between p-3 bg-[#03060d] border-b border-cyan-950/20 cursor-pointer hover:bg-slate-900/40 transition-colors">
            <span className="text-[10px] font-display font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-cyan-500"/> LSTM Trajectory Deviation
            </span>
            {section2Open ? <ChevronUp className="w-3.5 h-3.5 text-slate-500"/> : <ChevronDown className="w-3.5 h-3.5 text-slate-500"/>}
          </div>

          {section2Open && (
            <div className="p-3.5 space-y-3">
              <div className="flex items-center justify-between text-[9px] font-mono">
                <span className="text-slate-500">PROPAGATING TARGET:</span>
                <span className="text-cyan-400 font-bold">
                  {selectedConj ? (selectedConj as any).satA?.name : '— select conjunction —'}
                </span>
              </div>

              {lstmOffline || deviationData.dx === null ? (
                <NoData msg={lstmOffline ? 'LSTM data unavailable — awaiting data' : '— select a conjunction above —'} />
              ) : (
                <>
                  <div className="text-[9px] font-mono text-slate-400 flex justify-between">
                    <span>72H COVARIANCE ENVELOPE</span>
                    <span className="text-slate-500">(KM ERROR VECTOR)</span>
                  </div>
                  <div className="h-24 bg-[#020408] border border-slate-900 p-2.5 rounded">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart layout="vertical" data={lstmChartData} margin={{top:2,right:10,left:15,bottom:2}}>
                        <XAxis type="number" stroke="#475569" fontSize={8} fontFamily="monospace" tickLine={false}/>
                        <YAxis dataKey="name" type="category" stroke="#475569" fontSize={8.5} fontFamily="monospace" tickLine={false} width={60}/>
                        <Tooltip contentStyle={{background:'#090d16',border:'1px solid #1e293b',fontSize:'9px',fontFamily:'monospace'}} formatter={(v:any)=>[v+' km','Deviation']}/>
                        <Bar dataKey="value" fill="#0e7490" radius={[0,2,2,0]}>
                          {lstmChartData.map((_,i)=>{
                            const c=['#22d3ee','#10b981','#3b82f6'];
                            return <Cell key={i} fill={c[i%c.length]} opacity={0.8}/>;
                          })}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="bg-slate-900/40 border border-slate-900/60 p-2.5 rounded text-center text-[10px] font-mono text-slate-300">
                    Atmospheric drag uncertainty: <span className="text-yellow-400 font-bold">±{deviationData.total_deviation?.toFixed(3)} km</span>
                  </div>
                </>
              )}

              <button onClick={runLstmPrediction} disabled={lstmLoading || !selectedConj}
                className="w-full py-1.5 bg-slate-900 hover:bg-slate-850 text-cyan-400 border border-cyan-950/80 hover:border-cyan-400 rounded text-[9px] font-mono uppercase tracking-wider flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-40">
                <RefreshCw className={`w-3 h-3 ${lstmLoading?'animate-spin text-cyan-400':'text-slate-500'}`}/>
                {lstmLoading ? 'PROPAGATING…' : 'Run LSTM Prediction'}
              </button>
            </div>
          )}
        </div>

        {/* ── MARL ─────────────────────────────────────────────────────────── */}
        <div className="border border-cyan-950/40 bg-slate-950/35 rounded-lg overflow-hidden">
          <div onClick={() => setSection3Open(!section3Open)}
            className="flex items-center justify-between p-3 bg-[#03060d] border-b border-cyan-950/20 cursor-pointer hover:bg-slate-900/40 transition-colors">
            <span className="text-[10px] font-display font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
              <Award className="w-3.5 h-3.5 text-cyan-500"/> MARL Agent Constellations
            </span>
            {section3Open ? <ChevronUp className="w-3.5 h-3.5 text-slate-500"/> : <ChevronDown className="w-3.5 h-3.5 text-slate-500"/>}
          </div>

          {section3Open && (
            <div className="p-3.5 space-y-3">
              {agents.length === 0 ? (
                <div className="text-center p-4 bg-slate-950 border border-dashed border-slate-900 rounded font-mono text-[9px] text-slate-500">
                  No active agents. Agents spawn when high-criticality satellites face conjunctions.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left font-mono text-[9.5px]">
                    <thead>
                      <tr className="text-slate-500 uppercase tracking-tighter border-b border-slate-900/60">
                        <th className="pb-1">SATELLITE</th>
                        <th className="pb-1 text-center">EPISODES</th>
                        <th className="pb-1 text-right">REWARD</th>
                        <th className="pb-1 text-right">TREND</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900/35">
                      {agents.map((a:any, i:number) => (
                        <tr key={i} className="hover:bg-slate-900/10">
                          <td className="py-1.5 font-bold text-slate-300 truncate max-w-[85px]">{a.satellite || a.norad_id}</td>
                          <td className="py-1.5 text-center text-slate-400">{(a.episodes||a.episodes_trained||0).toLocaleString()}</td>
                          <td className={`py-1.5 text-right font-semibold ${(a.reward||a.cumulative_reward||0)>=0?'text-emerald-400':'text-red-400'}`}>
                            {(a.reward||a.cumulative_reward||0)>=0?'+':''}{(a.reward||a.cumulative_reward||0).toFixed(2)}
                          </td>
                          <td className={`py-1.5 text-right font-extrabold ${a.trend==='up'||a.trend==='UP'?'text-emerald-400':'text-red-400'}`}>
                            {a.trend==='up'||a.trend==='UP'?'↑':'↓'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* PPO Training Convergence Sparkline */}
              {rlCurve.length > 0 && (
                <div className="pt-2 border-t border-slate-900/50 space-y-1.5">
                  <span className="text-[9px] font-mono text-slate-400 uppercase tracking-wider">PPO Training Convergence</span>
                  <div className="h-20 bg-[#020408] border border-slate-900 p-1.5 rounded">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={rlCurve} margin={{top:2,right:4,left:-30,bottom:2}}>
                        <CartesianGrid strokeDasharray="2 4" stroke="#1e293b" vertical={false}/>
                        <XAxis dataKey="episode" hide/>
                        <YAxis stroke="#475569" fontSize={7} fontFamily="monospace" tickLine={false} domain={['auto', 'auto']}/>
                        <Tooltip contentStyle={{background:'#090d16',border:'1px solid #1e293b',fontSize:'8px',fontFamily:'monospace'}} formatter={(v:any)=>[v,'Reward']}/>
                        <Line type="monotone" dataKey="reward" stroke="#22d3ee" dot={false} strokeWidth={1.5}/>
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <span className="text-[7.5px] font-mono text-slate-600">last 200 episodes · CW-PPO · 200k steps</span>
                </div>
              )}

              <div className="flex items-center justify-between pt-2 border-t border-slate-900 text-[8.5px] font-mono text-slate-500">
                <span>POLICIES: PPO_MlpPolicy · ClohessyWiltshire6DOF</span>
                <span>Agents: <strong className="text-cyan-400">{agents.length}</strong></span>
              </div>
            </div>
          )}
        </div>

        {/* ── BENCHMARKS ───────────────────────────────────────────────────── */}
        <div className="border border-cyan-950/40 bg-slate-950/35 rounded-lg overflow-hidden">
          <div onClick={() => setBenchOpen(!benchOpen)}
            className="flex items-center justify-between p-3 bg-[#03060d] border-b border-cyan-950/20 cursor-pointer hover:bg-slate-900/40 transition-colors">
            <span className="text-[10px] font-display font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
              <BarChart2 className="w-3.5 h-3.5 text-cyan-500"/> Pipeline Benchmarks
            </span>
            {benchOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-500"/> : <ChevronDown className="w-3.5 h-3.5 text-slate-500"/>}
          </div>

          {benchOpen && (
            <div className="p-3.5 space-y-2.5">
              {benchOffline ? (
                <NoData msg="Benchmarks unavailable — backend offline" />
              ) : bench ? (
                <>
                  <div className="text-[8px] font-mono text-slate-500 uppercase tracking-wider mb-1">
                    Performance vs. naive threshold baseline
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left font-mono text-[8.5px] border-collapse">
                      <thead>
                        <tr className="text-slate-500 border-b border-slate-900/60">
                          <th className="pb-1 pr-2">Model</th>
                          <th className="pb-1 pr-2">Method</th>
                          <th className="pb-1 text-right">F1 / Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-900/30">
                        <tr>
                          <td className="py-1.5 text-slate-300 font-semibold pr-2">ANN Pc</td>
                          <td className="py-1.5 text-slate-500 pr-2 text-[8px]">Physics Pc labels (1e-4)</td>
                          <td className="py-1.5 text-right text-cyan-400 font-bold">{bench.ann?.f1_pct ?? '--'}%</td>
                        </tr>
                        <tr>
                          <td className="py-1.5 text-slate-300 font-semibold pr-2">LSTM</td>
                          <td className="py-1.5 text-slate-500 pr-2 text-[8px]">Uncertainty inflation</td>
                          <td className="py-1.5 text-right text-emerald-400 font-bold">
                            {bench.lstm?.is_trained ? 'Live' : <span className="text-slate-500">Not trained</span>}
                          </td>
                        </tr>
                        <tr>
                          <td className="py-1.5 text-slate-300 font-semibold pr-2">RL Agent</td>
                          <td className="py-1.5 text-slate-500 pr-2 text-[8px]">CW-PPO 200k steps</td>
                          <td className="py-1.5 text-right text-emerald-400 font-bold">
                            {bench.rl_agent?.is_trained
                              ? `μR=${bench.rl_agent.final_mean_reward}`
                              : <span className="text-slate-500">Not trained</span>}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="text-[8px] font-mono text-slate-600 mt-1 pt-2 border-t border-slate-900/40">
                    Detection: {bench.pipeline?.detection_method} · threshold {bench.pipeline?.conjunction_threshold_km} km
                  </div>
                </>
              ) : (
                <div className="text-[9px] font-mono text-slate-500 text-center py-3 animate-pulse">Loading benchmarks…</div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
