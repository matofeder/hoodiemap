import { formatDistance, poiTitle } from '../format.js';
import { iconSvg } from '../icons.js';
import { categoryInfo } from '../palette.js';
import { buildingInfo, poiInfo } from './describe.js';
import { convexHull } from '../map/geom.js';
import { edgePoint, placeOutside, resolveOverlaps, separateLabels, spreadAround } from './edge.js';

const NEAR_LABEL_HEIGHT_M = 6;
const ROOF_CLEARANCE_M = 3;
const LABEL_NUDGE_PX = 11; // label is anchored on its icon centre
// Extra local categories: an icon marker on the roof is enough, full labels would crowd the map.
const MINI = new Set(['food', 'post', 'bank', 'doctors', 'playground']);
const BEARING_PROBE_M = 80;
// Places within this distance hug the map tile; cities and farther places sit on the widget edge.
const RING_MAX_M = 5000;
const RING_GAP_PX = 12;
const SLAB_DEPTH_M = 10; // the slab's side faces are part of the map's silhouette
const BOTTOM_RESERVED_PX = 44; // address chip and compass live in the bottom band

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

// Hover, tap and keyboard focus all report to onLabel(info, buildingIndex, node, pinned).
function interactive(node, info, buildingIndex, onLabel) {
  node.tabIndex = 0;
  node.addEventListener('pointerenter', (e) => { if (e.pointerType !== 'touch') onLabel(info, buildingIndex, node, false); });
  node.addEventListener('pointerleave', (e) => { if (e.pointerType !== 'touch') onLabel(null); });
  node.addEventListener('pointerdown', (e) => { if (e.pointerType === 'touch') onLabel(info, buildingIndex, node, true); });
  node.addEventListener('focus', () => onLabel(info, buildingIndex, node, false));
  node.addEventListener('blur', () => onLabel(null));
}

function place(node, x, y, anchor) {
  node.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) ${anchor}`;
}

export function createOverlay(container, scene, project, anchor, onLabel = () => {}, tagInfo = null) {
  const root = el('div', 'gm-overlay', container);

  const tag = anchor ? el('div', 'gm-tag', root) : null;
  if (tag) {
    tag.textContent = 'Na predaj';
    if (tagInfo?.note) tag.appendChild(text('small', tagInfo.note));
    const propertyIndex = scene.property?.building_index ?? null;
    const info = propertyIndex != null
      ? buildingInfo(scene.buildings[propertyIndex], { isProperty: true })
      : tagInfo;
    if (info) interactive(tag, info, propertyIndex, onLabel);
  }

  const nears = scene.near_pois.map((p) => {
    const title = p.name || categoryInfo(p.category).label;
    const node = el('div', MINI.has(p.category) ? 'gm-near is-mini' : 'gm-near', root);
    if (MINI.has(p.category)) {
      node.setAttribute('aria-label', title);
      node.append(icon(p.category));
    } else {
      node.append(icon(p.category), text('b', title), text('em', formatDistance(p.distance_m)));
    }
    interactive(node, poiInfo(p), p.building_index ?? null, onLabel);
    const b = p.building_index != null ? scene.buildings[p.building_index] : null;
    return { p, node, w: 0, h: 0, lift: b ? b.height + ROOF_CLEARANCE_M : NEAR_LABEL_HEIGHT_M };
  });

  const fars = scene.far_pois.map((p) => {
    const node = el('div', 'gm-far', root);
    const label = el('span', 'gm-far-text');
    label.append(text('b', poiTitle(p)), text('em', formatDistance(p.distance_m)));
    const arrow = el('span', 'gm-arrow');
    arrow.innerHTML = iconSvg('arrow');
    node.append(icon(p.category), label, arrow);
    interactive(node, poiInfo(p), null, onLabel);
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
    if (tag) { tag.w = tag.offsetWidth; tag.h = tag.offsetHeight; }
    for (const f of fars) {
      f.w = f.node.offsetWidth;
      f.h = f.node.offsetHeight;
    }
  }

  function update() {
    const W = container.clientWidth, H = container.clientHeight;
    const centre = anchor ?? { x: 0, y: 0, h: 0, base: 0 };

    const c = project(centre.x, centre.y, 0);
    const r = scene.radius_m, Hb = H - BOTTOM_RESERVED_PX;
    const silhouette = convexHull([-r, r].flatMap((x) => [-r, r].flatMap((y) =>
      [0, -SLAB_DEPTH_M].map((h) => { const q = project(x, y, h); return [q.x, q.y]; }))))
      .map(([x, y]) => ({ x, y }));
    const outer = [], ring = [];
    const boxes = fars.map((f) => {
      const b = (f.p.bearing_deg * Math.PI) / 180;
      const q = project(centre.x + Math.sin(b) * BEARING_PROBE_M, centre.y + Math.cos(b) * BEARING_PROBE_M, 0);
      let dx = q.x - c.x, dy = q.y - c.y;
      const len = Math.hypot(dx, dy) || 1;
      dx /= len; dy /= len;
      f.arrow.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
      const dir = { x: dx, y: dy };
      const onRing = f.p.category !== 'city' && f.p.distance_m < RING_MAX_M;
      const pt = onRing
        ? placeOutside(c, dir, f.w / 2, f.h / 2, silhouette, RING_GAP_PX)
        : edgePoint(c, dir, f.w / 2, f.h / 2, W, Hb);
      const box = { x: pt.x, y: pt.y, w: f.w, h: f.h, dir };
      (onRing ? ring : outer).push(box);
      return box;
    });
    resolveOverlaps(outer, W, Hb);
    spreadAround(ring, silhouette, W, Hb, outer);
    boxes.forEach((b, i) => place(fars[i].node, b.x, b.y, 'translate(-50%, -50%)'));

    // The tag, the pin and the property below it are fixed; near labels step aside vertically.
    const fixed = [];
    if (tag) {
      const top = project(anchor.x, anchor.y, anchor.h);
      place(tag, top.x, top.y, 'translate(-50%, -100%)');
      const pinBottom = project(anchor.x, anchor.y, 0).y;
      fixed.push({ x: top.x, y: (top.y - tag.h + pinBottom) / 2, w: Math.max(tag.w, 44), h: pinBottom - top.y + tag.h });
    }
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
  return { update, measure, dispose: () => root.remove() };
}
