import React from 'react';
import { formatDistanceToNow } from 'date-fns';
import RiskBadge from './RiskBadge';

interface SatelliteSimple {
  id?: string;
  name?: string;
  type?: string;
  owner?: string;
}

interface ConjunctionCardProps {
  conjunction: {
    id: string;
    event_id: string;
    name_a?: string;
    name_b?: string;
    satA?: SatelliteSimple;
    satB?: SatelliteSimple;
    tca?: string;
    tca_utc?: string;
    missDistance?: number;
    miss_distance_km?: number;
    riskProbability?: number;
    collision_probability_chan?: number;
    status?: string;
    risk_level?: string;
    resolved?: boolean;
    object_type_a?: string;
    object_type_b?: string;
  };
  isSelected: boolean;
  onClick: (eventId: string) => void;
}

// Map common owners to country emojis
const getOwnerFlag = (owner?: string): string => {
  if (!owner) return '🌐';
  const o = owner.toUpperCase();
  if (o.includes('SPACEX') || o.includes('NASA') || o.includes('USSPACECOM') || o.includes('GPS') || o.includes('USA')
    || o.includes('STARLINK') || o.includes('TERRA') || o.includes('AQUA') || o.includes('LANDSAT')) {
    return '🇺🇸';
  }
  if (o.includes('ESA') || o.includes('EUROPE')) {
    return '🇪🇺';
  }
  if (o.includes('ROSCOSMOS') || o.includes('COSMOS') || o.includes('RUSSIA')) {
    return '🇷🇺';
  }
  if (o.includes('ISRO') || o.includes('INDIA')) {
    return '🇮🇳';
  }
  if (o.includes('ONEWEB') || o.includes('UK') || o.includes('UNITED KINGDOM')) {
    return '🇬🇧';
  }
  if (o.includes('CNES') || o.includes('FRANCE')) {
    return '🇫🇷';
  }
  if (o.includes('JAXA') || o.includes('JAPAN')) {
    return '🇯🇵';
  }
  if (o.includes('ASAL') || o.includes('ALGERIA')) {
    return '🇩🇿';
  }
  return '🌐'; // known fallback — always shows something instead of N/A
};

const truncateName = (name: string, maxLen = 16): string => {
  if (!name) return 'UNKNOWN';
  if (name.length <= maxLen) return name;
  return name.slice(0, maxLen - 1) + '…';
};

const ConjunctionCard: React.FC<ConjunctionCardProps> = ({ conjunction, isSelected, onClick }) => {
  const nameA = conjunction.name_a || conjunction.satA?.name || 'UNKNOWN';
  const nameB = conjunction.name_b || conjunction.satB?.name || 'UNKNOWN';

  const truncA = truncateName(nameA, 16);
  const truncB = truncateName(nameB, 16);

  const riskLevel = conjunction.status || conjunction.risk_level || 'MEDIUM';
  const isResolved = conjunction.resolved || riskLevel === 'RESOLVED';

  // Get risk level color for border-left
  let borderLeftColor = '#00D4FF'; // LOW
  if (isResolved) {
    borderLeftColor = '#10b981'; // RESOLVED / SAFE (green)
  } else if (riskLevel === 'CRITICAL') {
    borderLeftColor = '#FF2D55';
  } else if (riskLevel === 'HIGH') {
    borderLeftColor = '#FF6B35';
  } else if (riskLevel === 'MEDIUM') {
    borderLeftColor = '#FFB800';
  }

  // Row 2 displays
  const missDist = conjunction.miss_distance_km !== undefined 
    ? `${conjunction.miss_distance_km.toFixed(2)} km` 
    : conjunction.missDistance !== undefined 
      ? `${conjunction.missDistance.toFixed(0)} m` 
      : '0 m';

  // TCA Countdown
  const tcaValue = conjunction.tca_utc || conjunction.tca;
  let tcaCountdown = 'TCA elapsed';
  if (tcaValue) {
    try {
      const tcaDate = new Date(tcaValue);
      const isFuture = tcaDate.getTime() > Date.now();
      if (isFuture) {
        tcaCountdown = `TCA in ${formatDistanceToNow(tcaDate)}`;
      } else {
        tcaCountdown = `${formatDistanceToNow(tcaDate)} ago`;
      }
    } catch (_) {
      tcaCountdown = 'TCA Unknown';
    }
  }

  const prob = conjunction.collision_probability_chan ?? conjunction.riskProbability ?? 1e-5;
  const probFormatted = prob.toExponential(2);

  // Row 3 flags and types
  const typeA = conjunction.object_type_a || conjunction.satA?.type || 'PAYLOAD';
  const typeB = conjunction.object_type_b || conjunction.satB?.type || 'DEBRIS';

  const flagA = getOwnerFlag(conjunction.satA?.owner || conjunction.object_type_a || conjunction.name_a || '');
  const flagB = getOwnerFlag(conjunction.satB?.owner || conjunction.object_type_b || conjunction.name_b || '');

  return (
    <div
      id={`conj_card_${conjunction.event_id}`}
      onClick={() => onClick(conjunction.event_id)}
      style={{
        backgroundColor: isSelected ? '#1a2340' : '#0f1629',
        borderLeft: `4px solid ${borderLeftColor}`
      }}
      className="p-3 mb-2 rounded transition-all duration-200 cursor-pointer hover:brightness-110 active:scale-[0.99] select-none shadow-md border-r border-t border-b border-cyan-950/10 flex flex-col gap-2 relative overflow-hidden animate-[fadeIn_0.3s_ease-out]"
    >
      {/* Row 1: Terminating targets name flow -> Risk severity */}
      <div className="flex items-center justify-between gap-1 w-full">
        <div className="flex items-center gap-1.5 font-mono text-[10px] font-bold text-slate-100 truncate flex-1">
          <span className="truncate">{truncA}</span>
          <span className="text-slate-500 text-[8px] font-normal shrink-0">→</span>
          <span className="truncate">{truncB}</span>
        </div>
        <RiskBadge level={riskLevel} />
      </div>

      {/* Row 2: Diagnostic metrics row */}
      <div className="flex items-center justify-between text-[9px] font-mono">
        <div className="flex items-center gap-1">
          <span className="text-cyan-400 font-extrabold">{missDist}</span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-400 font-medium">{tcaCountdown}</span>
        </div>
        <div className="text-right">
          <span className="text-slate-500">Pc:</span>{' '}
          <span className="font-extrabold text-red-400">{probFormatted}</span>
        </div>
      </div>

      {/* Row 3: Target types, country flag references */}
      <div className="flex items-center justify-between font-mono text-[8.5px] border-t border-cyan-950/30 pt-1.5 mt-0.5">
        <div className="flex items-center justify-between font-mono text-[8.5px] border-t border-[#1a2340]/40 pt-1.5 mt-0.5">
          <div className="flex items-center gap-1.5 text-slate-400">
            <span className="flex items-center gap-1 px-1 py-0.2 bg-slate-900 rounded border border-cyan-950/20">
              {flagA && <span className="text-[10px] select-none">{flagA}</span>}
              <span className="text-slate-400 tracking-tight text-[8px] uppercase">{typeA}</span>
            </span>
            <span className="text-slate-600 font-normal">vs</span>
            <span className="flex items-center gap-1 px-1 py-0.2 bg-slate-900 rounded border border-cyan-950/20">
              {flagB && <span className="text-[10px] select-none">{flagB}</span>}
              <span className="text-slate-400 tracking-tight text-[8px] uppercase">{typeB}</span>
            </span>
          </div>

          <span className="text-[7.5px] text-slate-500 font-bold tracking-tight">ID: {conjunction.event_id.replace('CONJ-2026-', '#')}</span>
        </div>
      </div>
    </div>
  );
};

export default ConjunctionCard;
