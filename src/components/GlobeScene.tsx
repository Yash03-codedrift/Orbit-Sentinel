import React, { useRef, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import { Satellite, ConjunctionEvent } from '../types';
import { useGlobeStore } from '../store/useGlobeStore';
import { useConjunctionStore } from '../store/useConjunctionStore';
import EarthMesh from './Globe/EarthMesh';
import SatelliteDots from './Globe/SatelliteDots';
import ConjunctionHighlight from './Globe/ConjunctionHighlight';
import ManeuverArc from './Globe/ManeuverArc';
import { Eye, RotateCcw, Gauge, Radio } from 'lucide-react';

interface GlobeSceneProps {
  conjunctions: ConjunctionEvent[];
  selectedConjunction: ConjunctionEvent | null;
  onSelectConjunction: (conj: ConjunctionEvent) => void;
  onResetCamera?: (fn: () => void) => void;
  layers: {
    satellites: boolean;
    orbits: boolean;
    conjunctions: boolean;
  };
  setLayers: React.Dispatch<React.SetStateAction<{
    satellites: boolean;
    orbits: boolean;
    conjunctions: boolean;
  }>>;
}

// 5000 Star positions inside coordinates space of radius 50
function StarsBackground() {
  const starsGeo = useMemo(() => {
    const count = 5000;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Pick random point on a sphere surface of radius 40-60
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = 45 + Math.random() * 15;
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    return positions;
  }, []);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={5000}
          array={starsGeo}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#ffffff"
        size={0.06}
        sizeAttenuation={true}
        transparent
        opacity={0.8}
        depthWrite={false}
      />
    </points>
  );
}

export default function GlobeScene({
  conjunctions,
  selectedConjunction,
  onSelectConjunction,
  onResetCamera,
  layers,
  setLayers,
}: GlobeSceneProps) {
  const controlsRef = useRef<any>(null);
  const isAnimatingManeuver = useGlobeStore((s) => s.isAnimatingManeuver);
  const satellitePositions = useGlobeStore((s) => s.satellitePositions);
  const highlightedOrbitIds = useGlobeStore((s) => s.highlightedOrbitIds);
  const satelliteSpeed = useGlobeStore((s) => s.satelliteSpeed);
  const setSatelliteSpeed = useGlobeStore((s) => s.setSatelliteSpeed);
  const cinematicMode = useGlobeStore((s) => s.cinematicMode);

  const conjunctionPairs = useMemo(() =>
    (conjunctions || [])
      .map((c: any) => ({
        norad_id_a: c.norad_id_a || c.noradIdA || '',
        norad_id_b: c.norad_id_b || c.noradIdB || '',
        risk_level:  c.risk_level  || c.riskLevel  || 'HIGH',
      }))
      .filter((p: any) => p.norad_id_a && p.norad_id_b),
    [conjunctions]
  );

  const resetCamera = () => {
    if (controlsRef.current) {
      controlsRef.current.reset();
    }
  };

  // Expose resetCamera to parent (for cinematic mode overlay)
  React.useEffect(() => {
    if (onResetCamera) onResetCamera(resetCamera);
  }, []);

  // Convert click coordinates inside globe scene if needed or layer activations
  return (
    <div
      id="globe_container"
      className="relative w-full h-[360px] md:h-full min-h-[300px] flex flex-col bg-[#050810] border border-cyan-950/40 rounded-lg overflow-hidden select-none"
    >
      {/* HUD Watermark Overlay Info */}
      <div className="absolute top-3 left-4 pointer-events-none z-10 flex flex-col">
        <span className="font-display text-xs font-bold tracking-wider text-cyan-400 flex items-center gap-1.5 uppercase">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse border border-cyan-300" />
          REALTIME ORBITAL PROPAGATOR
        </span>
        <span className="font-mono text-[9px] text-slate-500 mt-0.5 uppercase">
          COORDINATES: SGP4 THREE.JS WEBGL / LEO ZONE
        </span>
      </div>

      {/* Primary WebGL Canvas Environment */}
      <div className="flex-1 w-full h-full relative" style={{ minHeight: '280px' }}>
        <Canvas
          id="globe_viewport"
          camera={{ position: [0, 0, 2.8], fov: 45 }}
          style={{ background: '#050810', width: '100%', height: '100%' }}
        >
          {/* Ambient space illumination */}
          <ambientLight intensity={0.5} />
          {/* Soft solar direction source */}
          <directionalLight position={[5, 3, 5]} intensity={1.2} />

          {/* Core Starfield */}
          <StarsBackground />

          {/* Planet Earth layer */}
          <EarthMesh />

          {/* Satellite points layer */}
          {layers.satellites && (
            <SatelliteDots
              positions={Array.isArray(satellitePositions) ? satellitePositions : []}
              showOrbits={layers.orbits}
              conjunctionPairs={conjunctionPairs}
              highlightedOrbitIds={highlightedOrbitIds}
            />
          )}

          {/* Conjunction collision hazard alerts layer */}
          {layers.conjunctions && selectedConjunction && (
            <ConjunctionHighlight conjunction={selectedConjunction} />
          )}

          {/* Avoidance maneuver curves layer */}
          {isAnimatingManeuver && selectedConjunction && (
            <ManeuverArc
              isAnimating={isAnimatingManeuver}
              burnPosition={selectedConjunction.satA}
            />
          )}

          {/* Orbit Navigation Control Hooks */}
          <OrbitControls
            ref={controlsRef}
            enablePan={false}
            minDistance={1.4}
            maxDistance={8}
            enableDamping
            dampingFactor={0.05}
          />
        </Canvas>

        {/* Small floating action buttons top right — hidden in cinematic mode */}
        {!cinematicMode && (
          <div className="absolute top-3 right-3 flex flex-col gap-1.5 z-10">
            <button
              id="btn_reset_camera"
              onClick={resetCamera}
              title="Reset Prefabricated Viewport"
              className="p-1.5 px-2 border border-cyan-800/25 bg-slate-950/80 rounded hover:bg-slate-900 text-slate-400 hover:text-cyan-400 text-[10px] font-mono flex items-center gap-1 transition-all pointer-events-auto cursor-pointer shadow-lg"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              RESET CAMERA
            </button>
          </div>
        )}
      </div>

      {/* Visual toggle overlays footer bar */}
      <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2 bg-slate-950/85 border border-cyan-950/40 rounded p-1.5 z-10 backdrop-blur-md pointer-events-auto shadow-md">
        <div className="flex items-center gap-1 text-[10px] font-mono text-slate-400 px-1 hidden sm:flex">
          <Eye className="w-3 h-3 text-cyan-400" />
          <span>VISIBILITY LAYERS</span>
        </div>

        <div className="flex items-center gap-1 flex-1 sm:justify-end justify-center">
          <button
            id="layer_satellites"
            onClick={() => setLayers((prev) => ({ ...prev, satellites: !prev.satellites }))}
            className={`px-2.5 py-1 text-[9px] font-mono rounded tracking-tighter uppercase transition-all cursor-pointer ${
              layers.satellites
                ? 'bg-cyan-950/50 text-cyan-400 border border-cyan-600/30 font-semibold'
                : 'text-slate-500 border border-transparent hover:text-slate-300'
            }`}
          >
            ● SAT
          </button>
          <button
            id="layer_orbits"
            onClick={() => setLayers((prev) => ({ ...prev, orbits: !prev.orbits }))}
            className={`px-2.5 py-1 text-[9px] font-mono rounded tracking-tighter uppercase transition-all cursor-pointer ${
              layers.orbits
                ? 'bg-sky-950/50 text-sky-400 border border-sky-600/30 font-semibold'
                : 'text-slate-500 border border-transparent hover:text-slate-300'
            }`}
          >
            ◎ ORBITS
          </button>
          <button
            id="layer_conjunctions"
            onClick={() => setLayers((prev) => ({ ...prev, conjunctions: !prev.conjunctions }))}
            className={`px-2.5 py-1 text-[9px] font-mono rounded tracking-tighter uppercase transition-all cursor-pointer ${
              layers.conjunctions
                ? 'bg-red-950/50 text-red-400 border border-red-600/30 font-semibold'
                : 'text-slate-500 border border-transparent hover:text-slate-300'
            }`}
          >
            ◈ CONJ
          </button>

          {/* Speed divider */}
          <div className="w-px h-4 bg-cyan-950/60 mx-1" />

          {/* Speed controller */}
          <div className="flex items-center gap-1.5">
            <Gauge className="w-3 h-3 text-slate-400 shrink-0" />
            <input
              id="satellite_speed_slider"
              type="range"
              min={0}
              max={2000}
              step={1}
              value={satelliteSpeed}
              onChange={(e) => setSatelliteSpeed(Number(e.target.value))}
              className="w-20 h-1.5 accent-cyan-400 cursor-pointer"
              title={`Simulation speed: ${satelliteSpeed}x`}
            />
            <span className="text-[9px] font-mono text-cyan-400 min-w-[32px]">{satelliteSpeed === 0 ? 'STOP' : `${satelliteSpeed}x`}</span>
            <button
              id="satellite_speed_stop"
              onClick={() => setSatelliteSpeed(0)}
              title="Freeze all satellites"
              className={`px-1.5 py-0.5 text-[9px] font-mono rounded border transition-all cursor-pointer ${
                satelliteSpeed === 0
                  ? 'bg-red-950/60 text-red-400 border-red-600/40 font-bold'
                  : 'text-slate-500 border-slate-700/40 hover:text-red-400 hover:border-red-700/40'
              }`}
            >
              ■
            </button>
            <button
              id="satellite_speed_live"
              onClick={() => setSatelliteSpeed(1)}
              title="Reset to real orbital speed"
              className={`flex items-center gap-1 px-2 py-0.5 text-[9px] font-mono rounded uppercase tracking-wider border transition-all cursor-pointer ${
                satelliteSpeed === 1
                  ? 'bg-emerald-950/60 text-emerald-400 border-emerald-600/40 font-bold'
                  : 'text-slate-400 border-slate-700/40 hover:text-emerald-400 hover:border-emerald-700/40'
              }`}
            >
              <Radio className="w-2.5 h-2.5" />
              LIVE
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}