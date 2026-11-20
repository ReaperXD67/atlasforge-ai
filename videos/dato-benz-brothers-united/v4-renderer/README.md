# V4 image-film renderer

This isolated renderer turns a film-root JSON plan into a 1920×1080 HyperFrames composition. Real photographs remain unchanged image textures with literal pixel crops and their original aspect ratio. Invented artwork can have separate foreground planes, camera travel, masks and optional restrained depth; it uses no generated human motion.

From this directory:

```powershell
node build.mjs --plan ../edit-plan-v4.json
node smoke.mjs
npm run preview
powershell -NoProfile -ExecutionPolicy Bypass -File render.ps1
```

`node smoke.mjs --demo` builds a separate 16-second silent renderer study from the bridge/coast/arch artwork and original seaside photograph. It overwrites the ignored generated `index.html`; rebuild the intended plan before exporting a delivery. The study is not a complete MV.

The build copies input bytes into ignored `assets/media/` and records SHA256 hashes in `build-receipt.json`. `UPSTREAM.json` records pinned runtimes and the narrowly adapted MIT luma shader. Three.js/GSAP are copied from an existing verified workspace vendor; no npm runtime dependency is added. Local font files and media remain outside Git.

## Plan contract

All source paths are relative to the film root, one directory above this renderer. Scenes must cover the declared duration consecutively. Default delivery is 196.760 seconds at 24fps. Times are seconds; camera keyframe `at` values are normalized 0–1. Full image planes use a world height of 15.4 with an overscan area; the default camera is about 12 units from the plane.

```json
{
  "duration": 196.760,
  "fps": 24,
  "width": 1920,
  "height": 1080,
  "audio": "assets/bgm.wav",
  "captions": "captions.json",
  "scenes": [{
    "id": "example",
    "start": 0,
    "end": 196.760,
    "src": "assets/art-v4/13-coast.png",
    "depthSrc": "assets/depth-v4/13-coast.png",
    "depthStrength": 0.4,
    "cameraPreset": "traverse",
    "transition": {"kind": "cut"},
    "layers": [{
      "id": "hock-original",
      "kind": "photo",
      "src": "assets/photos/seaside.jpg",
      "x": 2,
      "y": 0,
      "z": 1,
      "height": 7.2
    }]
  }]
}
```

Camera presets: `traverse`, `reveal`, `arrive`, `photo`, `hold`. Override with `camera:[{"at":0,"x":-1,"y":0,"z":12.8,"look":[0,0,0]},{"at":1,"x":1,"y":0,"z":12,"look":[0,0,0]}]`. Keyframe destination `ease` accepts `linear` (default), `smooth`, `in`, `out`. Explicit waypoints make directional handoffs and purposeful arrivals possible.

Layer dimensions are world units. Omit `width` on photographs to preserve aspect ratio; a mismatched supplied width fails. Optional `crop:[left,top,width,height]` uses source pixels. Photo cards always face the camera and receive no depth, mesh displacement, lighting changes or texture retouching. For transparent art foregrounds use `kind:"art"`, `height`, `x/y/z` and optional `rotation:[x,y,z]` radians. Higher positive `z` comes closer to the camera and produces stronger parallax. Keep foreground clear of lyric/title areas in sampled frames.

Layers can use `from`/`to` absolute `{x,y,z,scale,opacity}` states (or xyz arrays), `motionStart`/`motionEnd` normalized scene fractions and `ease` with the same choices as camera keys. Missing values retain the layer's base state. Photo scaling remains uniform; the image content is never stretched or rebuilt. These controls allow an authored foreground to pass out of frame and reveal the next visual destination.

Scene `depthSrc` applies only to the non-human main artwork, with strength capped at 0.8 world units. It estimates relative geometry; it cannot create unseen surfaces or actual moving people. `transition:{"kind":"luma","duration":0.7,"mask":"optional-local-grayscale.png"}` performs an image-layer threshold reveal at the start of the incoming scene. The fallback directional contour mask is original code. `occluder:"paper"`/`"arch"` enables optional simple geometry studies; use authored transparent artwork layers for final foreground detail. The procedural silk line is opt-in with `silk:true`.

Optional `title` and `subtitle` appear during that scene. Mandarin lyrics use the unmodified canonical cue file. `window.seek(seconds)` and `hf-seek` render an explicit time; no autonomous animation loop exists. `window.V4_READY_PROMISE` resolves after textures, font and shader compilation. `window.V4_LAST_STATE` reports the current scene/frame.

Use titles sparingly for the opening/dedication. `titleStyle` supports `color,fontSize,subtitleSize,lineHeight,left,top,width,background,padding,border`; numeric positions/sizes are pixels, while CSS strings are accepted. `titleAlign` and `titleEyebrowStyle` are optional. Actual newlines in text display via `white-space:pre-line`, without inserting HTML. For dark type directly over a light paper plate, use `background:"transparent",padding:0,border:"none"` and an authored color/position in the plate's negative space.

## Verification and export

`node smoke.mjs` writes ignored 1080p PNGs under `renders/smoke/` and `smoke-result.json`, including console errors, per-sample state and repeat-seek hashes. Add `--gpu` to use ANGLE D3D11 instead of SwiftShader, or `--seams` to sample every declared luma handoff into `renders/seams/`. It resolves the Puppeteer module already installed with HyperFrames. Set `V4_PUPPETEER_PATH` if the npm cache lives elsewhere.

For changed scenes only, use `node smoke.mjs --gpu --scene-indices "5,23,24"` (zero-based indices); it writes `renders/targeted/` and `targeted-result.json`. Each result records the source-plan SHA256 loaded into the page. `../../../.venv/Scripts/python.exe contact.py --result targeted-result.json` makes 4×4 review sheets from the actual PNGs. Add `--last-per-scene` for one later frame per scene.

`render.ps1` pins the current installed HyperFrames 0.9.72 CLI, system Chrome and one screenshot worker. Hardware GPU is the default after a successful full-plan smoke; this hybrid laptop selects AMD Radeon D3D11 rather than its NVIDIA adapter. `-Software` restores the deterministic SwiftShader fallback. `-Start 0 -End 4 -Output renders/test.mp4` renders a bounded MP4 span with that span's song audio, without rewriting the plan. Output frame cadence follows the plan. For an official check in this environment, set the browser variables first:

```powershell
$env:HYPERFRAMES_BROWSER_PATH='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:PRODUCER_HEADLESS_SHELL_PATH=$env:HYPERFRAMES_BROWSER_PATH
npx --yes hyperframes@0.9.72 check --browser-gpu --no-craft --samples 27 --timeout 120000 --json
```

These are render controls, not a guarantee of client acceptance. The completed V4 master and viewing copy passed the separate full decode, original-song correlation, all forty cue/source checks and nine exact encoded-picture bindings. See [DELIVERY-V4.json](../DELIVERY-V4.json) and the [main film README](../README.md) for current delivery and client-review status.

The initial 16-second silent study exported successfully with 0.8.152 before the CLI pin was updated: 1920×1080/24fps, 384 frames, 24.7 MB, 103.5 seconds of screenshot/software-GPU rendering. It predates the later title/layout controls. Eight full-resolution smoke samples passed with no browser errors and identical repeat-seek PNG bytes. Current 0.9.72 check passed lint, runtime, layout and contrast. Its craft warnings describe the intentionally silent study, a small eyebrow (subsequently increased) and apparent DOM stillness: the camera draws into a canvas, so encoded-pixel movement is verified separately. The completed full-song 0.9.72 export used hardware GPU and one worker, taking 6m49.8s. Its current official check passed runtime/layout and all five sampled contrast checks. One timed-DOM density warning and twenty DOM-only stillness warnings are retained: the composition draws motion inside WebGL. The separate 394-frame encoded movement audit found no unintended freeze before the deliberate closing hold; the independent encoded-frame review found no new P0/P1 framing defect. Neither check is a claim of continuous listening or client creative acceptance.

The full 54-shot/40-cue plan subsequently passed a 110-frame 1080p hardware smoke with zero browser errors and identical repeat-seek PNG bytes. The official 0.9.72 preflight passed 27 timeline samples and 23 overlap samples, including 5/5 contrast checks; one timeline-density warning reflects the 40 canonical cues and two titles. These checks precede the final encoded MV and are not client acceptance.

A four-second span of the full plan exported at 1920×1080/24fps with original-song AAC and passed complete decoding. One-worker capture took 19.404 seconds for 96 frames (31.3 seconds including full-plan setup/audio). A two-worker request took 19.839 seconds after a BeginFrame-to-screenshot retry, 38.5 seconds overall, so the default remains one worker. `-Workers 2`/`4` is available for later measured experiments, with low-memory mode disabled for those requests. The short range path's internal worker calibration and startup costs do not prove full-song scaling. No resolution, frame-rate or bitrate reduction was used for the comparison.
