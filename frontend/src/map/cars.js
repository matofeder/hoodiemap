import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { carPose, planCars } from './placement.js';

export function addCars(world, roads, mat, rng) {
  const cars = planCars(roads, rng);
  const body = new THREE.BoxGeometry(4.4, 1.5, 2.2);
  const cabin = new THREE.BoxGeometry(2.3, 1.2, 1.9);
  const groups = cars.map((car) => {
    const g = new THREE.Group();
    const b = new THREE.Mesh(body, mat(car.color));
    b.position.y = 1.15;
    const c = new THREE.Mesh(cabin, mat(PALETTE.carCabin));
    c.position.set(-0.3, 2.4, 0);
    g.add(b, c);
    g.traverse((o) => { o.castShadow = true; });
    world.add(g);
    return g;
  });
  function update(t) {
    cars.forEach((car, i) => {
      const pose = carPose(car, t);
      groups[i].position.set(pose.x, 0.1, -pose.y);
      groups[i].rotation.y = pose.heading;
    });
  }
  update(0);
  return { update };
}
