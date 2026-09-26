import * as THREE from 'three';
import { PALETTE } from '../palette.js';

const COUNT = 8;
const BIRD_SCALE = 2.4;
const SPREAD_M = 4;
// One loop: peck on the ground, take off, circle the square, land again.
const CYCLE_S = 18, TAKEOFF_S = 10, CIRCLE_S = 11.5, LAND_S = 15.5;
const CIRCLE_R = 11, CIRCLE_H = 13;

const smooth = (a) => a * a * (3 - 2 * a);

// Pure: where bird i is at time t (backend x/y metres + height), and whether it is flying.
export function birdPosition(home, bird, t, centre = home) {
  const tc = ((t + bird.delay) % CYCLE_S + CYCLE_S) % CYCLE_S;
  const [hx, hy] = [home[0] + bird.dx, home[1] + bird.dy];
  const orbit = (tt) => {
    const a = bird.angle + tt * 0.9;
    return [centre[0] + Math.cos(a) * (CIRCLE_R + bird.dr), centre[1] + Math.sin(a) * (CIRCLE_R + bird.dr),
      CIRCLE_H + bird.dr + Math.sin(tt * 2 + bird.angle) * 0.8];
  };
  if (tc < TAKEOFF_S) {
    const wander = Math.sin(tc * 0.6 + bird.angle) * 0.6;
    return { x: hx + wander, y: hy, h: 0, flying: false };
  }
  if (tc < CIRCLE_S) {
    const k = smooth((tc - TAKEOFF_S) / (CIRCLE_S - TAKEOFF_S)), [ox, oy, oh] = orbit(tc - TAKEOFF_S);
    return { x: hx + (ox - hx) * k, y: hy + (oy - hy) * k, h: oh * k, flying: true };
  }
  if (tc < LAND_S) {
    const [ox, oy, oh] = orbit(tc - TAKEOFF_S);
    return { x: ox, y: oy, h: oh, flying: true };
  }
  const k = smooth((tc - LAND_S) / (CYCLE_S - LAND_S)), [ox, oy, oh] = orbit(tc - TAKEOFF_S);
  return { x: ox + (hx - ox) * k, y: oy + (hy - oy) * k, h: oh * (1 - k), flying: k < 0.98 };
}

export function addPigeons(world, home, r, mat, rng) {
  if (!home) return { update() {} };
  // Circle over the square but keep the whole orbit above the map.
  const lim = r - CIRCLE_R - 14; // height lifts birds up-screen, so keep well inside
  const centre = home.map((v) => Math.max(-lim, Math.min(lim, v)));
  const body = new THREE.SphereGeometry(0.22, 10, 8);
  const head = new THREE.SphereGeometry(0.12, 8, 6);
  const wing = new THREE.BoxGeometry(0.3, 0.03, 0.34);
  wing.translate(0, 0, 0.17); // hinge at the body
  const grey = mat(PALETTE.pigeon, { clip: true }), dark = mat(PALETTE.pigeonHead, { clip: true });
  const birds = Array.from({ length: COUNT }, () => {
    const a = rng() * Math.PI * 2, d = Math.sqrt(rng()) * SPREAD_M;
    const bird = { dx: Math.cos(a) * d, dy: Math.sin(a) * d, angle: rng() * Math.PI * 2, dr: rng() * 3, delay: rng() * 0.8 };
    const g = new THREE.Group();
    const b = new THREE.Mesh(body, grey);
    b.scale.set(1.3, 0.9, 0.9);
    b.position.y = 0.25;
    const h = new THREE.Mesh(head, dark);
    h.position.set(0.28, 0.42, 0);
    const wl = new THREE.Mesh(wing, grey), wr = new THREE.Mesh(wing, grey);
    wl.position.set(0, 0.32, 0.12);
    wr.position.set(0, 0.32, -0.12);
    wr.rotation.y = Math.PI;
    g.add(b, h, wl, wr);
    g.scale.setScalar(BIRD_SCALE);
    g.traverse((o) => { o.castShadow = true; });
    world.add(g);
    return { bird, g, h, wl, wr, heading: rng() * Math.PI * 2 };
  });

  function update(t) {
    for (const p of birds) {
      const now = birdPosition(home, p.bird, t, centre), next = birdPosition(home, p.bird, t + 0.1, centre);
      p.g.position.set(now.x, 0.06 + now.h, -now.y);
      const dx = next.x - now.x, dy = next.y - now.y;
      if (Math.hypot(dx, dy) > 0.02) p.heading = Math.atan2(dy, dx);
      p.g.rotation.y = p.heading;
      const flap = now.flying ? Math.sin(t * 22 + p.bird.angle) * 0.9 : -0.1;
      p.wl.rotation.x = -flap;
      p.wr.rotation.x = flap;
      p.h.position.y = now.flying ? 0.42 : 0.42 - Math.max(0, Math.sin(t * 5 + p.bird.angle)) * 0.14; // pecking
    }
  }
  update(0);
  return { update };
}
