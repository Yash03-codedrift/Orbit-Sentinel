import React from 'react';
import { useRiskConfigStore } from '../../store/useRiskConfigStore';

interface RiskBadgeProps {
  level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NEGLIGIBLE' | 'RESOLVED' | string;
}

export default function RiskBadge({ level }: RiskBadgeProps) {
  const normLevel = String(level).toUpperCase();
  const bandsByKey = useRiskConfigStore((s) => s.bandsByKey);

  let styles = 'bg-[#0f1629] text-gray-400 border border-transparent';
  let inlineStyle: React.CSSProperties | undefined;

  if (normLevel === 'CRITICAL') {
    styles = 'bg-[#FF2D55] text-white font-extrabold animate-pulse shadow-[0_0_8px_rgba(255,45,85,0.4)]';
  } else if (normLevel === 'HIGH') {
    styles = 'bg-[#FF6B35] text-white font-bold';
  } else if (normLevel === 'MEDIUM') {
    styles = 'bg-[#FFB800] text-black font-semibold';
  } else if (normLevel === 'LOW') {
    styles = 'bg-[#1a2340] text-[#00D4FF] border border-cyan-800/30';
  } else if (normLevel === 'NEGLIGIBLE') {
    styles = 'bg-[#0f1629] text-gray-500 border border-transparent';
  } else if (normLevel === 'RESOLVED' || normLevel === 'SAFE') {
    styles = 'bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 font-semibold';
  } else if (bandsByKey[normLevel]) {
    // Custom / renamed band configured via the Risk Config panel — use its stored color.
    styles = 'font-bold';
    inlineStyle = { backgroundColor: bandsByKey[normLevel].color, color: '#0a0f1e' };
  }

  return (
    <span 
      id={`risk_badge_${normLevel}`}
      style={inlineStyle}
      className={`px-2 py-0.5 rounded text-[8px] tracking-wider uppercase font-mono ${styles} shrink-0 max-h-min inline-flex items-center justify-center`}
    >
      {normLevel}
    </span>
  );
}
