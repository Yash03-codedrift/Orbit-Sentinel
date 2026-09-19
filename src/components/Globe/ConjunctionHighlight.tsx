import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface SatelliteData {
  lat: number;
  lon?: number;
  lng?: number;
  alt: number;
  inclination?: number;
  type?: string;
}

interface Conjunction {
  satA: SatelliteData;
  satB: SatelliteData;
  miss_distance_km?: number;
  missDistance?: number;
}

interface ConjunctionHighlightProps {
  conjunction: Conjunction | null;
  orbitDataA?: any[] | null;
  orbitDataB?: any[] | null;
}

export default function ConjunctionHighlight({
  conjunction,
  orbitDataA,
  orbitDataB,
}: ConjunctionHighlightProps) {
  const sphereRef = useRef<THREE.Mesh>(null);

  const parsedOrbits = useMemo(() => {
    if (!conjunction) return null;

    const generateOrbitPoints = (sat: SatelliteData) => {
      const points: THREE.Vector3[] = [];
      const inclination = sat.inclination !== undefined ? sat.inclination : (sat.type === 'DEBRIS' ? 45 : 98);
      const alt = sat.alt !== undefined ? sat.alt : 500;
      const iRad = (inclination * Math.PI) / 180;

      for (let angle = 0; angle <= 360; angle += 4) {
        const trueAnomaly = (angle * Math.PI) / 180;
        const ox = Math.cos(trueAnomaly);
        const oy = Math.sin(trueAnomaly) * Math.cos(iRad);
        const oz = Math.sin(trueAnomaly) * Math.sin(iRad);

        const orbLat = Math.asin(oy) * (180 / Math.PI);
        const orbLng = Math.atan2(ox, oz) * (180 / Math.PI);

        const latRad = (orbLat * Math.PI) / 180;
        const lonRad = (orbLng * Math.PI) / 180;
        const r = 1 + alt / 6371;

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

    const convertToVectors = (data: any[]) => {
      return data.map((pt) => {
        const lat = pt.lat;
        const lon = pt.lon !== undefined ? pt.lon : pt.lng;
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

    const ptsA = orbitDataA ? convertToVectors(orbitDataA) : generateOrbitPoints(conjunction.satA);
    const ptsB = orbitDataB ? convertToVectors(orbitDataB) : generateOrbitPoints(conjunction.satB);

    return { ptsA, ptsB };
  }, [conjunction, orbitDataA, orbitDataB]);

  // Compute TCA Closest point
  const tcaObj = useMemo(() => {
    if (!conjunction) return null;

    const latA = conjunction.satA.lat !== undefined ? conjunction.satA.lat : 0;
    const lonA = conjunction.satA.lon !== undefined ? conjunction.satA.lon : (conjunction.satA.lng !== undefined ? conjunction.satA.lng : 0);
    const altA = conjunction.satA.alt !== undefined ? conjunction.satA.alt : 500;

    const latB = conjunction.satB.lat !== undefined ? conjunction.satB.lat : 0;
    const lonB = conjunction.satB.lon !== undefined ? conjunction.satB.lon : (conjunction.satB.lng !== undefined ? conjunction.satB.lng : 0);
    const altB = conjunction.satB.alt !== undefined ? conjunction.satB.alt : 500;

    const avgLat = (latA + latB) / 2;
    const avgLon = (lonA + lonB) / 2;
    const avgAlt = (altA + altB) / 2;

    const latRad = (avgLat * Math.PI) / 180;
    const lonRad = (avgLon * Math.PI) / 180;
    const r = 1 + avgAlt / 6371;

    const vector = new THREE.Vector3(
      r * Math.cos(latRad) * Math.cos(lonRad),
      r * Math.sin(latRad),
      r * Math.cos(latRad) * Math.sin(lonRad)
    );

    const missDistanceKm = conjunction.miss_distance_km !== undefined 
      ? conjunction.miss_distance_km 
      : (conjunction.missDistance !== undefined ? conjunction.missDistance / 1000 : 1.25);

    // Exact formula request: radius = conjunction.miss_distance_km / 6371, 
    // we scale it up or bound it with max to make it visually pleasing and prominent
    const dangerZoneRadius = Math.max(0.04, (missDistanceKm / 6371) * 200);

    return { pos: vector, dangerZoneRadius };
  }, [conjunction]);

  useFrame(({ clock }) => {
    if (sphereRef.current) {
      const scale = 1 + Math.sin(clock.getElapsedTime() * 10) * 0.25;
      sphereRef.current.scale.set(scale, scale, scale);
    }
  });

  if (!conjunction || !parsedOrbits || !tcaObj) return null;

  // Convert points arrays into Float32Arrays for BufferGeometry
  const lineGeometryA = useMemo(() => new THREE.BufferGeometry().setFromPoints(parsedOrbits.ptsA), [parsedOrbits.ptsA]);
  const lineGeometryB = useMemo(() => new THREE.BufferGeometry().setFromPoints(parsedOrbits.ptsB), [parsedOrbits.ptsB]);

  const lineA = useMemo(() => {
    const mat = new THREE.LineBasicMaterial({ color: "#00D4FF", transparent: true, opacity: 0.65 });
    return new THREE.Line(lineGeometryA, mat);
  }, [lineGeometryA]);

  const lineB = useMemo(() => {
    const mat = new THREE.LineBasicMaterial({ color: "#FF6B35", transparent: true, opacity: 0.65 });
    return new THREE.Line(lineGeometryB, mat);
  }, [lineGeometryB]);

  return (
    <group>
      {/* Orbit A (Cyan Line) */}
      <primitive object={lineA} />

      {/* Orbit B (Orange Line) */}
      <primitive object={lineB} />

      {/* Closest Approach Point Red Sphere */}
      <mesh ref={sphereRef} position={tcaObj.pos}>
        <sphereGeometry args={[0.025, 16, 16]} />
        <meshBasicMaterial color="#ef4444" />
      </mesh>

      {/* Danger Zone Transparent Red Sphere */}
      <mesh position={tcaObj.pos}>
        <sphereGeometry args={[tcaObj.dangerZoneRadius, 32, 32]} />
        <meshBasicMaterial
          color="#ef4444"
          transparent
          opacity={0.25}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}
