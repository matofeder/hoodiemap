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
