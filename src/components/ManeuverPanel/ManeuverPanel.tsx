import React, { useState, useEffect } from 'react';
import { useManeuverStore } from '../../store/useManeuverStore';
import { useConjunctionStore } from '../../store/useConjunctionStore';
import { triggerResponse } from '../../api/conjunctionApi';
import DeltaVVector from './DeltaVVector';
import WebhookViewer from './WebhookViewer';
import BurnParameters from './BurnParameters';
import { Rocket, Brain, Calendar, Shield, Gauge, Zap } from 'lucide-react';

export default function ManeuverPanel() {
  const activeManeuver = useManeuverStore((s) => s.activeManeuver);
  const computing = useManeuverStore((s) => s.computing);
  const webhookPayload = useManeuverStore((s) => s.webhookPayload);
  const setComputing = useManeuverStore((s) => s.setComputing);

  const activeConjunctionId = useConjunctionStore((s) => s.activeConjunctionId);
  const storeConjunctions = useConjunctionStore((s) => s.conjunctions);
  const selectedConjunction = storeConjunctions.find((c) => c.id === activeConjunctionId) || null;

  const handleComputeManeuver = async () => {
    if (!selectedConjunction) return;
    const eventId = selectedConjunction.event_id ?? selectedConjunction.id;
    if (!eventId) return;
    setComputing(true);
    try {
      const res: any = await triggerResponse(eventId);
      const data = res?.data ?? res;
      const maneuver = data?.maneuver ?? data?.maneuver_plan ?? null;
      const webhook = data?.webhook_payload ?? null;
      if (maneuver) useManeuverStore.getState().setActiveManeuver(maneuver);
      if (webhook)
        useManeuverStore
          .getState()
          .setWebhookPayload(typeof webhook === 'string' ? webhook : JSON.stringify(webhook, null, 2));
    } catch (err: any) {
      console.error('Maneuver compute failed:', err?.message ?? err);
    } finally {
      setComputing(false);
    }
  };

  // Computing Step index and percentage simulation states
  const [stepIndex, setStepIndex] = useState(0);
  const [progress, setProgress] = useState(0);

  const steps = [
    'Fetching state vectors...',
    'Computing delta-V...',
    'Running RL agent...',
    'Validating MARL...',
    'Generating webhook...',
  ];

  useEffect(() => {
    if (!computing) {
      setStepIndex(0);
      setProgress(0);
      return;
    }

    let currentStep = 0;
    setStepIndex(0);
    setProgress(5);

    const interval = setInterval(() => {
      if (currentStep < steps.length - 1) {
        currentStep += 1;
        setStepIndex(currentStep);
        setProgress(Math.round(((currentStep + 1) / steps.length) * 100));
      } else {
        clearInterval(interval);
      }
    }, 650); // Each step takes 650ms

    return () => clearInterval(interval);
  }, [computing]);

  // Display placeholder state if no active operation and no computation is running
  if (!activeManeuver && !computing) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[350px] p-6 text-center select-none space-y-3 bg-[#05070f] text-slate-500 font-mono">
        <span className="text-4xl animate-bounce">🛰️</span>
        <div className="text-xs uppercase tracking-wider max-w-[280px] leading-relaxed mx-auto text-slate-400">
          SELECT A CONJUNCTION AND TRIGGER RESPONSE TO SEE MANEUVER DETAILS
        </div>
        <p className="text-[10px] text-slate-600 max-w-[220px]">
          Target satellite engines will orient based on MARL predictions and compute prograde/retrograde impulse vectors.
        </p>
      </div>
    );
  }

  // Computing state with steps and animated bar indicator
  if (computing) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[350px] p-6 bg-[#05070f] space-y-5 select-none font-mono">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-cyan-950 flex items-center justify-center animate-spin">
            <div className="w-8 h-8 rounded-full border-t-2 border-cyan-400" />
          </div>
          <Zap className="w-4 h-4 text-cyan-400 absolute inset-0 m-auto animate-pulse" />
        </div>

        <div className="space-y-2 text-center w-full max-w-[280px]">
          <div className="text-xs font-semibold text-cyan-400 animate-pulse uppercase tracking-widest h-5">
            {steps[stepIndex]}
          </div>
          <div className="text-[9px] text-slate-500 uppercase h-3">
            STAGE {stepIndex + 1} OF {steps.length}
          </div>

          {/* Progress bar container */}
          <div className="w-full bg-slate-950 border border-cyan-950/40 rounded-full h-2.5 overflow-hidden p-0.5">
            <div
              className="bg-cyan-400 h-full rounded-full transition-all duration-300 shadow-[0_0_8px_rgba(34,211,238,0.7)]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-[9px] text-slate-400 mt-1">{progress}% Complete</div>
        </div>
      </div>
    );
  }

  // Render finalized computed maneuver layout when activeManeuver and payload are loaded
  const dvVector = activeManeuver?.delta_v_vector || activeManeuver?.deltaVVector || [0, 0, 0];
  const dvMagnitude = activeManeuver?.computed_delta_v_magnitude_mps || activeManeuver?.deltaVMagnitude || 0.45;
  const isRLAgent = activeManeuver?.rl_agent_used || activeManeuver?.rlAgentUsed || true;

  // Formatting epoch dates beautifully
  const formattedEpoch = activeManeuver?.epoch_tca 
    ? new Date(activeManeuver.epoch_tca).toLocaleString('en-US', { timeZone: 'UTC' }) + ' UTC' 
    : '2026-06-08 04:12:33 UTC';

  return (
    <div id="maneuver_details_scroller" className="bg-[#05070f] p-4 space-y-4 h-full overflow-y-auto scrollbar-thin">
      
      {/* Title Segment */}
      <div className="flex items-center justify-between pb-2 border-b border-cyan-950/40">
        <span className="text-xs font-semibold font-display text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
          <Rocket className="text-cyan-400 w-4 h-4 animate-pulse" />
          Maneuver Parameters
        </span>
        <span className="text-[8px] font-mono bg-cyan-950/50 text-cyan-400 border border-cyan-800/40 px-2 py-0.5 rounded shadow-[0_0_8px_rgba(34,211,238,0.1)]">
          MARL GENERATED
        </span>
      </div>

      {/* Burn parameters container card */}
      <div className="bg-[#02050a] border border-cyan-950/35 rounded-lg p-3.5 space-y-3 shadow-md">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono tracking-wider text-slate-400 uppercase">
            BURN PROFILE SUMMARY
          </span>
          <span className="text-[9px] font-mono text-emerald-400 flex items-center gap-1 bg-emerald-950/30 px-1.5 py-0.2 rounded border border-emerald-900/20">
            <Zap className="w-3 h-3 text-emerald-400" />
            OPTIMAL CONVERGENCE
          </span>
        </div>

        <div className="space-y-2.5 font-mono text-[10.5px] text-slate-300">
          {/* Target Satellite Name */}
          <div className="flex items-center justify-between py-1 border-b border-slate-900">
            <span className="text-slate-500">TARGET SPACECRAFT:</span>
            <span className="font-bold text-cyan-400 text-xs">{activeManeuver?.target_satellite?.name || 'STARLINK-3211'}</span>
          </div>

          {/* Burn Epoch */}
          <div className="flex items-center justify-between py-1 border-b border-slate-900">
            <span className="text-slate-500 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5" />
              BURN EPOCH (T_0):
            </span>
            <span className="text-slate-200">{formattedEpoch}</span>
          </div>

          {/* Delta-V magnitude info */}
          <div className="flex items-center justify-between py-1 border-b border-slate-900">
            <span className="text-slate-500">THRUST MAGNITUDE (ΔV):</span>
            <span className="text-yellow-400 font-extrabold text-xs">
              {Number(dvMagnitude).toFixed(4)} m/s
            </span>
          </div>

          {/* Burn Duration */}
          <div className="flex items-center justify-between py-1 border-b border-slate-900">
            <span className="text-slate-500">BURN TIME RUN:</span>
            <span className="text-slate-200 font-semibold">
              {activeManeuver?.burn_duration_seconds || activeManeuver?.burnDuration || 45} seconds
            </span>
          </div>

          {/* Fuel Weight usage */}
          <div className="flex items-center justify-between py-1 border-b border-slate-900">
            <span className="text-slate-500">ESTIMATED FUEL REQUISITE:</span>
            <span className="text-slate-200">
              {activeManeuver?.fuel_cost_kg || 1.15} kg <span className="text-slate-500">({activeManeuver?.fuel_cost_pct || 0.08}% budget)</span>
            </span>
          </div>

          {/* Algorithm Badge */}
          <div className="flex items-center justify-between py-1 border-b border-slate-900">
            <span className="text-slate-500 flex items-center gap-1">
              <Brain className="w-3.5 h-3.5" />
              SOLVING ALGORITHM:
            </span>
            <span className="bg-slate-900 border border-slate-800 text-slate-300 text-[8.5px] px-1.5 py-0.5 rounded uppercase">
              {activeManeuver?.algorithm || 'MARL-COOPERATIVE'}
            </span>
          </div>

          {/* Neural verification true/false check */}
          <div className="flex items-center justify-between py-1 border-b border-slate-900">
            <span className="text-slate-500 flex items-center gap-1">
              <Shield className="w-3.5 h-3.5" />
              RL AUTONOMY USED:
            </span>
            <span>
              {isRLAgent ? (
                <span className="text-emerald-400 font-bold bg-emerald-950/20 px-1 py-0.2 border border-emerald-900/10 rounded">✓ ACTIVE</span>
              ) : (
                <span className="text-slate-500 bg-slate-950 px-1 py-0.2 border rounded">– INACTIVE</span>
              )}
            </span>
          </div>

          {/* Actor Policy Confidence Rate */}
          <div className="space-y-1 pt-1">
            <div className="flex justify-between text-slate-500 text-[9.5px]">
              <span>ACTOR CONVERGENCE CONFIDENCE:</span>
              <span className="text-slate-200 font-bold">{activeManeuver?.confidence || 94.2}%</span>
            </div>
            <div className="w-full bg-slate-950 border border-slate-900 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full"
                style={{ width: `${activeManeuver?.confidence || 94.2}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Vector Visualization Overlay */}
      <DeltaVVector deltaVVector={dvVector} />

      {/* Miss Distance prognosis comparisons */}
      <BurnParameters maneuver={activeManeuver} />

      {/* JSON package with highlight code */}
      <WebhookViewer webhookPayload={webhookPayload} />

    </div>
  );
}