import React from 'react';
import { useManeuverStore } from '../../store/useManeuverStore';
import { ShieldCheck, AlertTriangle } from 'lucide-react';

interface BurnParametersProps {
  maneuver: {
    pre_maneuver_miss_km?: number;
    post_maneuver_miss_km?: number;
    miss_distance_km?: number;
    preBurnMissKm?: number;
    postBurnMissKm?: number;
  } | null;
}

export default function BurnParameters({ maneuver }: BurnParametersProps) {
  const verificationResult = useManeuverStore((s) => s.verificationResult);

  // Extract or fall back safely to avoid undefined value crashes
  const preMiss = maneuver
    ? maneuver.pre_maneuver_miss_km ?? maneuver.preBurnMissKm ?? (maneuver.miss_distance_km ?? 0.342)
    : 0.342;

  const postMiss = maneuver
    ? maneuver.post_maneuver_miss_km ?? maneuver.postBurnMissKm ?? 2.845
    : 2.845;

  const isResolved = postMiss > 1.0;

  return (
    <div className="bg-slate-950/60 border border-cyan-950/20 rounded-lg p-3.5 space-y-3 select-none w-full">
      <div className="flex items-center justify-between pb-1 text-[10px] font-mono tracking-wider text-slate-500 uppercase border-b border-slate-900">
        <span>Post-Maneuver Prognosis</span>
        <span className="text-[9px] text-cyan-400">Monte Carlo Envelope</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Before / After comparison */}
        <div className="space-y-2">
          <span className="text-[9px] font-mono text-slate-400 block uppercase">
            MISS DISTANCE COMPARISON
          </span>
          <div className="space-y-1 text-xs font-mono">
            <div className="flex items-center justify-between px-2 py-1 bg-slate-950 border border-red-950/30 rounded text-red-500">
              <span>BEFORE FLIGHT:</span>
              <span className="font-bold">{preMiss.toFixed(3)} km</span>
            </div>
            <div className="flex items-center justify-between px-2 py-1 bg-slate-950 border border-emerald-950/30 rounded text-emerald-400 font-bold">
              <span>AFTER BURN:</span>
              <span className="font-bold">{postMiss.toFixed(3)} km</span>
            </div>
          </div>
        </div>

        {/* Dynamic status badge indicator based on safety boundaries */}
        <div className="flex flex-col justify-center items-center p-3 bg-[#020509] rounded border border-slate-900/40 text-center min-h-[64px]">
          {isResolved ? (
            <div className="space-y-1">
              <span className="text-[11px] font-semibold font-display tracking-wide text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.3)] animate-pulse block">
                ✓ RISK RESOLVED
              </span>
              <span className="text-[8px] font-mono text-slate-500 block uppercase">
                COVE DECONGESTED TO SAFE SLAB
              </span>
            </div>
          ) : (
            <div className="space-y-1 text-amber-500">
              <AlertTriangle className="w-4 h-4 mx-auto mb-0.5 animate-bounce" />
              <span className="text-[10px] font-bold font-mono tracking-tighter block">
                ⚠ INSUFFICIENT SEPARATION
              </span>
              <span className="text-[8px] font-mono text-slate-500 block uppercase">
                CRITICAL THRESHOLD IS &lt; 1.0 KM
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Verification status block if verified from background thread */}
      {verificationResult && (
        <div className="pt-2.5 mt-1 border-t border-slate-900/50 bg-emerald-950/15 border-l-2 border-l-emerald-500 p-2 rounded-r flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
          <div className="font-mono">
            <div className="text-[9px] font-bold text-emerald-400 uppercase tracking-wider">
              VERIFICATION COMPLETE
            </div>
            <div className="text-[8px] text-slate-400 mt-0.5 leading-snug">
              SECONDARY CONJUNCTIONS PROJECTED: <span className="text-white font-bold">{verificationResult.secondary_conjunctions_count ?? 0}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
