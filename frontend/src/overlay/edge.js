const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
const EDGE_EPS = 0.5;
const PERIMETER_STEP = 4;

const collide = (a, b, gap) =>
  Math.abs(a.x - b.x) < (a.w + b.w) / 2 + gap - 1e-6 && Math.abs(a.y - b.y) < (a.h + b.h) / 2 + gap - 1e-6;

// Centre positions a box can take along the inset rectangle, nearest to where it is now first.
function perimeterSpots(b, W, H, pad) {
  const x0 = b.w / 2 + pad, x1 = W - b.w / 2 - pad, y0 = b.h / 2 + pad, y1 = H - b.h / 2 - pad;
  const spots = [];
  for (let x = x0; x <= x1; x += PERIMETER_STEP) spots.push({ x, y: y0 }, { x, y: y1 });
  for (let y = y0; y <= y1; y += PERIMETER_STEP) spots.push({ x: x0, y }, { x: x1, y });
  return spots.sort((p, q) => Math.hypot(p.x - b.x, p.y - b.y) - Math.hypot(q.x - b.x, q.y - b.y));
}

export function edgePoint(center, dir, halfW, halfH, W, H, pad = 10) {
  const mx = halfW + pad, my = halfH + pad;
  const cx = clamp(center.x, mx, W - mx), cy = clamp(center.y, my, H - my);
  let k = Infinity;
  if (dir.x > 1e-6) k = Math.min(k, (W - mx - cx) / dir.x);
  if (dir.x < -1e-6) k = Math.min(k, (mx - cx) / dir.x);
  if (dir.y > 1e-6) k = Math.min(k, (H - my - cy) / dir.y);
  if (dir.y < -1e-6) k = Math.min(k, (my - cy) / dir.y);
  if (!Number.isFinite(k)) k = 0;
  return { x: cx + dir.x * k, y: cy + dir.y * k };
}

// Spread badges sitting on one edge along that edge: a forward pass pushes each
// badge past its predecessor, a backward pass pulls the chain back inside.
function sweep(group, axis, size, gap, lo, hi) {
  group.sort((a, b) => a[axis] - b[axis]);
  for (let i = 1; i < group.length; i++) {
    const need = (group[i - 1][size] + group[i][size]) / 2 + gap;
    group[i][axis] = Math.max(group[i][axis], group[i - 1][axis] + need);
  }
  for (let i = group.length - 1; i >= 0; i--) {
    group[i][axis] = Math.min(group[i][axis], hi(group[i]));
    if (i < group.length - 1) {
      const need = (group[i][size] + group[i + 1][size]) / 2 + gap;
      group[i][axis] = Math.min(group[i][axis], group[i + 1][axis] - need);
    }
  }
  for (const b of group) b[axis] = Math.max(b[axis], lo(b));
}

export function resolveOverlaps(boxes, W, H, pad = 10, gap = 6, maxIter = 20) {
  const minX = (b) => b.w / 2 + pad, maxX = (b) => W - b.w / 2 - pad;
  const minY = (b) => b.h / 2 + pad, maxY = (b) => H - b.h / 2 - pad;
  const left = boxes.filter((b) => b.x <= minX(b) + EDGE_EPS);
  const right = boxes.filter((b) => !left.includes(b) && b.x >= maxX(b) - EDGE_EPS);
  const sides = new Set([...left, ...right]);
  const top = boxes.filter((b) => !sides.has(b) && b.y <= minY(b) + EDGE_EPS);
  const bottom = boxes.filter((b) => !sides.has(b) && !top.includes(b) && b.y >= maxY(b) - EDGE_EPS);
  sweep(left, 'y', 'h', gap, minY, maxY);
  sweep(right, 'y', 'h', gap, minY, maxY);
  sweep(top, 'x', 'w', gap, minX, maxX);
  sweep(bottom, 'x', 'w', gap, minX, maxX);

  // Remaining overlaps (e.g. a corner badge against an edge neighbour): push apart pairwise.
  for (let iter = 0; iter < maxIter; iter++) {
    let moved = false;
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j];
        const ox = (a.w + b.w) / 2 + gap - Math.abs(a.x - b.x);
        const oy = (a.h + b.h) / 2 + gap - Math.abs(a.y - b.y);
        if (ox <= 1e-6 || oy <= 1e-6) continue;
        moved = true;
        if (ox < oy) {
          const s = ((a.x <= b.x ? -1 : 1) * ox) / 2;
          a.x += s; b.x -= s;
        } else {
          const s = ((a.y <= b.y ? -1 : 1) * oy) / 2;
          a.y += s; b.y -= s;
        }
      }
    }
    for (const b of boxes) {
      b.x = clamp(b.x, minX(b), maxX(b));
      b.y = clamp(b.y, minY(b), maxY(b));
    }
    if (!moved) break;
  }

  // Last resort for crowded corners: move any badge still overlapping to the nearest free edge spot.
  const placed = [];
  for (const b of boxes) {
    if (placed.some((p) => collide(p, b, gap))) {
      const free = perimeterSpots(b, W, H, pad).find((s) => !placed.some((p) => collide(p, { ...b, ...s }, gap)));
      if (free) Object.assign(b, free);
    }
    placed.push(b);
  }
  return boxes;
}

// Nudge movable labels vertically until none overlaps another label or a fixed box (tag, pin).
// Boxes are centre-based {x, y, w, h}; only y changes, so labels stay above their spot.
export function separateLabels(boxes, fixed, H, gap = 3, maxIter = 24) {
  const all = [...fixed, ...boxes];
  for (let iter = 0; iter < maxIter; iter++) {
    let moved = false;
    for (const b of boxes) {
      for (const o of all) {
        if (o === b || !collide(o, b, gap)) continue;
        const need = (o.h + b.h) / 2 + gap - Math.abs(b.y - o.y);
        const dir = b.y > o.y || (b.y === o.y && boxes.indexOf(b) > boxes.indexOf(o)) ? 1 : -1;
        if (fixed.includes(o)) b.y += dir * need;
        else { b.y += (dir * need) / 2; o.y -= (dir * need) / 2; }
        moved = true;
      }
    }
    for (const b of boxes) b.y = clamp(b.y, b.h / 2 + 2, H - b.h / 2 - 2);
    if (!moved) break;
  }
  return boxes;
}

// ---- Badges hugging the map diamond (screen-space convex polygon of the slab) ----

const cross = (ax, ay, bx, by) => ax * by - ay * bx;
const EDGE_SAMPLES = 16;
const EDGE_PAD = 10;

// Distance along `dir` (unit) from `from` to where the ray leaves the convex polygon; 0 if outside.
export function rayExit(from, dir, poly) {
  let best = Infinity;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length];
    const ex = b.x - a.x, ey = b.y - a.y;
    const den = cross(dir.x, dir.y, ex, ey);
    if (Math.abs(den) < 1e-9) continue;
    const t = cross(a.x - from.x, a.y - from.y, ex, ey) / den; // along the ray
    const u = cross(a.x - from.x, a.y - from.y, dir.x, dir.y) / den; // along the edge
    if (t > 1e-9 && u >= -1e-9 && u <= 1 + 1e-9) best = Math.min(best, t);
  }
  return Number.isFinite(best) ? best : 0;
}

function pointInPoly(p, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i], b = poly[j];
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

// Centre-based box {x, y, w, h} against a convex polygon (corners, vertices and edge crossings).
export function boxHitsPoly(b, poly) {
  const x0 = b.x - b.w / 2, x1 = b.x + b.w / 2, y0 = b.y - b.h / 2, y1 = b.y + b.h / 2;
  const corners = [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }];
  if (corners.some((c) => pointInPoly(c, poly))) return true;
  if (poly.some((v) => v.x > x0 && v.x < x1 && v.y > y0 && v.y < y1)) return true;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], c = poly[(i + 1) % poly.length];
    const dx = c.x - a.x, dy = c.y - a.y;
    for (let k = 0; k <= EDGE_SAMPLES; k++) { // an edge can pass through the box between corners
      const px = a.x + (dx * k) / EDGE_SAMPLES, py = a.y + (dy * k) / EDGE_SAMPLES;
      if (px > x0 && px < x1 && py > y0 && py < y1) return true;
    }
  }
  return false;
}

const PUSH_STEP_PX = 2;
const PUSH_MAX_STEPS = 60;

function pushOut(b, dir, poly) {
  for (let s = 0; s < PUSH_MAX_STEPS && boxHitsPoly(b, poly); s++) {
    b.x += dir.x * PUSH_STEP_PX;
    b.y += dir.y * PUSH_STEP_PX;
  }
}

// Centre for a badge that sits `gap` px outside the polygon, on the ray from `center` along `dir`.
export function placeOutside(center, dir, halfW, halfH, poly, gap) {
  const k = rayExit(center, dir, poly) + halfW * Math.abs(dir.x) + halfH * Math.abs(dir.y) + gap;
  const b = { x: center.x + dir.x * k, y: center.y + dir.y * k, w: halfW * 2, h: halfH * 2 };
  pushOut(b, dir, poly); // the support-function estimate can clip a vertex: nudge clear
  const back = { ...b };
  // Pull back towards the map while it stays clear, so the badge hugs the edge.
  for (let s = 0; s < PUSH_MAX_STEPS; s++) {
    back.x -= dir.x * PUSH_STEP_PX;
    back.y -= dir.y * PUSH_STEP_PX;
    if (boxHitsPoly({ ...back, w: back.w + gap * 2, h: back.h + gap * 2 }, poly)) break;
    b.x = back.x;
    b.y = back.y;
  }
  return { x: b.x, y: b.y };
}

// Separate badges from each other and from fixed boxes, keep them inside W×H and off the polygon.
// Each box carries `dir` (its outward direction), used to push it back out when it slides onto the map.
export function spreadAround(boxes, poly, W, H, fixed = [], gap = 6, maxIter = 40) {
  const clampBox = (b) => {
    b.x = clamp(b.x, b.w / 2 + EDGE_PAD, W - b.w / 2 - EDGE_PAD);
    b.y = clamp(b.y, b.h / 2 + EDGE_PAD, H - b.h / 2 - EDGE_PAD);
  };
  const separate = (a, b, bothMove) => {
    const ox = (a.w + b.w) / 2 + gap - Math.abs(a.x - b.x);
    const oy = (a.h + b.h) / 2 + gap - Math.abs(a.y - b.y);
    if (ox <= 1e-6 || oy <= 1e-6) return false;
    const share = bothMove ? 0.5 : 1;
    if (ox < oy) {
      const s = (a.x <= b.x ? -1 : 1) * ox * share;
      a.x += s;
      if (bothMove) b.x -= s;
    } else {
      const s = (a.y <= b.y ? -1 : 1) * oy * share;
      a.y += s;
      if (bothMove) b.y -= s;
    }
    return true;
  };
  for (let iter = 0; iter < maxIter; iter++) {
    let moved = false;
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) moved = separate(boxes[i], boxes[j], true) || moved;
      for (const f of fixed) moved = separate(boxes[i], f, false) || moved;
    }
    for (const b of boxes) {
      clampBox(b);
      if (boxHitsPoly(b, poly)) {
        pushOut(b, b.dir, poly);
        clampBox(b);
        moved = true;
      }
    }
    if (!moved) break;
  }
  return boxes;
}
