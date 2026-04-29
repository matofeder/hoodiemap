import * as THREE from 'three';

let _activeTube = null;
let _activeFallback = null;

/**
 * Fetches a route from /api/route and renders the first ~450 m as a 3D tube.
 * Falls back to a dashed straight line if the API fails.
 */
export async function showRouteHint(scene, fromLat, fromLon, toLat, toLon, color) {
  hideRouteHint(scene);

  try {
    const resp = await fetch(
      `/api/route?from_lat=${fromLat}&from_lon=${fromLon}&to_lat=${toLat}&to_lon=${toLon}`
    );
    if (!resp.ok) throw new Error(`route ${resp.status}`);
    const data = await resp.json();
    const coords = data.routes?.[0]?.geometry?.coordinates;
    if (!coords || coords.length < 2) throw new Error('no geometry');

    const truncated = _truncateRoute(coords, 450);
    if (truncated.length < 2) throw new Error('too short');

    const pts = truncated.map(([lon, lat]) => {
      const { x, y } = _latLonToLocal(lat, lon, fromLat, fromLon);
      return new THREE.Vector3(x, 1.5, -y);
    });

    const curve = new THREE.CatmullRomCurve3(pts);
    const geo = new THREE.TubeGeometry(curve, Math.max(4, truncated.length * 2), 1.5, 6, false);
    const mat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(color),
      transparent: true,
      opacity: 0.85,
    });
    _activeTube = new THREE.Mesh(geo, mat);
    scene.add(_activeTube);
  } catch {
    _showFallback(scene, fromLat, fromLon, toLat, toLon, color);
  }
}

export function hideRouteHint(scene) {
  if (_activeTube) {
    _activeTube.geometry.dispose();
    _activeTube.material.dispose();
    scene.remove(_activeTube);
    _activeTube = null;
  }
  if (_activeFallback) {
    _activeFallback.geometry.dispose();
    _activeFallback.material.dispose();
    scene.remove(_activeFallback);
    _activeFallback = null;
  }
}

export function _latLonToLocal(lat, lon, centerLat, centerLon) {
  const metersPerDegLat = 111320;
  const metersPerDegLon = 111320 * Math.cos(centerLat * Math.PI / 180);
  return {
    x: (lon - centerLon) * metersPerDegLon,
    y: (lat - centerLat) * metersPerDegLat,
  };
}

function _showFallback(scene, fromLat, fromLon, toLat, toLon, color) {
  const bearing = _bearing(fromLat, fromLon, toLat, toLon);
  const rad = (bearing * Math.PI) / 180;
  const len = 430;
  const pts = [
    new THREE.Vector3(0, 1.0, 0),
    new THREE.Vector3(Math.sin(rad) * len, 1.0, -Math.cos(rad) * len),
  ];
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineDashedMaterial({
    color: new THREE.Color(color),
    dashSize: 10,
    gapSize: 6,
    transparent: true,
    opacity: 0.7,
  });
  _activeFallback = new THREE.Line(geo, mat);
  _activeFallback.computeLineDistances();
  scene.add(_activeFallback);
}

function _truncateRoute(coords, maxMeters) {
  let dist = 0;
  const result = [coords[0]];
  for (let i = 1; i < coords.length; i++) {
    const [lon0, lat0] = coords[i - 1];
    const [lon1, lat1] = coords[i];
    dist += _haversineM(lat0, lon0, lat1, lon1);
    result.push(coords[i]);
    if (dist >= maxMeters) break;
  }
  return result;
}

function _haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const r = Math.PI / 180;
  const phi1 = lat1 * r, phi2 = lat2 * r;
  const a = Math.sin((lat2 - lat1) * r / 2) ** 2
    + Math.cos(phi1) * Math.cos(phi2) * Math.sin((lon2 - lon1) * r / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function _bearing(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const phi1 = lat1 * r, phi2 = lat2 * r;
  const dlam = (lon2 - lon1) * r;
  const x = Math.sin(dlam) * Math.cos(phi2);
  const y = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dlam);
  return ((Math.atan2(x, y) / r) + 360) % 360;
}
