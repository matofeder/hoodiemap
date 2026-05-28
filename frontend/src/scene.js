import * as THREE from 'three';
import { BUILDING_COLORS, BUILDING_COLOR_DEFAULT, GEO_LAYER_COLORS, ROAD_COLORS, ROAD_COLOR_DEFAULT, POI_COLORS } from './colors.js';
import { buildRibbonGeometry, buildDashLineGeometry } from './geometry.js';
import { addAnimations, addShrubs, addCyclists } from './animations.js';
import { addPOIMarkers } from './poi.js';

const HOUSE_TYPES      = new Set(['house', 'detached', 'bungalow']);
const APARTMENT_TYPES  = new Set(['apartments', 'residential', 'terrace']);
const CHURCH_TYPES     = new Set(['church', 'cathedral', 'chapel', 'monastery']);
const COMMERCIAL_TYPES = new Set(['commercial', 'retail', 'supermarket', 'kiosk']);
const OFFICE_TYPES     = new Set(['office', 'civic', 'public', 'government']);
const INDUSTRIAL_TYPES = new Set(['industrial', 'warehouse', 'factory']);

let _activeScene = null;

if (import.meta.hot) {
  import.meta.hot.dispose(() => { _activeScene?.dispose(); });
}

export function createScene(container, sceneData) {
  if (_activeScene) {
    _activeScene.dispose();
    _activeScene = null;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xF0F4F8);

  // Fixed canvas size — infographic layout controls dimensions via CSS
  const W = container.clientWidth || 800;
  const H = container.clientHeight || 676;

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setSize(W, H);
  container.innerHTML = '';
  container.appendChild(renderer.domElement);

  // Fixed isometric-ish camera — no user control
  const camera = new THREE.PerspectiveCamera(42, W / H, 0.1, 2000);
  camera.position.set(0, 380, 520);
  camera.lookAt(0, 0, 0);

  // Lights
  const ambient = new THREE.AmbientLight(0xffffff, 1.0);
  scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xfff5e0, 1.4);
  sun.position.set(200, 500, 300);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.near = 10;
  sun.shadow.camera.far = 1200;
  sun.shadow.camera.left = -700;
  sun.shadow.camera.right = 700;
  sun.shadow.camera.top = 700;
  sun.shadow.camera.bottom = -700;
  scene.add(sun);

  _addGround(scene, sceneData.bbox_m);

  if (sceneData.geo_layers) {
    _addGeoLayers(scene, sceneData.geo_layers);
  }

  _addRoads(scene, sceneData.roads);
  _addBuildings(scene, sceneData.buildings);

  const animatables = [
    ...addAnimations(scene, sceneData),
    ...addCyclists(scene, sceneData.roads, (sceneData.display_radius_m || 600) * 1.2),
  ];
  addShrubs(scene, sceneData);

  if (sceneData.pois.length > 0) {
    addPOIMarkers(scene, sceneData.pois);
  }

  if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
    addOuterNeedles(scene, sceneData.outer_pois, sceneData.display_radius_m || 600);
  }

  let raf;
  function animate(time) {
    raf = requestAnimationFrame(animate);
    animatables.forEach(fn => fn(time * 0.001));
    renderer.render(scene, camera);
  }
  animate(0);

  function dispose() {
    cancelAnimationFrame(raf);
    renderer.dispose();
    container.innerHTML = '';
  }

  _activeScene = { dispose };
  return { dispose, scene };
}


function _addGround(scene, bboxM) {
  const size = bboxM * 2.2;
  const geo = new THREE.PlaneGeometry(size, size);
  const mat = new THREE.MeshLambertMaterial({ color: 0xc8bfb0 });
  const ground = new THREE.Mesh(geo, mat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
}


function _addGeoLayers(scene, geoLayers) {
  const Y_OFFSET = { residential: 0.03, forest: 0.05, park: 0.05, water: 0.07 };

  ['residential', 'water', 'forest', 'park'].forEach(layerName => {
    const rings = geoLayers[layerName];
    if (!rings || rings.length === 0) return;
    const color = GEO_LAYER_COLORS[layerName];
    const yOff = Y_OFFSET[layerName] ?? 0.05;
    rings.forEach(ring => {
      if (!ring || ring.length < 3) return;
      try {
        const shape = new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y)));
        const geo = new THREE.ShapeGeometry(shape);
        geo.rotateX(-Math.PI / 2);
        geo.translate(0, yOff, 0);
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

      const roofGroup = _buildRoof(b.type || 'yes', fp, b.height, colorHex);
      scene.add(roofGroup);
    } catch (err) {
      console.warn('_addBuildings: skipped footprint', b, err);
    }
  });
}

function _buildRoof(type, footprint, height, baseColorHex) {
  const group = new THREE.Group();
  const xs = footprint.map(([x]) => x);
  const ys = footprint.map(([, y]) => y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = maxX - minX, d = maxY - minY;
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

  if (HOUSE_TYPES.has(type)) {
    const ridgeH = Math.min(w, d) * 0.4;
    const topY = height + ridgeH;
    const color = new THREE.Color(baseColorHex).multiplyScalar(0.75);
    const mat = new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide });
    let verts;
    if (w >= d) {
      const cz = -(minY + maxY) / 2;
      verts = new Float32Array([
        minX, height, -minY,  maxX, height, -minY,  minX, topY, cz,
        maxX, height, -minY,  maxX, topY, cz,        minX, topY, cz,
        minX, height, -maxY,  minX, topY, cz,        maxX, height, -maxY,
        maxX, height, -maxY,  minX, topY, cz,        maxX, topY, cz,
        minX, height, -minY,  minX, topY, cz,        minX, height, -maxY,
        maxX, height, -minY,  maxX, height, -maxY,  maxX, topY, cz,
      ]);
    } else {
      verts = new Float32Array([
        minX, height, -minY,  cx, topY, -minY,  minX, height, -maxY,
        cx,   topY,   -minY,  cx, topY, -maxY,  minX, height, -maxY,
        maxX, height, -minY,  maxX, height, -maxY,  cx, topY, -minY,
        maxX, height, -maxY,  cx, topY, -maxY,       cx, topY, -minY,
        minX, height, -minY,  maxX, height, -minY,  cx, topY, -minY,
        minX, height, -maxY,  cx, topY, -maxY,       maxX, height, -maxY,
      ]);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.computeVertexNormals();
    group.add(new THREE.Mesh(geo, mat));

  } else if (CHURCH_TYPES.has(type)) {
    _addFlatRoofCap(group, footprint, height, baseColorHex);
    const spireGeo = new THREE.ConeGeometry(0.8, 15, 4);
    const spireMat = new THREE.MeshLambertMaterial({ color: 0x9e8ac0 });
    const spire = new THREE.Mesh(spireGeo, spireMat);
    spire.position.set(cx, height + 7.5, -cy);
    spire.castShadow = true;
    group.add(spire);

  } else if (COMMERCIAL_TYPES.has(type)) {
    _addFlatRoofCap(group, footprint, height, baseColorHex);
  } else if (APARTMENT_TYPES.has(type) && height > 5) {
    _addFlatRoofCap(group, footprint, height, baseColorHex);
    _addWindows(group, footprint, height);

  } else if (OFFICE_TYPES.has(type) && height > 5) {
    _addFlatRoofCap(group, footprint, height, baseColorHex);
    _addWindows(group, footprint, height);

  } else if (INDUSTRIAL_TYPES.has(type)) {
    const ridgeH = Math.min(w, d) * 0.2;
    const color = new THREE.Color(baseColorHex).multiplyScalar(0.80);
    const mat = new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide });
    const verts = new Float32Array([
      minX, height,          -minY,
      maxX, height,          -minY,
      maxX, height + ridgeH, -minY,
      minX, height,          -minY,
      maxX, height + ridgeH, -minY,
      minX, height + ridgeH, -minY,
      minX, height,          -maxY,
      minX, height + ridgeH, -minY,
      maxX, height,          -maxY,
      maxX, height,          -maxY,
      minX, height + ridgeH, -minY,
      maxX, height + ridgeH, -minY,
    ]);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.computeVertexNormals();
    group.add(new THREE.Mesh(geo, mat));

  } else {
    _addFlatRoofCap(group, footprint, height, baseColorHex);
  }

  return group;
}

function _addFlatRoofCap(group, footprint, height, baseColorHex) {
  const color = new THREE.Color(baseColorHex).multiplyScalar(0.7);
  try {
    const shape = new THREE.Shape(footprint.map(([x, y]) => new THREE.Vector2(x, y)));
    const geo = new THREE.ShapeGeometry(shape);
    geo.rotateX(-Math.PI / 2);
    geo.translate(0, height, 0);
    const mat = new THREE.MeshLambertMaterial({ color });
    group.add(new THREE.Mesh(geo, mat));
  } catch (_) {}
}

function _addWindows(group, footprint, height) {
  const xs = footprint.map(([x]) => x);
  const ys = footprint.map(([, y]) => y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);

  const winMat = new THREE.MeshBasicMaterial({ color: 0xadd8e6 });
  const WIN_W = 0.8, WIN_H = 0.6, WIN_D = 0.1;
  const FLOOR_STEP = 2.5, SPACING = 1.8;

  let windowCount = 0;
  const MAX_WIN = 60;

  for (let floorY = 1.2; floorY < height - 0.5 && windowCount < MAX_WIN; floorY += FLOOR_STEP) {
    for (let wx = minX + 1; wx < maxX - 0.5 && windowCount < MAX_WIN; wx += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_W, WIN_H, WIN_D);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(wx, floorY, -minY - WIN_D / 2);
      group.add(mesh);
      windowCount++;
    }
    for (let wx = minX + 1; wx < maxX - 0.5 && windowCount < MAX_WIN; wx += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_W, WIN_H, WIN_D);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(wx, floorY, -maxY + WIN_D / 2);
      group.add(mesh);
      windowCount++;
    }
    for (let wy = minY + 1; wy < maxY - 0.5 && windowCount < MAX_WIN; wy += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_D, WIN_H, WIN_W);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(minX - WIN_D / 2, floorY, -wy);
      group.add(mesh);
      windowCount++;
    }
    for (let wy = minY + 1; wy < maxY - 0.5 && windowCount < MAX_WIN; wy += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_D, WIN_H, WIN_W);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(maxX + WIN_D / 2, floorY, -wy);
      group.add(mesh);
      windowCount++;
    }
  }
}

export function addOuterNeedles(scene, outerPois, displayRadiusM) {
  const needles = [];
  const needleR = displayRadiusM * 0.93;

  outerPois.forEach(poi => {
    const colorHex = POI_COLORS[poi.category] || '#888888';
    const color = new THREE.Color(colorHex);
    const rad = (poi.bearing_deg * Math.PI) / 180;
    const x = Math.sin(rad) * needleR;
    const z = -Math.cos(rad) * needleR;

    const geo = new THREE.ConeGeometry(3, 15, 6);
    const mat = new THREE.MeshLambertMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.25,
    });
    const needle = new THREE.Mesh(geo, mat);
    needle.position.set(x, 8, z);
    needle.castShadow = false;
    scene.add(needle);
    needle.userData.poiCategory = poi.category;
    needles.push({ mesh: needle, mat, poi });
  });

  return {
    highlight(activePoi) {
      needles.forEach(({ mat, poi }) => {
        mat.emissiveIntensity = poi === activePoi ? 1.0 : 0.25;
      });
    },
  };
}
