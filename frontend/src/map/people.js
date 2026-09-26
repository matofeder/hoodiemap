import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { carPose, planCyclists, planPedestrians, planZoneWalkers } from './placement.js';

// Figures are ~2.6x life size (cars ~1x) — at widget scale real-size people are sub-pixel dots.
const PERSON_SCALE = 2.6;
const STEP_HZ = 2.2;
const BODY = new THREE.CylinderGeometry(0.28, 0.34, 0.8, 8);
const LEGS = new THREE.CylinderGeometry(0.22, 0.2, 0.6, 6);
const HEAD = new THREE.SphereGeometry(0.26, 10, 8);

function addMovers(world, plan, build, animate) {
  const groups = plan.map((m) => {
    const g = build(m);
    g.scale.setScalar(PERSON_SCALE);
    g.traverse((o) => { o.castShadow = true; });
    world.add(g);
    return g;
  });
  function update(t) {
    plan.forEach((m, i) => {
      const pose = carPose(m, t);
      groups[i].position.set(pose.x, 0.1, -pose.y);
      groups[i].rotation.y = pose.heading;
      animate(groups[i], m, t);
    });
  }
  update(0);
  return { update };
}

function makePerson(mat, color) {
  const g = new THREE.Group();
  const inner = new THREE.Group();
  const l = new THREE.Mesh(LEGS, mat(PALETTE.bike, { clip: true }));
  l.position.y = 0.3;
  const b = new THREE.Mesh(BODY, mat(color, { clip: true }));
  b.position.y = 1.0;
  const h = new THREE.Mesh(HEAD, mat(PALETTE.skin, { clip: true }));
  h.position.y = 1.62;
  inner.add(l, b, h);
  g.add(inner);
  return g;
}

const walkBob = (g, m, t) => {
  g.children[0].position.y = Math.abs(Math.sin((t * STEP_HZ + m.phase) * Math.PI)) * 0.1;
};

export function addPedestrians(world, roads, mat, rng) {
  const plan = [...planPedestrians(roads, rng), ...planZoneWalkers(roads, rng)];
  return addMovers(world, plan, (m) => makePerson(mat, m.color), walkBob);
}

const GROUP_RADIUS_M = 2.2;

// Two or three people standing in a circle and chatting (gentle sway, one of them gesturing).
export function addChatGroups(world, spots, mat, rng) {
  const people = [];
  spots.slice(0, 3).forEach(([cx, cy], gi) => {
    const n = 2 + (rng() < 0.5 ? 1 : 0), a0 = rng() * Math.PI * 2;
    for (let i = 0; i < n; i++) {
      const a = a0 + (i / n) * Math.PI * 2;
      const x = cx + Math.cos(a) * GROUP_RADIUS_M, y = cy + Math.sin(a) * GROUP_RADIUS_M;
      const p = makePerson(mat, PALETTE.shirts[(gi * 3 + i + 1) % PALETTE.shirts.length]);
      p.position.set(x, 0.1, -y);
      p.rotation.y = a + Math.PI; // face the centre
      p.scale.setScalar(PERSON_SCALE);
      p.traverse((o) => { o.castShadow = true; });
      world.add(p);
      people.push({ p, phase: rng() * 6 });
    }
  });
  return {
    update(t) {
      for (const { p, phase } of people) p.children[0].rotation.z = Math.sin(t * 1.3 + phase) * 0.06;
    },
  };
}

export function addCyclists(world, roads, mat, rng) {
  const wheel = new THREE.TorusGeometry(0.42, 0.07, 6, 16);
  const frame = new THREE.BoxGeometry(1.0, 0.08, 0.08);
  const body = new THREE.CylinderGeometry(0.24, 0.3, 0.75, 8);
  const head = new THREE.SphereGeometry(0.25, 10, 8);
  return addMovers(world, planCyclists(roads, rng), (m) => {
    const g = new THREE.Group();
    const dark = mat(PALETTE.bike, { clip: true });
    for (const x of [-0.55, 0.55]) {
      const w = new THREE.Mesh(wheel, dark);
      w.position.set(x, 0.49, 0);
      g.add(w);
    }
    const f = new THREE.Mesh(frame, dark);
    f.position.y = 0.72;
    const rider = new THREE.Group();
    const b = new THREE.Mesh(body, mat(m.color, { clip: true }));
    b.position.y = 1.2;
    b.rotation.z = -0.35; // leaning forward over the handlebars
    const h = new THREE.Mesh(head, mat(PALETTE.skin, { clip: true }));
    h.position.set(0.2, 1.72, 0);
    rider.add(b, h);
    g.add(f, rider);
    return g;
  }, (g, m, t) => {
    g.children.at(-1).position.y = Math.sin((t * 1.6 + m.phase) * Math.PI) * 0.03;
  });
}
