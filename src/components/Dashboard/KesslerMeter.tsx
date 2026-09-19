import React from 'react';

interface KesslerMeterProps {
  index: number;
  showFull?: boolean;
}

export default function KesslerMeter({ index = 0, showFull = false }: KesslerMeterProps) {
  // Normalize index within 0 to 100 bounds
  const normalizedIndex = Math.min(Math.max(Number(index) || 0, 0), 100);

  // Determine risk banding color classes and labels
  let riskColor = 'text-emerald-400';
  let riskBg = 'bg-emerald-500';
  let riskStroke = '#10b981';
  let riskLabel = 'LOW RISK';

  if (normalizedIndex >= 60) {
    riskColor = 'text-red-500';
    riskBg = 'bg-red-500';
    riskStroke = '#ef4444';
    riskLabel = 'CRITICAL THREAT';
  } else if (normalizedIndex >= 30) {
    riskColor = 'text-amber-500';
    riskBg = 'bg-amber-500';
    riskStroke = '#f59e0b';
    riskLabel = 'MODERATE RISK';
  }

  // Description text for tooltip
  const tooltipText = "The Kessler Syndrome risk index estimates the probability of a cascade collision event in LEO. 0 = safe, 100 = cascade imminent.";

  if (!showFull) {
    return (
      <div 
        id="kessler_meter_compact"
        className="group relative flex items-center gap-2 select-none cursor-help"
        title={tooltipText}
      >
        <span className="font-mono text-[9px] text-slate-400 font-semibold uppercase tracking-wider">
          KRI: <span className={`${riskColor} font-bold`}>{normalizedIndex.toFixed(1)}%</span>
        </span>
        <div className="w-16 h-1 w-[64px] bg-slate-800 rounded-full overflow-hidden relative">
          <div 
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{ 
              width: `${normalizedIndex}%`,
              background: 'linear-gradient(to right, #10b981, #f59e0b, #ef4444)' 
            }}
          />
        </div>

        {/* Dynamic Tooltip on Hover */}
        <div className="absolute right-0 bottom-full mb-2 hidden group-hover:flex flex-col items-center z-50">
          <div className="bg-[#0b1329] border border-cyan-800/30 p-2.5 rounded shadow-xl text-[9px] font-mono leading-normal w-[220px] text-slate-300">
            <p className="font-bold text-cyan-400 border-b border-cyan-950/40 pb-1 mb-1 uppercase tracking-wide">KESSLER CASCADE INDEX</p>
            <p className="text-slate-400 leading-relaxed">{tooltipText}</p>
          </div>
          <div className="w-2 h-2 bg-[#0b1329] border-r border-b border-cyan-800/30 transform rotate-45 -mt-1" />
        </div>
      </div>
    );
  }

  // Full representation: SVG Radial Gauge
  const radius = 70;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius; // Outer circle circumference (439.82)
  const strokeDashoffset = circumference - (normalizedIndex / 100) * circumference;

  return (
    <div 
      id="kessler_meter_full"
      className="group relative flex flex-col items-center justify-center p-4 bg-[#080d19]/60 border border-cyan-950/45 rounded-lg select-none cursor-help"
    >
      {/* SVG radial tracking gauge inside box */}
      <div className="w-[180px] h-[180px] relative flex items-center justify-center">
        <svg viewBox="0 0 200 200" className="w-full h-full transform -rotate-90">
          {/* Track background */}
          <circle
            cx="100"
            cy="100"
            r={radius}
            stroke="#1a2340"
            strokeWidth={strokeWidth}
            fill="transparent"
            strokeOpacity={0.4}
          />
          {/* Track progressive fill */}
          <circle
            cx="100"
            cy="100"
            r={radius}
            stroke={riskStroke}
            strokeWidth={strokeWidth}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>

        {/* Core numbers absolute centered overlay */}
        <div className="absolute top-0 left-0 w-full h-full flex flex-col items-center justify-center font-mono">
          <span className="text-3xl font-extrabold text-white tracking-tight">
            {normalizedIndex.toFixed(1)}
          </span>
          <span className="text-[10px] text-slate-500 mt-0.5">/ 100 %</span>
        </div>
      </div>

      {/* Accompanying labels at bottom */}
      <div className="text-center mt-1">
        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest font-display">
          KESSLER RISK INDEX
        </div>
        <div className={`text-xs font-extrabold font-mono tracking-wider mt-1 ${riskColor}`}>
          ● {riskLabel}
        </div>
      </div>

      {/* Overlay Styled Tooltip */}
      <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 hidden group-hover:flex flex-col items-center z-50">
        <div className="w-3 h-3 bg-[#0b1329] border-l border-t border-cyan-800/30 transform rotate-45 -mb-1.5" />
        <div className="bg-[#0b1329] border border-cyan-800/30 p-3 rounded-lg shadow-2xl text-[9px] font-mono leading-normal w-[240px] text-slate-300">
          <p className="font-bold text-cyan-400 border-b border-cyan-950/40 pb-1 mb-1.5 uppercase tracking-wider">KESSLER CASCADE INDEX</p>
          <p className="text-slate-400 leading-relaxed">{tooltipText}</p>
        </div>
      </div>
    </div>
  );
}
