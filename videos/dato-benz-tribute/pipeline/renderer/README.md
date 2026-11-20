# Integrated image music-film renderer

This renderer builds a 1920×1080, 24fps HyperFrames music film from a measured recording, local lyric cues and finished cinematic image plates. The person belongs inside the main artwork. Photo cards, frames and identity foreground layers are rejected. No generated video is used.

## Run

From this folder, with the project's private local media and `edit-plan.json` ready:

```powershell
node build.mjs --plan ../../edit-plan.json
node smoke.mjs --gpu
npm run check
npm run preview
powershell -NoProfile -ExecutionPolicy Bypass -File render.ps1 -Output ../../renders/Dato-Benz-picture.mp4 -Quality delivery
```

`build.mjs` requires the actual recording duration and checks it against local FFprobe within 2 ms. It never inherits the previous song's duration. Source paths are relative to the Benz project root. It freezes input bytes into ignored `assets/media/`, records hashes in ignored `build-receipt.json`, and keeps the canonical cue text/times. The local Mandarin font and reviewed Three/GSAP bytes are copied from the existing licensed workspace cache.

The renderer pins HyperFrames 0.9.72. `render.ps1` uses actual hardware GPU and one worker by default, with `-Software` fallback and optional `-Start`/`-End` for bounded studies. Root's finalization/verification workflow owns the original-song audio mux, encoded checks and client delivery.

## Plan contract

```json
{
  "duration": 183.0255,
  "fps": 24,
  "width": 1920,
  "height": 1080,
  "audio": "assets/bgm.wav",
  "captions": "captions.json",
  "scenes": [{
    "id": "integrated-scene",
    "start": 0,
    "end": 183.0255,
    "src": "assets/art/01-shelter.png",
    "containsIdentity": true,
    "faceBounds": [0.205, 0.09, 0.11, 0.245],
    "subjectBounds": [0.10, 0.08, 0.31, 0.92],
    "faceMargin": 0.04,
    "focalRect": [0, 0, 1, 1],
    "focalRectEnd": [0.02, 0, 0.98, 0.98],
    "atmosphere": {"kind": "rain", "strength": 0.25},
    "captionTheme": "light"
  }]
}
```

Bounds/regions are normalized source coordinates `[left,top,width,height]`. `focalRect` derives a straight, image-filling camera and clamps it to the source edges; `focalRectEnd` supplies the final region. Alternatively use explicit normalized-time camera keys: `camera:[{"at":0,"x":0,"y":0,"z":13,"look":[0,0,-1]},{"at":1,"x":0.4,"y":0,"z":12.8,"look":[0.4,0,-1]}]`. Destination `ease` accepts `linear` (default), `smooth`, `in` or `out`. Neither default camera nor atmosphere uses an independent animation loop.

`containsIdentity:true` requires `faceBounds` and rejects `depthSrc`. Five trajectory points plus every explicit camera key check the projected face bounds and image-plane coverage before the renderer becomes ready. Default face margin is 10%; an explicit `faceMargin` can admit a source whose natural framing has less headroom. A deliberate matte requires `allowMatte:true`; otherwise a camera that exposes outside the image plane fails. These are geometric guards, not face recognition or semantic likeness judgments.

Background-only relative depth uses `depthSrc` and `depthStrength` capped at 0.6 world units on face-free plates. Main plate height is 15.4 world units at z=-1; the default lens is 45°. Plane geometries are shared by dimensions/subdivision count, and textures are cached by source/hash and color space, rather than duplicated per shot.

## Subject-protected environmental movement

`atmosphere.kind` accepts `rain`, `light` or `water`; `strength` is capped at 0.5. Identity plates additionally require `subjectBounds`. The original small GLSL shader protects that rectangle plus default `subjectPadding:0.015`; its feather lies outside the protected core. It does not displace, recolor, relight or animate the protected person in the finished artwork. This is not a claim that an image generator preserved the original photograph byte-for-byte.

- Rain creates subtle finite-clock background streaks; use it only in scenes that depict rain.
- Light makes one bounded warm illumination pass across the background. Optional normalized `start`/`end` set its phase within the scene.
- Water adds restrained background reflection UV movement below `waterLine` (normalized distance from source top, default0.6). Put the line on the actual reflective floor/water; do not apply it to dry architecture.

Foreground PNGs use `layers:[{kind:"foreground",src,height,x,y,z,from,to,motionStart,motionEnd,ease}]`. PNGs use straight alpha, with transparent materials and no depth writes. Transform motion is explicit and finite; keep foregrounds clear of the face and lyric area. Identity/card layers, borders and photo-frame styling fail the build. `transition:{kind:"luma",duration:0.45,mask:"optional.png"}` uses the narrowly adapted MIT grayscale-mask handoff; readable name cues can use a direct cut.

Lyrics are transparent 48 px type with a soft shadow and a continuous lower shade, without an opaque text box. Set `captionTheme:"dark"` on pale images, or `captionColor` and `captionShade` when needed. Titles are sparse transparent type, controlled by `title`, `subtitle`, `titleStyle:{left,top,width,color,fontSize,subtitleSize,lineHeight}` and `titleAlign`. Inspect actual background contrast; DOM checks do not see the complete WebGL image.

## Verification

`smoke.mjs --gpu` captures scene starts/interiors and verifies identical screenshot bytes after out-of-order seeks. Its receipt includes plan SHA, hardware renderer, browser errors, projected face bounds and image-coverage checks. Use `--scene-indices 0,3,8 --label targeted`, `--seams`, or `--times 0,20,80` for focused samples.

Exact encoded-picture references:

```powershell
node smoke.mjs --gpu --bindings --times 0,20,40,60,80,100,120,150,175
```

This writes ignored `renders/bindings/reference-bindings.json` and frame-aligned PNGs, with plan/build/source hashes, for the separate full-file verifier. Times must be inside the actual recording; the command above is an example, not a prescribed shot list. The harness rejects source changes after a build.

The 12-second integrated-portrait prototype passed official 0.9.72 lint/runtime/layout/contrast checks. Its one DOM-only stillness warning does not observe the canvas. Ten 1080p screenshots had no browser errors and repeated seeks were byte-identical. In same-camera FX-off/on comparisons, the protected 680×935 px interior had **zero pixel difference** for rain, light and water, while background pixels changed. The five negative guard cases rejected identity depth, photo overlays, missing/out-of-range face bounds and a recording-clock mismatch without altering the previous compiled index. The actual film still needs its own final check, picture/audio decode, cue/source validation and visual review.

`verify_subject_keepout.py <capture-directory> --reference ... --effects ... --crop left,top,width,height` repeats the screenshot comparison without resize, alignment or color fitting. [UPSTREAM.json](UPSTREAM.json) and `vendor/` retain reviewed runtime/shader/font provenance. Only reusable pipeline source and this guide are intended for Git; media, model caches, generated HTML, captions, plans and production receipts remain local.
