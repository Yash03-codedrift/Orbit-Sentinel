import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface OrbitPoint {
  lat: number;
  lon?: number;
  lng?: number;
  alt: number;
}

interface BurnPosition {
  lat: number;
  lon?: number;
  lng?: number;
  alt: number;
}

interface ManeuverArcProps {
  isAnimating: boolean;
  burnPosition: BurnPosition | null;
  oldOrbit?: OrbitPoint[] | null;
  newOrbit?: OrbitPoint[] | null;
}

export default function ManeuverArc({
  isAnimating,
  burnPosition,
  oldOrbit,
  newOrbit,
}: ManeuverArcProps) {
  // Helpers to convert coordinates to Cartesian
  const convertToVectors = (data: OrbitPoint[]) => {
    return data.map((pt) => {
      const lat = pt.lat;
      const lon = pt.lon !== undefined ? pt.lon : (pt.lng !== undefined ? pt.lng : 0);
      const alt = pt.alt;
      const latRad = (lat * Math.PI) / 180;
      const lonRad = (lon * Math.PI) / 180;
      const r = 1 + alt / 6371;
      return new THREE.Vector3(
        r * Math.cos(latRad) * Math.cos(lonRad),
        r * Math.sin(latRad),
        r * Math.cos(latRad) * Math.sin(lonRad)
      );
    });
  };

  // Trajectory Fallback generator
  const trajectoryData = useMemo(() => {
    if (!isAnimating) return null;

    const bLat = burnPosition?.lat ?? 0;
    const bLon = burnPosition?.lon !== undefined ? burnPosition?.lon : (burnPosition?.lng ?? 0);
    const bAlt = burnPosition?.alt ?? 500;

    const generateOrbitPoints = (altOffset: number) => {
      const points: THREE.Vector3[] = [];
      const inclination = 85; 
      const iRad = (inclination * Math.PI) / 180;

      for (let angle = 0; angle <= 360; angle += 4) {
        const trueAnomaly = (angle * Math.PI) / 180;
        const ox = Math.cos(trueAnomaly);
        const oy = Math.sin(trueAnomaly) * Math.cos(iRad);
        const oz = Math.sin(trueAnomaly) * Math.sin(iRad);

        // Incorporate a skew around the burn coordinate
        const orbLat = Math.asin(oy) * (180 / Math.PI) + bLat * 0.1;
        const orbLng = Math.atan2(ox, oz) * (180 / Math.PI) + bLon * 0.1;

        const latRad = (orbLat * Math.PI) / 180;
        const lonRad = (orbLng * Math.PI) / 180;
        const r = 1 + (bAlt + altOffset) / 6371;

        points.push(
          new THREE.Vector3(
            r * Math.cos(latRad) * Math.cos(lonRad),
            r * Math.sin(latRad),
            r * Math.cos(latRad) * Math.sin(lonRad)
          )
        );
      }
      return points;
    };

    const ptsOld = oldOrbit ? convertToVectors(oldOrbit) : generateOrbitPoints(0);
    const ptsNew = newOrbit ? convertToVectors(newOrbit) : generateOrbitPoints(25);

    return { ptsOld, ptsNew };
  }, [isAnimating, burnPosition, oldOrbit, newOrbit]);

  // Particle creation inside useMemo
  const { particles, originPos } = useMemo(() => {
    const list: { pos: THREE.Vector3; vel: THREE.Vector3 }[] = [];
    if (!isAnimating || !burnPosition) return { particles: list, originPos: new THREE.Vector3() };

    const bLat = burnPosition.lat;
    const bLon = burnPosition.lon !== undefined ? burnPosition.lon : (burnPosition.lng ?? 0);
    const bAlt = burnPosition.alt;

    const latRad = (bLat * Math.PI) / 180;
    const lonRad = (bLon * Math.PI) / 180;
    const r = 1 + bAlt / 6371;

    const origin = new THREE.Vector3(
      r * Math.cos(latRad) * Math.cos(lonRad),
      r * Math.sin(latRad),
      r * Math.cos(latRad) * Math.sin(lonRad)
    );

    // Create 8 outward exploding particles
    for (let i = 0; i < 8; i++) {
      const angle = (i * Math.PI * 2) / 8;
      const vel = new THREE.Vector3(
        Math.cos(angle) * 0.01 + (Math.random() - 0.5) * 0.004,
        Math.sin(angle) * 0.01 + (Math.random() - 0.5) * 0.004,
        (Math.random() - 0.5) * 0.008
      );
      list.push({ pos: origin.clone(), vel });
    }

    return { particles: list, originPos: origin };
  }, [isAnimating, burnPosition]);

  // Particles refs for fast hardware updates
  const particleRefs = useRef<(THREE.Mesh | null)[]>([]);

  const oldMat = useMemo(() => new THREE.LineBasicMaterial({
    color: "#ef4444",
    transparent: true,
    opacity: 0.8
  }), []);

  const newMat = useMemo(() => new THREE.LineBasicMaterial({
    color: "#10b981",
    transparent: true,
    opacity: 0.1
  }), []);

  const oldGeom = useMemo(() => {
    if (!trajectoryData) return new THREE.BufferGeometry();
    return new THREE.BufferGeometry().setFromPoints(trajectoryData.ptsOld);
  }, [trajectoryData]);

  const newGeom = useMemo(() => {
    if (!trajectoryData) return new THREE.BufferGeometry();
    return new THREE.BufferGeometry().setFromPoints(trajectoryData.ptsNew);
  }, [trajectoryData]);

  const oldLine = useMemo(() => new THREE.Line(oldGeom, oldMat), [oldGeom, oldMat]);
  const newLine = useMemo(() => new THREE.Line(newGeom, newMat), [newGeom, newMat]);

  useFrame((state) => {
    if (!isAnimating) return;
    const t = (state.clock.getElapsedTime() * 1.2) % 1.0;

    // 1. Line opacities fading
    if (oldMat) {
      oldMat.opacity = Math.max(0, 0.8 * (1 - t));
    }
    if (newMat) {
      newMat.opacity = Math.min(0.8, 0.8 * t);
    }

    // 2. Exploding engine ignition particle movement
    if (particles.length > 0) {
      particles.forEach((p, index) => {
        const mesh = particleRefs.current[index];
        if (mesh) {
          // Reset when loop restarts
          if (t < 0.05) {
            p.pos.copy(originPos);
            mesh.scale.set(1, 1, 1);
          } else {
            p.pos.add(p.vel);
            const scaleFac = Math.max(0.1, 1 - t);
            mesh.scale.set(scaleFac, scaleFac, scaleFac);
          }
          mesh.position.copy(p.pos);
        }
      });
    }
  });

  if (!isAnimating || !trajectoryData) return null;

  return (
    <group>
      {/* Pre-maneuver critical hazard trajectory path (dashed, fading out) */}
      <primitive object={oldLine} />

      {/* Avoidance maneuver trajectory trajectory path (solid, fading in) */}
      <primitive object={newLine} />

      {/* Burn explosion burst particle animation */}
      <group>
        {particles.map((_, index) => (
          <mesh
            key={index}
            ref={(el) => {
              particleRefs.current[index] = el;
            }}
          >
            <sphereGeometry args={[0.012, 8, 8]} />
            <meshBasicMaterial
              color="#eab308"
              transparent
              opacity={0.9}
              blending={THREE.AdditiveBlending}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}
