import { cloudTexture } from './textures.js';

const STRENGTH = 0.3; // how much a full cloud darkens what is under it
const DRIFT = [0.0035, 0.0012]; // texture repeats per second
const SPAN_FACTOR = 1.3; // one texture repeat covers 1.3 × the map side

// Cloud shadows drifting over everything (ground, roofs, trees): each material samples a shared
// cloud texture at its world x/z, so no extra geometry and one texture lookup per pixel.
export function createClouds(r, rng) {
  const uniforms = {
    cloudMap: { value: cloudTexture(rng) },
    cloudOffset: { value: [0, 0] },
    cloudScale: { value: 1 / (2 * r * SPAN_FACTOR) },
    cloudStrength: { value: STRENGTH },
  };

  function patch(material) {
    material.onBeforeCompile = (shader) => {
      Object.assign(shader.uniforms, uniforms);
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\nuniform vec2 cloudOffset;\nuniform float cloudScale;\nvarying vec2 vCloudUv;')
        .replace('#include <project_vertex>', `#include <project_vertex>
  vec4 cloudPos = vec4(transformed, 1.0);
  #ifdef USE_INSTANCING
    cloudPos = instanceMatrix * cloudPos;
  #endif
  cloudPos = modelMatrix * cloudPos;
  vCloudUv = cloudPos.xz * cloudScale + cloudOffset;`);
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', '#include <common>\nuniform sampler2D cloudMap;\nuniform float cloudStrength;\nvarying vec2 vCloudUv;')
        .replace('#include <opaque_fragment>',
          'outgoingLight *= 1.0 - cloudStrength * texture2D(cloudMap, vCloudUv).a;\n#include <opaque_fragment>');
    };
    material.customProgramCacheKey = () => 'clouds';
    return material;
  }

  function update(t) {
    uniforms.cloudOffset.value = [t * DRIFT[0], t * DRIFT[1]];
  }

  return { patch, update };
}
