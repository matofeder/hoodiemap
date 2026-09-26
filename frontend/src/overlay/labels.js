import { formatDistance, poiTitle } from '../format.js';
import { iconSvg } from '../icons.js';
import { categoryInfo } from '../palette.js';
import { edgePoint, resolveOverlaps } from './edge.js';

const NEAR_LABEL_HEIGHT_M = 16;
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
    const node = el('div', 'gm-near', root);
    node.append(icon(p.category), text('b', p.name || categoryInfo(p.category).label), text('em', formatDistance(p.distance_m)));
    return { p, node, w: 0 };
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
    for (const n of nears) n.w = n.node.offsetWidth;
    for (const f of fars) {
      f.w = f.node.offsetWidth;
      f.h = f.node.offsetHeight;
    }
  }

  function update() {
    const W = container.clientWidth, H = container.clientHeight;
    const top = project(anchor.x, anchor.y, anchor.h);
    place(tag, top.x, top.y, 'translate(-50%, -100%)');

    for (const n of nears) {
      const q = project(n.p.x, n.p.y, NEAR_LABEL_HEIGHT_M);
      const x = Math.min(Math.max(q.x, 15), W - n.w - 4 + 11);
      place(n.node, x, q.y, 'translate(-11px, -50%)');
    }

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

    const o = project(0, 0, 0), n = project(0, 50, 0);
    needle.style.transform = `rotate(${Math.atan2(n.y - o.y, n.x - o.x) + Math.PI / 2}rad)`;
  }

  measure();
  return { update, measure };
}
