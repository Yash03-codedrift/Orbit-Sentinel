import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Check, Loader2 } from 'lucide-react';

interface ComputationProgressProps {
  steps: string[];
  currentStep: number;
  isComplete: boolean;
}

export default function ComputationProgress({ steps, currentStep, isComplete }: ComputationProgressProps) {
  // Compute progress percentage
  // steps.length steps. If currentStep goes from 1 to steps.length.
  let progressPercent = 0;
  if (isComplete) {
    progressPercent = 100;
  } else if (currentStep > 0) {
    progressPercent = Math.min(100, (currentStep / steps.length) * 100);
  }

  return (
    <div className="bg-slate-950/95 border border-cyan-950/40 p-4 rounded-lg space-y-3 font-mono text-[10px] text-cyan-400 max-w-full">
      <div className="flex items-center justify-between font-bold text-[11px] pb-1.5 border-b border-cyan-950/50">
        <span className="tracking-wider text-slate-300 uppercase">SOLVING STEWARDSHIP VECTORS</span>
        <span className={isComplete ? "text-emerald-400 font-extrabold animate-pulse" : "animate-pulse text-cyan-400"}>
          {isComplete ? "RESOLVED ✓" : "RUNNING MODEL..."}
        </span>
      </div>

      <div className="space-y-2 select-none pt-1">
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const isDone = isComplete || currentStep > stepNumber;
          const isCurrent = !isComplete && currentStep === stepNumber;

          return (
            <div key={index} className="flex items-center gap-2.5">
              <div className="shrink-0 flex items-center justify-center w-4 h-4 rounded-full border border-cyan-950 bg-[#04060c]">
                {isDone ? (
                  <Check className="w-2.5 h-2.5 text-emerald-400" />
                ) : isCurrent ? (
                  <Loader2 className="w-2.5 h-2.5 text-cyan-400 animate-spin" />
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-700" />
                )}
              </div>
              <span className={`leading-tight flex-1 ${
                isDone ? 'text-slate-500 line-through decoration-slate-600/30' : isCurrent ? 'text-white font-semibold' : 'text-slate-600'
              }`}>
                {stepNumber}. {step}
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden border border-cyan-950/20 relative mt-2">
        <motion.div
          className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${progressPercent}%` }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        />
      </div>

      {/* Response Generated Alert Block */}
      <AnimatePresence>
        {isComplete && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="mt-3.5 p-3 bg-emerald-950/30 border border-emerald-500/40 rounded-md flex flex-col items-center justify-center text-center space-y-1"
          >
            <div className="text-emerald-400 font-black text-xs uppercase tracking-wider flex items-center gap-1.5">
              <Check className="w-4 h-4 text-emerald-400 animate-bounce" />
              RESPONSE GENERATED ✓
            </div>
            <span className="text-[8.5px] text-slate-400 uppercase leading-normal max-w-[250px]">
              AUTONOMOUS CORRECTION COMMITTED TO SPACECRAFT TELEMETRY WITH SUCCESSFUL EPSILON CLEARANCE VERIFIED.
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
