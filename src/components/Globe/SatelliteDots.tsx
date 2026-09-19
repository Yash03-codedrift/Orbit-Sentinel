import React, { useMemo, useRef, useEffect, useState, useCallback } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import { useGlobeStore } from '../../store/useGlobeStore';

interface SatellitePosition {
  norad_id?: string;
  noradId?: string;
  id?: string;
  lat: number;
  lon: number;
  lng?: number;
  alt: number;
  object_type?: string;
  type?: string;
  criticality_score?: number;
  name: string;
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

interface SatelliteDotsProps {
  positions: SatellitePosition[];
  showOrbits?: boolean;
  conjunctionPairs?: Array<{ norad_id_a: string; norad_id_b: string; risk_level?: string }>;
  highlightedOrbitIds?: string[];
}

// Convert lat/lon/alt to normalised 3D position on unit-ish sphere
function latLonAltToXYZ(lat: number, lon: number, alt: number): [number, number, number] {
  const r = 1.0 + alt / 6371.0;
  const latRad = (lat * Math.PI) / 180;
  const lonRad = (lon * Math.PI) / 180;
  return [
    r * Math.cos(latRad) * Math.cos(lonRad),
    r * Math.sin(latRad),
    r * Math.cos(latRad) * Math.sin(lonRad),
  ];
}

function getSatColor(sat: SatellitePosition, isConjunction: boolean, conjRisk?: string, isHighlighted?: boolean): string {
  if (isHighlighted) return '#ffffff';
  if (isConjunction) {
    return conjRisk === 'CRITICAL' ? '#ff0000' : '#ffaa00';
  }
  const type = sat.object_type || sat.type || 'PAYLOAD';
  if (type === 'DEBRIS') return '#ff5a1f';
  if (type === 'ROCKET_BODY') return '#ff8c42';
  return '#00d4ff';
}

// Separate component for the selected satellite with a pulsing ring
function SelectedSatellite({ sat, onDeselect }: { sat: SatellitePosition; onDeselect: () => void }) {
  const ringRef = useRef<THREE.Mesh>(null);
  const pos = useMemo<[number, number, number]>(
  () => latLonAltToXYZ(sat.lat, sat.lon ?? (sat as any).lng ?? 0, sat.alt),
  [sat.lat, sat.lon, (sat as any).lng, sat.alt]
);

  useFrame((state) => {
    if (ringRef.current) {
      const t = state.clock.getElapsedTime();
      const scale = 1.0 + 0.4 * Math.sin(t * 3);
      ringRef.current.scale.setScalar(scale);
      (ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.3 + 0.2 * Math.sin(t * 3);
    }
  });

  return (
    <group position={pos}>
      {/* Main satellite body */}
      <mesh onClick={(e) => { e.stopPropagation(); onDeselect(); }}>
        <sphereGeometry args={[0.013, 8, 8]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      {/* Pulsing ring */}
      <mesh ref={ringRef}>
        <sphereGeometry args={[0.022, 12, 12]} />
        <meshBasicMaterial color="#00d4ff" transparent opacity={0.35} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* Tooltip */}
      <Html distanceFactor={4} position={[0, 0.05, 0]} center>
        <div className="bg-[#040814]/95 border border-cyan-400 px-2 py-0.5 rounded text-[8px] font-mono font-bold text-cyan-400 uppercase shadow-[0_0_12px_rgba(34,211,238,0.5)] whitespace-nowrap select-none flex items-center gap-1">
          <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping shrink-0" />
          🎯 LOCK: {sat.name}
        </div>
      </Html>
    </group>
  );
}

export default function SatelliteDots({ positions, showOrbits = true, conjunctionPairs = [], highlightedOrbitIds = [] }: SatelliteDotsProps) {
  const selectedSatelliteId = useGlobeStore((s) => s.selectedSatelliteId);
  const setSelectedSatellite = useGlobeStore((s) => s.setSelectedSatellite);
  const satelliteSpeed = useGlobeStore((s) => s.satelliteSpeed);
  const { camera, raycaster } = useThree();

  // Build conjunction lookup for O(1) access
  const conjunctionSet = useMemo(() => {
    const m = new Map<string, string>(); // norad_id -> risk_level
    for (const pair of conjunctionPairs) {
      m.set(pair.norad_id_a, pair.risk_level || 'HIGH');
      m.set(pair.norad_id_b, pair.risk_level || 'HIGH');
    }
    return m;
  }, [conjunctionPairs]);

  // Build highlighted orbit set for O(1) lookup
  const highlightedSet = useMemo(() => new Set(highlightedOrbitIds), [highlightedOrbitIds]);

  // Separate selected satellite from the rest
  const { selectedSat, regularSats } = useMemo(() => {
    let selectedSat: SatellitePosition | null = null;
    const regularSats: SatellitePosition[] = [];
    for (const sat of positions) {
      const id = sat.norad_id || sat.noradId || sat.id || '';
      if (id === selectedSatelliteId) {
        selectedSat = sat;
      } else {
        regularSats.push(sat);
      }
    }
    return { selectedSat, regularSats };
  }, [positions, selectedSatelliteId]);

  // Build color groups: debris (orange), rocket_body (amber), conjunction (red/amber), payload (cyan)
  type ColorGroup = { color: string; indices: number[] };

  const colorGroups = useMemo<ColorGroup[]>(() => {
    const groups: Record<string, { color: string; indices: number[] }> = {};
    regularSats.forEach((sat, i) => {
      const id = sat.norad_id || sat.noradId || sat.id || '';
      const conjRisk = conjunctionSet.get(id);
      const isHighlighted = highlightedSet.has(id);
      const color = getSatColor(sat, !!conjRisk, conjRisk, isHighlighted);
      if (!groups[color]) groups[color] = { color, indices: [] };
      groups[color].indices.push(i);
    });
    return Object.values(groups);
  }, [regularSats, conjunctionSet, highlightedSet]);

  // One InstancedMesh per color group
  const meshRefs = useRef<(THREE.InstancedMesh | null)[]>([]);

  const instancedGeometry = useMemo(() => new THREE.SphereGeometry(0.007, 5, 5), []);

  // Build matrices per color group
  const groupData = useMemo(() => {
    return colorGroups.map(group => {
      const matrices: THREE.Matrix4[] = [];
      const mat = new THREE.Matrix4();
      for (const si of group.indices) {
        const sat = regularSats[si];
        const [x, y, z] = latLonAltToXYZ(sat.lat, sat.lon ?? (sat as any).lng ?? 0, sat.alt);
        mat.identity();
        mat.setPosition(x, y, z);
        matrices.push(mat.clone());
      }
      return { color: group.color, matrices, satIndices: group.indices };
    });
  }, [regularSats, colorGroups]);

  // ── Continuous orbital animation ───────────────────────────────────────────
  // Each satellite gets a fixed orbital plane derived from its lat/lon at poll
  // time. We store p̂ (position unit vec at epoch), q̂ (90° ahead in orbit),
  // orbital radius r, angular velocity ω (Kepler), and the absolute epoch time t0.
  // Every frame: θ = ω * (now - t0),  pos = r*(cosθ·p̂ + sinθ·q̂)
  // t0 is NEVER reset between polls — motion is continuous forever.

  interface OrbitalPlane {
    px: number; py: number; pz: number; // unit vec at epoch
    qx: number; qy: number; qz: number; // unit vec 90° prograde
    r: number;     // orbital radius in Three.js units
    omega: number; // rad/s from Kepler's 3rd law
    t0: number;    // ms — set ONCE on first load, never changed
  }

  const orbitsRef = useRef<OrbitalPlane[]>([]);
  const frameMatrix = useMemo(() => new THREE.Matrix4(), []);
  // Epoch anchored to page load so orbits survive re-renders without jumping
  const epochRef = useRef<number>(performance.now());

  useEffect(() => {
    // GM / R_earth³  →  gives ω in rad/s when r is in Three.js units (1 = 6371 km)
    const MU = 398600.4418 / (6371 ** 3);

    const newOrbits: OrbitalPlane[] = regularSats.map((sat, i) => {
      const existing = orbitsRef.current[i];

      const lat  = sat.lat ?? 0;
      const lon  = sat.lon ?? (sat as any).lng ?? 0;
      const alt  = sat.alt ?? 400;
      const r    = 1.0 + alt / 6371.0;
      const omega = Math.sqrt(MU / (r * r * r)) * 300; // 300x time-accel for visible motion

      // Position unit vector at this poll epoch
      const latR = lat * Math.PI / 180;
      const lonR = lon * Math.PI / 180;
      const px = Math.cos(latR) * Math.cos(lonR);
      const py = Math.sin(latR);
      const pz = Math.cos(latR) * Math.sin(lonR);

      // Orbital plane normal — tilted by latitude (inclination proxy)
      // equatorial sats → normal points up; polar sats → normal points sideways
      const incR = lat * Math.PI / 180;
      let nx = -Math.sin(lonR) * Math.cos(incR);
      let ny =  Math.sin(incR);
      let nz =  Math.cos(lonR) * Math.cos(incR);
      const nLen = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1;
      nx /= nLen; ny /= nLen; nz /= nLen;

      // q̂ = n̂ × p̂  (prograde direction, 90° ahead in orbit)
      let qx = ny*pz - nz*py;
      let qy = nz*px - nx*pz;
      let qz = nx*py - ny*px;
      const qLen = Math.sqrt(qx*qx + qy*qy + qz*qz) || 1;
      qx /= qLen; qy /= qLen; qz /= qLen;

      return {
        px, py, pz,
        qx, qy, qz,
        r, omega,
        // Preserve t0 across re-polls so the orbit doesn't jump position
        t0: existing ? existing.t0 : epochRef.current,
      };
    });

    orbitsRef.current = newOrbits;
  }, [regularSats]);

  // 60 fps — pure math, zero allocations
  useFrame(() => {
    const orbits = orbitsRef.current;
    if (!orbits.length || !groupData.length) return;

    const now = performance.now();

    groupData.forEach((gd, gi) => {
      const mesh = meshRefs.current[gi];
      if (!mesh) return;

      gd.satIndices.forEach((satIdx, instIdx) => {
        const o = orbits[satIdx];
        if (!o) return;

        const theta = o.omega * satelliteSpeed * (now - o.t0) / 1000; // radians
        const c = Math.cos(theta);
        const s = Math.sin(theta);

        // r * (cosθ · p̂  +  sinθ · q̂)
        frameMatrix.elements[12] = o.r * (c * o.px + s * o.qx);
        frameMatrix.elements[13] = o.r * (c * o.py + s * o.qy);
        frameMatrix.elements[14] = o.r * (c * o.pz + s * o.qz);
        // Only set translation — identity rotation is fine for dots
        frameMatrix.elements[0] = 1; frameMatrix.elements[5] = 1; frameMatrix.elements[10] = 1; frameMatrix.elements[15] = 1;
        frameMatrix.elements[1] = 0; frameMatrix.elements[2] = 0; frameMatrix.elements[3] = 0;
        frameMatrix.elements[4] = 0; frameMatrix.elements[6] = 0; frameMatrix.elements[7] = 0;
        frameMatrix.elements[8] = 0; frameMatrix.elements[9] = 0; frameMatrix.elements[11] = 0;

        mesh.setMatrixAt(instIdx, frameMatrix);
      });

      mesh.instanceMatrix.needsUpdate = true;
    });
  });

  // Hover state
  const [hoveredSat, setHoveredSat] = useState<SatellitePosition | null>(null);
  const [hoveredPos, setHoveredPos] = useState<[number, number, number] | null>(null);

  // Click handler using instanceId from raycaster
  const handleMeshClick = useCallback((event: any, groupIdx: number) => {
    event.stopPropagation();
    const instanceId = event.instanceId;
    if (instanceId === undefined || instanceId === null) return;
    const satIdx = groupData[groupIdx]?.satIndices[instanceId];
    if (satIdx === undefined) return;
    const sat = regularSats[satIdx];
    if (!sat) return;
    const id = sat.norad_id || sat.noradId || sat.id || '';
    setSelectedSatellite(id === selectedSatelliteId ? null : id);
  }, [groupData, regularSats, selectedSatelliteId, setSelectedSatellite]);

  const handleMeshHover = useCallback((event: any, groupIdx: number) => {
    event.stopPropagation();
    const instanceId = event.instanceId;
    if (instanceId === undefined || instanceId === null) { setHoveredSat(null); return; }
    const satIdx = groupData[groupIdx]?.satIndices[instanceId];
    if (satIdx === undefined) { setHoveredSat(null); return; }
    const sat = regularSats[satIdx];
    if (!sat) return;
    const mat = groupData[groupIdx].matrices[instanceId];
    setHoveredSat(sat);
    setHoveredPos([mat.elements[12], mat.elements[13], mat.elements[14]]);
    document.body.style.cursor = 'pointer';
  }, [groupData, regularSats]);

  const handleMeshUnhover = useCallback(() => {
    setHoveredSat(null);
    setHoveredPos(null);
    document.body.style.cursor = 'default';
  }, []);

  return (
    <group>
      {/* InstancedMesh groups — one draw call per color bucket, matrices set via useEffect */}
      {groupData.map((gd, gi) => (
        <instancedMesh
          key={gd.color}
          ref={(el) => { meshRefs.current[gi] = el; }}
          args={[instancedGeometry, undefined, gd.matrices.length]}
          onClick={(e) => handleMeshClick(e, gi)}
          onPointerOver={(e) => handleMeshHover(e, gi)}
          onPointerOut={handleMeshUnhover}
        >
          <meshBasicMaterial color={gd.color} toneMapped={false} />
        </instancedMesh>
      ))}

      {/* Selected satellite: separate high-quality mesh with pulsing ring */}
      {selectedSat && (
        <SelectedSatellite
          sat={selectedSat}
          onDeselect={() => setSelectedSatellite(null)}
        />
      )}

      {/* Hover tooltip */}
      {hoveredSat && hoveredPos && (
        <Html position={hoveredPos} pointerEvents="none" distanceFactor={4} center>
          <div className="bg-[#050914]/95 border border-cyan-800/40 p-2.5 rounded shadow-[0_4px_20px_rgba(0,0,0,0.8)] font-mono text-[8px] space-y-1 min-w-[130px] pointer-events-none select-none">
            <div className="text-cyan-400 font-bold block truncate pb-0.5 border-b border-cyan-950/45">
              {hoveredSat.name}
            </div>
            <div className="text-[7.5px] text-slate-400 flex justify-between">
              <span>NORAD:</span>
              <span className="text-slate-200 font-semibold">{hoveredSat.norad_id || hoveredSat.noradId || hoveredSat.id}</span>
            </div>
            <div className="text-[7.5px] text-slate-400 flex justify-between">
              <span>ALT:</span>
              <span className="text-slate-200">{Math.round(hoveredSat.alt)} km</span>
            </div>
            <div className="text-[7.5px] text-slate-400 flex justify-between">
              <span>TYPE:</span>
              <span className="text-slate-200 uppercase font-semibold">{hoveredSat.object_type || hoveredSat.type}</span>
            </div>
            {hoveredSat.criticality_score !== undefined && (
              <div className="text-[7.5px] text-slate-400 flex justify-between">
                <span>CRIT:</span>
                <span className="text-amber-400 font-extrabold">{hoveredSat.criticality_score.toFixed(1)}</span>
              </div>
            )}
          </div>
        </Html>
      )}

    </group>
  );
}
