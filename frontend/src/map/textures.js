import * as THREE from 'three';

const PAVING_TILE_M = 3; // one texture repeat covers 3 × 3 m

// Warm stone paving: offset rows of rounded slabs with light grout.
export function pavingTexture() {
  const S = 128, c = document.createElement('canvas');
  c.width = c.height = S;
  const g = c.getContext('2d');
  g.fillStyle = '#EAD7B7';
  g.fillRect(0, 0, S, S);
  const rows = 4, cols = 3, h = S / rows, w = S / cols;
  const tones = ['#F3E3C6', '#F0DDBC', '#F6E8CF', '#EEDAB8'];
  for (let r = 0; r < rows; r++) {
    for (let k = -1; k < cols + 1; k++) {
      const x = k * w + (r % 2) * (w / 2);
      g.fillStyle = tones[(r * 3 + k + 4) % tones.length];
      g.beginPath();
      g.roundRect(x + 2, r * h + 2, w - 4, h - 4, 4);
      g.fill();
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1 / PAVING_TILE_M, 1 / PAVING_TILE_M);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

// Soft, tileable cloud blobs in the alpha channel (drawn 3×3 so they wrap seamlessly).
export function cloudTexture(rng) {
  const S = 256, c = document.createElement('canvas');
  c.width = c.height = S;
  const g = c.getContext('2d');
  for (let i = 0; i < 7; i++) {
    const cx = rng() * S, cy = rng() * S;
    for (let j = 0; j < 4; j++) {
      const x = cx + (rng() - 0.5) * 60, y = cy + (rng() - 0.5) * 30, rad = 25 + rng() * 30;
      for (const ox of [-S, 0, S]) {
        for (const oy of [-S, 0, S]) {
          const grad = g.createRadialGradient(x + ox, y + oy, 0, x + ox, y + oy, rad);
          grad.addColorStop(0, 'rgba(255,255,255,0.55)');
          grad.addColorStop(1, 'rgba(255,255,255,0)');
          g.fillStyle = grad;
          g.fillRect(x + ox - rad, y + oy - rad, rad * 2, rad * 2);
        }
      }
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}
