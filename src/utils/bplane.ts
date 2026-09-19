interface StateVector {
  x?: number; y?: number; z?: number;
  vx?: number; vy?: number; vz?: number;
}

export interface BPlaneResult {
  xi: number;    // km, in-plane axis 1
  eta: number;   // km, in-plane axis 2
  missKm: number;
}

const cross = (a: number[], b: number[]) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const dot = (a: number[], b: number[]) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const norm = (a: number[]) => {
  const m = Math.sqrt(dot(a, a));
  return m > 1e-9 ? a.map((v) => v / m) : a;
};

/**
 * Computes the real B-plane (encounter plane) miss vector from two
 * state vectors at TCA — the same method conjunction-assessment tools
 * (CARA, ESA) use: project the relative position onto the plane
 * perpendicular to the relative velocity vector.
 */
export function computeBPlane(a: StateVector, b: StateVector): BPlaneResult | null {
  if (
    a?.x === undefined || b?.x === undefined ||
    a?.vx === undefined || b?.vx === undefined
  ) {
    return null;
  }

  const rRel = [a.x! - b.x!, a.y! - b.y!, a.z! - b.z!];
  const vRel = [a.vx! - b.vx!, a.vy! - b.vy!, a.vz! - b.vz!];

  const vMag = Math.sqrt(dot(vRel, vRel));
  if (vMag < 1e-6) return null;
  const vHat = vRel.map((v) => v / vMag);

  const rDotV = dot(rRel, vHat);
  const bVec = rRel.map((r, i) => r - rDotV * vHat[i]);

  let ref = [0, 0, 1];
  if (Math.abs(vHat[2]) > 0.95) ref = [0, 1, 0];

  const xiHat = norm(cross(vHat, ref));
  const etaHat = norm(cross(vHat, xiHat));

  return {
    xi: dot(bVec, xiHat),
    eta: dot(bVec, etaHat),
    missKm: Math.sqrt(dot(bVec, bVec)),
  };
}