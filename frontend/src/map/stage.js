import * as THREE from 'three';
import { createOverlay } from '../overlay/labels.js';
import { mulberry32, seedFromCoords } from '../random.js';
import { addBuildings } from './buildings.js';
import { addCars } from './cars.js';
import { addGround } from './ground.js';
import { createMaterialCache } from './materials.js';
import { addProperty } from './property.js';
import { addTrees } from './trees.js';

const CAMERA_DIR = new THREE.Vector3(190, 215, 250).normalize();
const SUN_DIR = new THREE.Vector3(90, 160, 60).normalize();

export function createStage(container, scene) {
  const r = scene.radius_m;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const world = new THREE.Scene();
  world.add(new THREE.HemisphereLight('#FFFFFF', '#B7C9A8', 0.72 * Math.PI));
  const sun = new THREE.DirectionalLight('#FFF6E8', 0.7 * Math.PI);
  sun.position.copy(SUN_DIR).multiplyScalar(r * 2.5);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -r * 1.3, right: r * 1.3, top: r * 1.3, bottom: -r * 1.3, near: 1, far: r * 6 });
  sun.shadow.bias = -0.0005;
  world.add(sun);

  const mat = createMaterialCache();
  addGround(world, scene, mat);
  addBuildings(world, scene.buildings, scene.property?.building_index ?? null, mat);
  const trees = addTrees(world, scene, mat);
  const cars = addCars(world, scene.roads, mat, mulberry32(seedFromCoords(scene.center.lat, scene.center.lon) + 1));
  const property = addProperty(world, scene, mat);

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -r * 10, r * 10);
  camera.position.copy(CAMERA_DIR).multiplyScalar(r * 3);
  camera.lookAt(0, 0, 0);

  const v = new THREE.Vector3();
  const project = (x, y, h = 0) => {
    v.set(x, h, -y).project(camera);
    return { x: ((v.x + 1) / 2) * container.clientWidth, y: ((1 - v.y) / 2) * container.clientHeight };
  };
  const overlay = createOverlay(container, scene, project, property.anchor);

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
    property.update(t);
    trees.update(t);
    cars.update(t);
    renderer.render(world, camera);
    overlay.update();
  }

  let visible = true, raf = 0;
  function loop(ms) {
    raf = 0;
    if (!visible || document.hidden) return;
    frame(ms);
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
      ro.disconnect();
      io.disconnect();
      document.removeEventListener('visibilitychange', start);
      renderer.dispose();
    },
  };
}
