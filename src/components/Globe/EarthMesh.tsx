import React, { useRef, useState, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// CDN fallbacks — attempted in order; procedural fallback used if all fail
const TEXTURE_URLS = [
  'https://cdn.jsdelivr.net/npm/three-globe/example/img/earth-blue-marble.jpg',
  'https://unpkg.com/three-globe@2.31.1/example/img/earth-blue-marble.jpg',
  'https://raw.githubusercontent.com/vasturiano/three-globe/master/example/img/earth-blue-marble.jpg',
  'https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57735/land_shallow_topo_2048.jpg',
];

function makeProceduralEarth(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 2048;
  canvas.height = 1024;
  const ctx = canvas.getContext('2d')!;

  // Deep ocean base with gradient
  const oceanGrad = ctx.createLinearGradient(0, 0, 0, 1024);
  oceanGrad.addColorStop(0,   '#0b2a4a');
  oceanGrad.addColorStop(0.3, '#0d3560');
  oceanGrad.addColorStop(0.5, '#0e3d70');
  oceanGrad.addColorStop(0.7, '#0d3560');
  oceanGrad.addColorStop(1,   '#071e35');
  ctx.fillStyle = oceanGrad;
  ctx.fillRect(0, 0, 2048, 1024);

  // Ocean shimmer/depth variation
  for (let i = 0; i < 600; i++) {
    const x = Math.random() * 2048;
    const y = Math.random() * 1024;
    const r = Math.random() * 40 + 5;
    const grad = ctx.createRadialGradient(x, y, 0, x, y, r);
    grad.addColorStop(0, 'rgba(20,80,140,0.15)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }

  // Landmass helper
  const drawLand = (shapes: [number, number, number, number, number][]) => {
    for (const [cx, cy, rx, ry, rot] of shapes) {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(rot);
      ctx.beginPath();
      ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
      ctx.restore();
      ctx.fill();
    }
  };

  // Continental land — rich green/brown
  const landGrad = ctx.createLinearGradient(0, 150, 0, 900);
  landGrad.addColorStop(0,   '#2d5a1b');
  landGrad.addColorStop(0.3, '#3a6b22');
  landGrad.addColorStop(0.5, '#4a7c2f');
  landGrad.addColorStop(0.7, '#5a6b2a');
  landGrad.addColorStop(1,   '#6b5820');
  ctx.fillStyle = landGrad;

  // North America
  ctx.beginPath();
  ctx.ellipse(390, 310, 185, 160, -0.15, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(430, 260, 90, 60, 0.1, 0, Math.PI * 2); ctx.fill();
  // Central America connector
  ctx.beginPath();
  ctx.ellipse(470, 430, 30, 50, 0.3, 0, Math.PI * 2); ctx.fill();
  // South America
  ctx.beginPath();
  ctx.ellipse(530, 620, 90, 150, 0.08, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(510, 500, 50, 40, 0.1, 0, Math.PI * 2); ctx.fill();

  // Europe
  ctx.beginPath();
  ctx.ellipse(1010, 295, 90, 75, -0.05, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1050, 260, 60, 45, 0.1, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1090, 310, 40, 30, 0.1, 0, Math.PI * 2); ctx.fill();

  // Africa
  ctx.beginPath();
  ctx.ellipse(1040, 490, 115, 185, 0.0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1040, 350, 80, 60, 0.0, 0, Math.PI * 2); ctx.fill();

  // Asia (multiple blobs)
  ctx.beginPath();
  ctx.ellipse(1220, 300, 200, 150, -0.08, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1440, 310, 200, 130, 0.05, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1350, 450, 120, 100, 0.0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1250, 430, 80, 70, 0.0, 0, Math.PI * 2); ctx.fill();
  // Indian subcontinent
  ctx.beginPath();
  ctx.ellipse(1230, 520, 65, 90, 0.1, 0, Math.PI * 2); ctx.fill();
  // SE Asia
  ctx.beginPath();
  ctx.ellipse(1450, 480, 80, 60, 0.2, 0, Math.PI * 2); ctx.fill();

  // Australia
  ctx.beginPath();
  ctx.ellipse(1570, 670, 115, 80, 0.05, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1530, 630, 60, 40, -0.1, 0, Math.PI * 2); ctx.fill();

  // Greenland
  ctx.fillStyle = '#4a8a6a';
  ctx.beginPath();
  ctx.ellipse(570, 200, 75, 60, -0.2, 0, Math.PI * 2); ctx.fill();

  // Desert areas (Sahara, Arabia) — sandy overlay
  ctx.fillStyle = 'rgba(180, 140, 60, 0.35)';
  ctx.beginPath();
  ctx.ellipse(1040, 430, 120, 70, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1130, 370, 70, 50, 0.1, 0, Math.PI * 2); ctx.fill();

  // Polar ice caps — bright white
  ctx.fillStyle = 'rgba(220, 235, 255, 0.85)';
  ctx.beginPath(); ctx.ellipse(1024, 22, 1024, 55, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(1024, 1002, 1024, 55, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = 'rgba(200, 220, 255, 0.6)';
  ctx.beginPath(); ctx.ellipse(1024, 45, 900, 35, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(1024, 980, 900, 35, 0, 0, Math.PI * 2); ctx.fill();

  // Subtle lat/lon grid
  ctx.strokeStyle = 'rgba(100,180,255,0.06)';
  ctx.lineWidth = 1;
  for (let x = 0; x <= 2048; x += 2048 / 24) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 1024); ctx.stroke();
  }
  for (let y = 0; y <= 1024; y += 1024 / 12) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(2048, y); ctx.stroke();
  }

  // City lights (night-side glow dots)
  ctx.fillStyle = 'rgba(255, 210, 100, 0.7)';
  const cities: [number, number][] = [
    // N America
    [390,295],[440,305],[480,310],[510,330],[550,320],[370,330],[420,340],
    // Europe
    [1015,290],[1050,285],[1080,295],[1035,305],[1060,300],[1020,275],
    // Asia
    [1200,330],[1350,300],[1450,340],[1490,370],[1320,390],[1380,360],
    [1240,480],[1260,450],[1470,450],[1510,400],
    // SE Asia coast
    [1450,490],[1480,500],
    // Africa  
    [1040,470],[1030,510],[1050,530],[1060,560],
    // Australia
    [1565,670],[1610,680],[1540,650],
    // S America
    [530,580],[520,620],[545,640],
  ];
  for (const [cx, cy] of cities) {
    ctx.beginPath(); ctx.arc(cx, cy, 2.5, 0, Math.PI * 2); ctx.fill();
    // Soft glow
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 8);
    glow.addColorStop(0, 'rgba(255,200,80,0.15)');
    glow.addColorStop(1, 'rgba(255,200,80,0)');
    ctx.fillStyle = glow;
    ctx.beginPath(); ctx.arc(cx, cy, 8, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(255, 210, 100, 0.7)';
  }

  return new THREE.CanvasTexture(canvas);
}

export default function EarthMesh() {
  const earthRef = useRef<THREE.Mesh>(null);
  const atmosphereRef = useRef<THREE.Mesh>(null);
  // Start with procedural texture immediately so earth is always visible
  const [texture, setTexture] = useState<THREE.Texture>(() => makeProceduralEarth());

  useEffect(() => {
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin('anonymous');

    let cancelled = false;
    let idx = 0;

    const tryNext = () => {
      if (cancelled) return;
      if (idx >= TEXTURE_URLS.length) return; // already showing procedural
      loader.load(
        TEXTURE_URLS[idx],
        (tex) => {
          if (cancelled) return;
          tex.colorSpace = THREE.SRGBColorSpace;
          setTexture(tex);
        },
        undefined,
        () => { idx++; tryNext(); }
      );
    };

    tryNext();
    return () => { cancelled = true; };
  }, []);

  useFrame((state) => {
    if (earthRef.current) {
      earthRef.current.rotation.y = state.clock.getElapsedTime() * 0.008;
    }
  });

  return (
    <group>
      <mesh ref={earthRef} castShadow receiveShadow>
        <sphereGeometry args={[1, 64, 64]} />
        <meshStandardMaterial
          map={texture}
          roughness={0.65}
          metalness={0.05}
        />
      </mesh>

      {/* Atmosphere glow */}
      <mesh ref={atmosphereRef}>
        <sphereGeometry args={[1.025, 64, 64]} />
        <meshBasicMaterial
          color="#00d4ff"
          transparent
          opacity={0.12}
          depthWrite={false}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
    </group>
  );
}
