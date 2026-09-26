export function cumulativeLengths(pts) {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  }
  return cum;
}

export function pointAlong(pts, cum, s) {
  const total = cum[cum.length - 1];
  const d = Math.max(0, Math.min(total, s));
  let i = 1;
  while (i < cum.length - 1 && cum[i] < d) i++;
  const [ax, ay] = pts[i - 1], [bx, by] = pts[i];
  const len = cum[i] - cum[i - 1] || 1;
  const t = (d - cum[i - 1]) / len;
  return { x: ax + (bx - ax) * t, y: ay + (by - ay) * t, dx: (bx - ax) / len, dy: (by - ay) / len };
}

function slice(pts, cum, s, e) {
  const a = pointAlong(pts, cum, s), b = pointAlong(pts, cum, e);
  const mid = [];
  for (let i = 1; i < pts.length - 1; i++) if (cum[i] > s && cum[i] < e) mid.push(pts[i]);
  return [[a.x, a.y], ...mid, [b.x, b.y]];
}

export function dashSegments(pts, on, off) {
  const cum = cumulativeLengths(pts), total = cum[cum.length - 1], out = [];
  for (let s = 0; s < total; s += on + off) {
    const e = Math.min(total, s + on);
    if (e - s < on * 0.3) break;
    out.push(slice(pts, cum, s, e));
  }
  return out;
}

const DISC_SEGMENTS = 12;

export function ribbonTriangles(polylines, width) {
  const h = width / 2, out = [];
  for (const pts of polylines) {
    for (let i = 1; i < pts.length; i++) {
      const [ax, ay] = pts[i - 1], [bx, by] = pts[i];
      const len = Math.hypot(bx - ax, by - ay);
      if (len < 1e-6) continue;
      const nx = (-(by - ay) / len) * h, ny = ((bx - ax) / len) * h;
      out.push(ax + nx, ay + ny, ax - nx, ay - ny, bx - nx, by - ny);
      out.push(ax + nx, ay + ny, bx - nx, by - ny, bx + nx, by + ny);
    }
    for (const [cx, cy] of pts) {
      for (let k = 0; k < DISC_SEGMENTS; k++) {
        const a0 = (k / DISC_SEGMENTS) * 2 * Math.PI, a1 = ((k + 1) / DISC_SEGMENTS) * 2 * Math.PI;
        out.push(cx, cy, cx + Math.cos(a0) * h, cy + Math.sin(a0) * h, cx + Math.cos(a1) * h, cy + Math.sin(a1) * h);
      }
    }
  }
  return out;
}
