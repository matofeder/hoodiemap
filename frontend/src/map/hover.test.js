import * as THREE from 'three';
import { describe, expect, it, vi } from 'vitest';
import { createHover } from './hover.js';

// Fake DOM container: just enough for createHover's addEventListener/removeEventListener/
// getBoundingClientRect calls, and lets the test see which listeners are still registered.
function fakeContainer() {
  const listeners = new Map(); // type -> Set of handlers
  return {
    listeners,
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(fn);
    },
    removeEventListener(type, fn) {
      listeners.get(type)?.delete(fn);
    },
    getBoundingClientRect() {
      return { left: 0, top: 0, width: 100, height: 100 };
    },
  };
}

const fakeNode = { getBoundingClientRect: () => ({ left: 10, top: 10, width: 20, height: 20 }) };

describe('createHover dispose', () => {
  it('removes every listener it registered', () => {
    const container = fakeContainer();
    const hover = createHover({
      container,
      camera: new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100),
      meshes: [],
      world: new THREE.Scene(),
      buildings: [],
      tooltip: { show: vi.fn(), hide: vi.fn() },
      describe: () => ({ title: 'x', lines: [] }),
      requestRender: vi.fn(),
    });

    hover.dispose();

    for (const handlers of container.listeners.values()) {
      expect(handlers.size).toBe(0);
    }
  });

  it('stops glowing, touching the world or requesting a render once disposed', () => {
    const container = fakeContainer();
    const world = new THREE.Scene();
    const requestRender = vi.fn();
    const buildings = [{ footprint: [[0, 0], [10, 0], [10, 10], [0, 10]], height: 5 }];
    const hover = createHover({
      container,
      camera: new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100),
      meshes: [],
      world,
      buildings,
      tooltip: { show: vi.fn(), hide: vi.fn() },
      describe: () => ({ title: 'x', lines: [] }),
      requestRender,
    });

    // Hover building 0 via a label, as onLabel does: this lights the glow shell.
    hover.onLabel({ title: 'x', lines: [] }, 0, fakeNode, false);
    expect(world.children.length).toBe(1);
    expect(requestRender).toHaveBeenCalledTimes(1);

    hover.dispose();
    expect(world.children.length).toBe(0); // glow removed and state reset, not just detached

    requestRender.mockClear();
    const before = world.children.length;

    // A stale callback (a queued rAF, a still-firing label blur) calling in after dispose
    // must be inert: no re-render request, no re-adding to the (disposed) world.
    hover.onLabel(null);

    expect(requestRender).not.toHaveBeenCalled();
    expect(world.children.length).toBe(before);
  });
});
