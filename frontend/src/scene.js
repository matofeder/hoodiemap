import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';
import { BUILDING_COLORS, BUILDING_COLOR_DEFAULT, GEO_LAYER_COLORS, ROAD_COLORS, ROAD_COLOR_DEFAULT } from './colors.js';
import { buildRibbonGeometry, buildDashLineGeometry } from './geometry.js';
import { addAnimations, addShrubs } from './animations.js';
import { addPOIs } from './poi.js';

let _activeScene = null;

if (import.meta.hot) {
  import.meta.hot.dispose(() => { _activeScene?.dispose(); });
}

export function createScene(container, sceneData, mode) {
  if (_activeScene) {
    _activeScene.dispose();
    _activeScene = null;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x87ceeb);
  scene.fog = new THREE.Fog(0xc9e8f4, 600, 1200);

  // Renderer
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setSize(container.clientWidth || window.innerWidth, container.clientHeight || window.innerHeight);
  container.innerHTML = '';
  container.appendChild(renderer.domElement);

  // CSS2D renderer for POI labels
  const labelRenderer = new CSS2DRenderer();
  labelRenderer.setSize(container.clientWidth || window.innerWidth, container.clientHeight || window.innerHeight);
  labelRenderer.domElement.style.position = 'absolute';
  labelRenderer.domElement.style.top = '0';
  labelRenderer.domElement.style.pointerEvents = 'none';
  container.appendChild(labelRenderer.domElement);

  // Camera
  const camera = new THREE.PerspectiveCamera(
    45,
    (container.clientWidth || window.innerWidth) / (container.clientHeight || window.innerHeight),
    0.1,
    2000,
  );
  camera.position.set(0, 300, 350);
  camera.lookAt(0, 0, 0);

  // Controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI / 2.2;
  controls.minDistance = 50;
  controls.maxDistance = 800;

  // Lights
  const ambient = new THREE.AmbientLight(0xffffff, 1.0);
  scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xfff5e0, 1.4);
  sun.position.set(300, 500, 200);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.near = 10;
  sun.shadow.camera.far = 1200;
  sun.shadow.camera.left = -700;
  sun.shadow.camera.right = 700;
  sun.shadow.camera.top = 700;
  sun.shadow.camera.bottom = -700;
  scene.add(sun);

  // Ground
  _addGround(scene, sceneData.bbox_m);

  // Geo layers (water / forest / park) — above ground, below roads and buildings
  if (sceneData.geo_layers) {
    _addGeoLayers(scene, sceneData.geo_layers);
  }

  // Roads
  _addRoads(scene, sceneData.roads);

  // Buildings
  _addBuildings(scene, sceneData.buildings);

  // Animations (cars, trees, pedestrians, center pin)
  const animatables = addAnimations(scene, sceneData);
  addShrubs(scene, sceneData);

  // POI markers
  if (sceneData.pois.length > 0) {
    addPOIs(scene, labelRenderer, camera, sceneData.pois);
  }

  // Resize handler
  function onResize() {
    const w = container.clientWidth || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    labelRenderer.setSize(w, h);
  }
  window.addEventListener('resize', onResize);

  // Animation loop
  let raf;
  function animate(time) {
    raf = requestAnimationFrame(animate);
    controls.update();
    animatables.forEach(fn => fn(time * 0.001));
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
  }
  animate(0);

  function dispose() {
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', onResize);
    renderer.dispose();
    container.innerHTML = '';
  }

  _activeScene = { dispose };
  return { dispose };
}


function _addGround(scene, bboxM) {
  const size = bboxM * 2.2;
  const geo = new THREE.PlaneGeometry(size, size);
  const mat = new THREE.MeshLambertMaterial({ color: 0x7ab648 });
  const ground = new THREE.Mesh(geo, mat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
}


function _addGeoLayers(scene, geoLayers) {
  ['water', 'forest', 'park'].forEach(layerName => {
    const rings = geoLayers[layerName];
    if (!rings || rings.length === 0) return;
    const color = GEO_LAYER_COLORS[layerName];
    rings.forEach(ring => {
      if (!ring || ring.length < 3) return;
      try {
        const shape = new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y)));
        const geo = new THREE.ShapeGeometry(shape);
        geo.rotateX(-Math.PI / 2);
        geo.translate(0, 0.05, 0);
        const mat = new THREE.MeshLambertMaterial({ color });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.receiveShadow = true;
        scene.add(mesh);
      } catch (err) {
        console.warn('_addGeoLayers: skipped ring in', layerName, err);
      }
    });
  });
}


function _addRoads(scene, roads) {
  const CENTER_LINE_TYPES = new Set(['primary', 'secondary', 'tertiary']);

  roads.forEach(road => {
    const style = ROAD_COLORS[road.type] || ROAD_COLOR_DEFAULT;
    if (road.points.length < 2) return;

    const pts = road.points.map(([x, y]) => new THREE.Vector3(x, 0, -y));
    const curve = new THREE.CatmullRomCurve3(pts);
    const width = style.width;

    // Road surface
    const surfaceGeo = buildRibbonGeometry(curve, width);
    const surfaceMat = new THREE.MeshLambertMaterial({ color: new THREE.Color(style.fill) });
    const surface = new THREE.Mesh(surfaceGeo, surfaceMat);
    surface.receiveShadow = true;
    scene.add(surface);

    // White edge strips (y = 0.16, width 0.3m each side)
    const edgeOffset = width / 2 + 0.15; // centre of 0.3m strip
    const edgeMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5 });
    for (const sign of [-1, 1]) {
      const offsetPts = _offsetCurvePoints(curve, sign * edgeOffset);
      const edgeCurve = new THREE.CatmullRomCurve3(offsetPts);
      const edgeGeo = buildRibbonGeometry(edgeCurve, 0.3, 1.0);
      const edgeMesh = new THREE.Mesh(edgeGeo, edgeMat);
      scene.add(edgeMesh);
    }

    // Dashed centre line for major roads
    if (CENTER_LINE_TYPES.has(road.type)) {
      const dashGeo = buildDashLineGeometry(curve, 2, 3, 0.17);
      const dashMat = new THREE.MeshBasicMaterial({ color: 0xf5d020 }); // yellow
      scene.add(new THREE.Mesh(dashGeo, dashMat));
    }
  });
}

/** Returns N evenly-spaced Vector3 points offset perpendicularly from a curve. */
function _offsetCurvePoints(curve, offsetM, n = 20) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const pos = curve.getPoint(t);
    const tan = curve.getTangent(t).normalize();
    pts.push(new THREE.Vector3(
      pos.x - tan.z * offsetM,
      pos.y,
      pos.z + tan.x * offsetM,
    ));
  }
  return pts;
}


function _addBuildings(scene, buildings) {
  buildings.forEach(b => {
    const colorHex = BUILDING_COLORS[b.type] || BUILDING_COLOR_DEFAULT;
    const color = new THREE.Color(colorHex);
    const darkColor = color.clone().multiplyScalar(0.7);

    const fp = b.footprint;
    if (!fp || fp.length < 3) return;

    try {
      const shape = new THREE.Shape(fp.map(([x, y]) => new THREE.Vector2(x, y)));
      const extGeo = new THREE.ExtrudeGeometry(shape, {
        depth: b.height,
        bevelEnabled: false,
      });
      extGeo.rotateX(-Math.PI / 2);

      const mat = new THREE.MeshLambertMaterial({ color });
      const mesh = new THREE.Mesh(extGeo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);

      // Flat roof cap
      const roofShape = new THREE.Shape(fp.map(([x, y]) => new THREE.Vector2(x, y)));
      const roofGeo = new THREE.ShapeGeometry(roofShape);
      roofGeo.rotateX(-Math.PI / 2);
      roofGeo.translate(0, b.height, 0);
      const roofMat = new THREE.MeshLambertMaterial({ color: darkColor });
      const roof = new THREE.Mesh(roofGeo, roofMat);
      scene.add(roof);
    } catch (err) {
      console.warn('_addBuildings: skipped footprint', b, err);
    }
  });
}
