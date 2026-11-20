// Author: gre
// License: MIT
// Description: A wipe that follows the brightness of a grayscale mask (the luma texture)
// Tags: wipe, luma, mask
// Source: https://github.com/gl-transitions/gl-transitions/blob/deeebdee7581cdfe924ed9cf104ea2fd10e63155/transitions/LumaWipe.glsl

uniform sampler2D luma;

vec4 transition(vec2 uv) {
  return mix(
    getToColor(uv),
    getFromColor(uv),
    step(progress, texture2D(luma, uv).r)
  );
}
