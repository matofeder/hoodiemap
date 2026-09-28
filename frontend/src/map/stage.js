import * as THREE from 'three';
import { buildingInfo } from '../overlay/describe.js';
import { centroid } from './geom.js';
import { createOverlay } from '../overlay/labels.js';
import { createTooltip } from '../overlay/tooltip.js';
import { mulberry32, seedFromCoords } from '../random.js';
import { categoryInfo } from '../palette.js';
import { addBuildings } from './buildings.js';
import { addCars } from './cars.js';
import { addGround } from './ground.js';
import { createMaterialCache, squareClippingPlanes } from './materials.js';
import { createClouds } from './clouds.js';
import { createHover } from './hover.js';
import { addDecor } from './decor.js';
import { addChatGroups, addCyclists, addPedestrians } from './people.js';
import { addPigeons } from './pigeons.js';
import { gatheringSpots } from './placement.js';
import { addProperty } from './property.js';
import { addTrees } from './trees.js';
import { detailFor } from './detail.js';
import { addStreetFocus } from './focus.js';
import { tierLabel } from '../format.js';

const CAMERA_DIR = new THREE.Vector3(190, 215, 250).normalize();
const SUN_DIR = new THREE.Vector3(90, 160, 60).normalize();
const FRAME_MS = 1000 / 30; // gentle idle animation — 30 fps is plenty and halves GPU work

const STREET_NOTE = 'Presná adresa nie je uvedená';

export function createStage(container, scene) {
  const r = scene.radius_m;
  const detail = detailFor(scene.tier);
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.localClippingEnabled = true;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const world = new THREE.Scene();
  world.add(new THREE.HemisphereLight('#FFFFFF', '#B7C9A8', 0.72 * Math.PI));
  const sun = new THREE.DirectionalLight('#FFF6E8', 0.7 * Math.PI);
  sun.position.copy(SUN_DIR).multiplyScalar(r * 2.5);
  sun.castShadow = true;
  sun.shadow.mapSize.set(detail.shadowMap, detail.shadowMap);
  Object.assign(sun.shadow.camera, { left: -r * 1.3, right: r * 1.3, top: r * 1.3, bottom: -r * 1.3, near: 1, far: r * 6 });
  sun.shadow.bias = -0.0005;
  world.add(sun);

  const seed = seedFromCoords(scene.center.lat, scene.center.lon);
  const clouds = createClouds(r, mulberry32(seed + 4));
  const mat = createMaterialCache(squareClippingPlanes(r), clouds.patch);
  addGround(world, scene, mat, { lanes: detail.lanes });
  const highlights = new Map(scene.near_pois
    .filter((p) => p.building_index != null)
    .map((p) => [p.building_index, categoryInfo(p.category).color]));
  const buildingMeshes = addBuildings(world, scene.buildings, scene.property?.building_index ?? null, mat, highlights);
  const trees = addTrees(world, scene, mat, { seeded: detail.seededTrees });
  const cars = addCars(world, scene.roads, mat, mulberry32(seed + 1), detail.maxCars);
  if (detail.decor) addDecor(world, scene, mat);
  const spots = gatheringSpots(scene);
  const people = addPedestrians(world, scene.roads, mat, mulberry32(seed + 2), detail.people);
  const bikes = addCyclists(world, scene.roads, mat, mulberry32(seed + 3), detail.people);
  const idle = { update() {} };
  const groups = detail.pigeons ? addChatGroups(world, spots.slice(1), mat, mulberry32(seed + 5)) : idle;
  const pigeons = detail.pigeons ? addPigeons(world, spots[0] ?? null, r, mat, mulberry32(seed + 6)) : idle;
  const focus = detail.property ? addProperty(world, scene, mat)
    : detail.streetFocus ? addStreetFocus(world, scene.focus, mat, r)
      : { update() {}, anchor: null };
  const tagInfo = detail.streetFocus
    ? { title: `Na predaj · ${tierLabel('street')} ${scene.focus?.name ?? ''}`.trim(), lines: [STREET_NOTE], note: STREET_NOTE }
    : null;

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -r * 10, r * 10);
  camera.position.copy(CAMERA_DIR).multiplyScalar(r * 3);
  camera.lookAt(0, 0, 0);

  const v = new THREE.Vector3();
  const project = (x, y, h = 0) => {
    v.set(x, h, -y).project(camera);
    return { x: ((v.x + 1) / 2) * container.clientWidth, y: ((1 - v.y) / 2) * container.clientHeight };
  };
  const propertyIndex = scene.property?.building_index ?? null;
  const propertyAt = propertyIndex != null ? centroid(scene.buildings[propertyIndex].footprint) : null;
  const distanceFromProperty = (i) => {
    if (!propertyAt) return null;
    const [x, y] = centroid(scene.buildings[i].footprint);
    return Math.hypot(x - propertyAt[0], y - propertyAt[1]);
  };
  const poiByBuilding = new Map(scene.near_pois.filter((p) => p.building_index != null).map((p) => [p.building_index, p]));
  const tooltip = createTooltip(container);
  const hover = createHover({
    container, camera, meshes: buildingMeshes, world, buildings: scene.buildings, tooltip,
    describe: (i) => buildingInfo(scene.buildings[i], {
      isProperty: i === propertyIndex, poi: poiByBuilding.get(i), distanceM: distanceFromProperty(i),
    }),
    requestRender: () => { if (!raf) frame(performance.now()); },
  });
  const overlay = createOverlay(container, scene, project, focus.anchor, hover.onLabel, tagInfo);

  function fit() {
    const W = container.clientWidth, H = container.clientHeight, aspect = W / H;
    renderer.setSize(W, H);
    const hh = Math.max(0.8 * r, (1.22 * r) / aspect);
    Object.assign(camera, { left: -hh * aspect, right: hh * aspect, top: hh, bottom: -hh });
    camera.updateProjectionMatrix();
    overlay.measure();
  }

  function frame(ms) {
    const t = ms / 1000;
    focus.update(t);
    trees.update(t);
    cars.update(t);
    people.update(t);
    bikes.update(t);
    groups.update(t);
    pigeons.update(t);
    clouds.update(t);
    renderer.render(world, camera);
    overlay.update();
  }

  let visible = true, raf = 0, last = -Infinity;
  function loop(ms) {
    raf = 0;
    if (!visible || document.hidden) return;
    if (ms - last >= FRAME_MS - 1) {
      last = ms;
      frame(ms);
    }
    raf = requestAnimationFrame(loop);
  }
  function start() {
    if (!reduced && !raf && visible && !document.hidden) raf = requestAnimationFrame(loop);
  }

  fit();
  frame(0);
  const ro = new ResizeObserver(() => { fit(); frame(performance.now()); });
  ro.observe(container);
  const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; start(); });
  io.observe(container);
  document.addEventListener('visibilitychange', start);
  if (document.fonts) document.fonts.ready.then(() => { overlay.measure(); frame(performance.now()); });
  start();

  return {
    dispose() {
      cancelAnimationFrame(raf);
      raf = 0;
      visible = false;
      hover.dispose();
      overlay.dispose();
      tooltip.dispose();
      ro.disconnect();
      io.disconnect();
      document.removeEventListener('visibilitychange', start);
      world.traverse((o) => {
        o.geometry?.dispose();
        for (const m of [o.material].flat()) {
          m?.map?.dispose();
          m?.dispose();
        }
      });
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
  };
}
