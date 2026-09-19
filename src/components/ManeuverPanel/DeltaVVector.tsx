import React, { useMemo } from 'react';

interface DeltaVVectorProps {
  deltaVVector: number[]; // [dv_x, dv_y, dv_z] in m/s
}

export default function DeltaVVector({ deltaVVector }: DeltaVVectorProps) {
  // Safe extraction of coordinates
  const [dvx, dvy, dvz] = useMemo(() => {
    if (!Array.isArray(deltaVVector) || deltaVVector.length < 3) return [0, 0, 0];
    return deltaVVector.map((val) => (typeof val === 'number' && !isNaN(val) ? val : 0));
  }, [deltaVVector]);

  // Center coordinate of SVG container (200x200 pixel boundaries)
  const cx = 100;
  const cy = 100;

  // Maximum magnitude coordinate scaling offset
  const scale = 80;

  // Compute ending coordinates of the delta-v thrust action arrow
  // dvx maps to horizontal (Prograde), dvy/dvz to vertical and depth
  const arrowEnd = useMemo(() => {
    const mag = Math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz);
    if (mag === 0) return { x: cx, y: cy };

    // Standard projection onto SVG 2D layout plane
    // X goes right positive. Y goes upwards positive (hence subtraction)
    const factor = mag > 1.0 ? 1.0 : mag; // bounds scaling
    const targetX = cx + (dvx / (mag || 1)) * factor * scale;
    const targetY = cy - (dvy / (mag || 1)) * factor * scale;

    return { x: targetX, y: targetY };
  }, [dvx, dvy, dvz]);

  const formatting = (val: number) => {
    return (val >= 0 ? '+' : '') + val.toFixed(2);
  };

  return (
    <div className="flex flex-col items-center bg-slate-950/65 border border-cyan-950/40 p-4 rounded-lg shadow-inner select-none w-full">
      <span className="text-[10px] font-mono tracking-widest text-slate-500 mb-2 uppercase">
        DELTA-V VECTOR (ECI FRAME)
      </span>

      <svg width="200" height="200" className="bg-[#02050b] rounded border border-slate-900/60 shadow-lg">
        <defs>
          {/* Cyan Grid Reference Circles */}
          <radialGradient id="grid-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#083344" stopOpacity="0" />
            <stop offset="100%" stopColor="#083344" stopOpacity="0.15" />
          </radialGradient>
          {/* Custom Yellow Line Marker head */}
          <marker
            id="v-arrow"
            viewBox="0 0 10 10"
            refX="6"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#facc15" />
          </marker>
        </defs>

        {/* Outer radial boundary glow */}
        <circle cx={cx} cy={cy} r="90" fill="url(#grid-grad)" stroke="#0e7490" strokeWidth="0.5" strokeDasharray="3 3" />
        <circle cx={cx} cy={cy} r="50" fill="none" stroke="#155e75" strokeWidth="0.5" strokeDasharray="2 4" />

        {/* 1. X Axis (Prograde) - Color Red */}
        <line x1={cx} y1={cy} x2="180" y2="100" stroke="#ef4444" strokeWidth="1" strokeDasharray="1 1" />
        <path d="M 180 97 L 186 100 L 180 103 Z" fill="#ef4444" />
        <text x="188" y="103" fill="#ef4444" className="text-[9px] font-mono font-bold">X</text>

        {/* 2. Y Axis (Cross-track) - Color Green */}
        <line x1={cx} y1={cy} x2="100" y2="20" stroke="#22c55e" strokeWidth="1" strokeDasharray="1 1" />
        <path d="M 97 20 L 100 14 L 103 20 Z" fill="#22c55e" />
        <text x="100" y="11" fill="#22c55e" className="text-[9px] font-mono font-bold text-center" textAnchor="middle">Y</text>

        {/* 3. Z Axis (Radial - Out of plane indicator) - Color Blue */}
        <line x1={cx} y1={cy} x2="40" y2="160" stroke="#3b82f6" strokeWidth="1" strokeDasharray="1 1" />
        <circle cx="40" cy="160" r="2.5" fill="#3b82f6" />
        <text x="30" y="171" fill="#3b82f6" className="text-[9px] font-mono font-bold">Z</text>

        {/* 4. Origin Dot */}
        <circle cx={cx} cy={cy} r="3" fill="#475569" />

        {/* 5. Actual Delta-V Thrust Burn Arrow */}
        {(dvx !== 0 || dvy !== 0 || dvz !== 0) && (
          <line
            x1={cx}
            y1={cy}
            x2={arrowEnd.x}
            y2={arrowEnd.y}
            stroke="#facc15"
            strokeWidth="2.5"
            markerEnd="url(#v-arrow)"
          />
        )}
      </svg>

      <div className="mt-3 space-y-1 w-full text-center">
        <div className="text-[11px] font-mono font-bold text-yellow-400">
          ΔV Component: {formatting(dvx)}x, {formatting(dvy)}y, {formatting(dvz)}z m/s
        </div>
        <div className="text-[9px] font-mono text-slate-500 uppercase">
          MAGNITUDE: {Math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz).toFixed(4)} m/s
        </div>
      </div>
    </div>
  );
}
