import { convexHull, polygonArea } from './geom.js';

export const GABLE_MIN_FILL = 0.8;

export function orientedRect(pts) {
  const hull = convexHull(pts);
  let best = null;
  for (let i = 0; i < hull.length; i++) {
    const [ax, ay] = hull[i], [bx, by] = hull[(i + 1) % hull.length];
    const angle = Math.atan2(by - ay, bx - ax), c = Math.cos(angle), s = Math.sin(angle);
    let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity;
    for (const [x, y] of hull) {
      const u = x * c + y * s, v = -x * s + y * c;
      minU = Math.min(minU, u); maxU = Math.max(maxU, u);
      minV = Math.min(minV, v); maxV = Math.max(maxV, v);
    }
    const area = (maxU - minU) * (maxV - minV);
    if (!best || area < best.area - 1e-9) best = { area, angle, minU, maxU, minV, maxV };
  }
  let { angle } = best;
  const c = Math.cos(angle), s = Math.sin(angle);
  const cu = (best.minU + best.maxU) / 2, cv = (best.minV + best.maxV) / 2;
  let length = best.maxU - best.minU, width = best.maxV - best.minV;
  if (width > length) {
    [length, width] = [width, length];
    angle += Math.PI / 2;
  }
  return { cx: cu * c - cv * s, cy: cu * s + cv * c, angle, length, width };
}

export function roofType(kind, pts) {
  if (kind === 'house') {
    const r = orientedRect(pts);
    return polygonArea(pts) / (r.length * r.width) >= GABLE_MIN_FILL ? 'gable' : 'hip';
  }
  if (kind === 'other') return 'none';
  return 'flat';
}

export function roofTriangles(rect, type, overhang = 0.6) {
  const hl = rect.length / 2 + overhang, hw = rect.width / 2 + overhang;
  const h = (type === 'gable' ? 0.45 : 0.3) * rect.width;
  const a = type === 'gable' ? hl : Math.max(0, hl - hw);
  const c = Math.cos(rect.angle), s = Math.sin(rect.angle);
  const P = (u, v, z) => [rect.cx + u * c - v * s, rect.cy + u * s + v * c, z];
  const b1 = P(-hl, -hw, 0), b2 = P(hl, -hw, 0), b3 = P(hl, hw, 0), b4 = P(-hl, hw, 0);
  const r1 = P(-a, 0, h), r2 = P(a, 0, h);
  return [b1, b2, r2, b1, r2, r1, b3, b4, r1, b3, r1, r2, b2, b3, r2, b4, b1, r1];
}
