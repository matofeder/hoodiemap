import { formatDistance, poiTitle } from '../format.js';
import { iconSvg } from '../icons.js';
import { categoryInfo } from '../palette.js';
import { edgePoint, resolveOverlaps, separateLabels } from './edge.js';

const NEAR_LABEL_HEIGHT_M = 6;
const ROOF_CLEARANCE_M = 3;
const LABEL_NUDGE_PX = 11; // label is anchored on its icon centre
// Extra local categories: an icon marker on the roof is enough, full labels would crowd the map.
const MINI = new Set(['food', 'post', 'bank', 'doctors', 'playground']);
const BEARING_PROBE_M = 80;

function el(tag, className, parent) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (parent) parent.appendChild(node);
  return node;
}

function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}

function icon(category) {
  const node = el('i', 'gm-icon');
  node.style.setProperty('--c', categoryInfo(category).color);
  node.innerHTML = iconSvg(category);
  return node;
}

function place(node, x, y, anchor) {
  node.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) ${anchor}`;
}

export function createOverlay(container, scene, project, anchor) {
  const root = el('div', 'gm-overlay', container);

  const tag = el('div', 'gm-tag', root);
  tag.textContent = 'Na predaj';

  const nears = scene.near_pois.map((p) => {
    const title = p.name || categoryInfo(p.category).label;
    const node = el('div', MINI.has(p.category) ? 'gm-near is-mini' : 'gm-near', root);
    if (MINI.has(p.category)) {
      node.title = `${title} · ${formatDistance(p.distance_m)}`;
      node.append(icon(p.category));
    } else {
      node.append(icon(p.category), text('b', title), text('em', formatDistance(p.distance_m)));
    }
    const b = p.building_index != null ? scene.buildings[p.building_index] : null;
    return { p, node, w: 0, h: 0, lift: b ? b.height + ROOF_CLEARANCE_M : NEAR_LABEL_HEIGHT_M };
  });

  const fars = scene.far_pois.map((p) => {
    const node = el('div', 'gm-far', root);
    const label = el('span', 'gm-far-text');
    label.append(text('b', poiTitle(p)), text('em', formatDistance(p.distance_m)));
    const arrow = el('span', 'gm-arrow');
    arrow.innerHTML = iconSvg('arrow');
    node.title = p.name || categoryInfo(p.category).label;
    node.append(icon(p.category), label, arrow);
    return { p, node, arrow, w: 0, h: 0 };
  });

  if (scene.address) {
    const address = el('div', 'gm-address', root);
    const pin = el('i', 'gm-pin');
    pin.innerHTML = iconSvg('pin');
    address.append(pin, text('span', scene.address));
  }

  const north = el('div', 'gm-north', root);
  const needle = el('span', 'gm-needle', north);
  needle.innerHTML = iconSvg('north');
  north.append(text('b', 'S'));

  function measure() {
    for (const n of nears) {
      n.w = n.node.offsetWidth;
      n.h = n.node.offsetHeight;
    }
    tag.w = tag.offsetWidth;
    tag.h = tag.offsetHeight;
    for (const f of fars) {
      f.w = f.node.offsetWidth;
      f.h = f.node.offsetHeight;
    }
  }

  function update() {
    const W = container.clientWidth, H = container.clientHeight;
    const top = project(anchor.x, anchor.y, anchor.h);
    place(tag, top.x, top.y, 'translate(-50%, -100%)');

    const c = project(anchor.x, anchor.y, 0);
    const boxes = fars.map((f) => {
      const b = (f.p.bearing_deg * Math.PI) / 180;
      const q = project(anchor.x + Math.sin(b) * BEARING_PROBE_M, anchor.y + Math.cos(b) * BEARING_PROBE_M, 0);
      let dx = q.x - c.x, dy = q.y - c.y;
      const len = Math.hypot(dx, dy) || 1;
      dx /= len; dy /= len;
      f.arrow.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
      const pt = edgePoint(c, { x: dx, y: dy }, f.w / 2, f.h / 2, W, H);
      return { x: pt.x, y: pt.y, w: f.w, h: f.h };
    });
    resolveOverlaps(boxes, W, H);
    boxes.forEach((b, i) => place(fars[i].node, b.x, b.y, 'translate(-50%, -50%)'));

    // The tag, the pin and the property below it are fixed; near labels step aside vertically.
    const pinBottom = project(anchor.x, anchor.y, 0).y;
    const fixed = [{ x: top.x, y: (top.y - tag.h + pinBottom) / 2, w: Math.max(tag.w, 44), h: pinBottom - top.y + tag.h }];
    const nearBoxes = nears.map((n) => {
      const q = project(n.p.x, n.p.y, n.lift);
      const left = Math.min(Math.max(q.x, 15), W - n.w - 4 + LABEL_NUDGE_PX) - LABEL_NUDGE_PX;
      return { x: left + n.w / 2, y: q.y, w: n.w, h: n.h };
    });
    separateLabels(nearBoxes, [...fixed, ...boxes], H);
    nearBoxes.forEach((b, i) => place(nears[i].node, b.x - b.w / 2 + LABEL_NUDGE_PX, b.y, 'translate(-11px, -50%)'));

    const o = project(0, 0, 0), n = project(0, 50, 0);
    needle.style.transform = `rotate(${Math.atan2(n.y - o.y, n.x - o.x) + Math.PI / 2}rad)`;
  }

  measure();
  return { update, measure };
}
