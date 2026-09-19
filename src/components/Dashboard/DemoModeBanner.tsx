import React from 'react';
import { useSystemStore } from '../../store/useSystemStore';

export default function DemoModeBanner() {
  const demoMode = useSystemStore((s) => s.demoMode);
  const setDemoMode = useSystemStore((s) => s.setDemoMode);

  if (!demoMode) return null;

  return (
    <div 
      className="h-10 w-full bg-amber-500/10 border-b border-amber-500/40 px-3 flex items-center justify-between text-amber-400 select-none shrink-0 font-mono text-[9px] font-bold animate-[pulse_2s_infinite]"
      style={{
        boxShadow: "inset 0 0 10px rgba(245, 158, 11, 0.15)"
      }}
    >
      <div className="flex items-center gap-1.5 truncate">
        <span className="text-amber-500 text-xs animate-bounce shrink-0">⚡</span>
        <span className="truncate tracking-wide uppercase">
          DEMO MODE — Live CelesTrak data, synthetic high-risk conjunction pre-selected
        </span>
      </div>
      <button
        onClick={() => setDemoMode(false)}
        className="px-2 py-0.5 border border-amber-500/40 hover:border-amber-400 hover:bg-amber-500/20 text-[8px] hover:text-white rounded text-amber-500 font-extrabold transition-all cursor-pointer uppercase shrink-0"
      >
        Exit Demo
      </button>
    </div>
  );
}
