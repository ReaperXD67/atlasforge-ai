# BOSSTON | Pragon — 好运来

A complete Chinese New Year lyric film built around **17 generated AI artworks**: seven original worlds and ten new scenes, arranged into **52 authored shots**. The active V3 renderer combines inferred depth, continuous camera travel, restrained water/silk/lantern motion, atmosphere and optical transitions. Lacquer red, luminous gold and an expansive dawn connect the festival worlds.

The **185-second original song** is the only soundtrack. All **71 lyric cues** retain their measured vocal timing, including **nine Bosston mentions** with the approved double-s spelling. The supplied brand lockup correctly uses uppercase BOSSTON.

**Delivery status:** the V3 source and motion proof pass their preflight checks; all 17 image/depth pairs pass checksum and dimension checks. The full AI Cinema render is running; encoded delivery checks and final visual review are pending. Earlier export sizes, render times and audio correlations do not describe this revision.

## Build and preview

Use the repository's [Windows environment](../../SETUP.md), Node.js, Chrome and FFmpeg. The local `assets/bgm.wav`, extracted brand PNG and [fonts](assets/fonts/README.md) must be present. The generated artwork is listed in [ai-assets.json](ai-assets.json); [ai-depths.json](ai-depths.json) binds every depth map to its exact source image.

From the repository root:

```powershell
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/prepare_ai.py
Push-Location videos/bosston-pragon-good-fortune
npm run check
npm run dev
Pop-Location
```

Edit lyric text and cue bounds in `captions.json`, or shot choices and camera paths in `prepare_ai.py`, then compile again. The compiler writes `scene-plan.json`, `film-data.js`, `index.html`, `motion-ledger.json` and the [storyboard](STORYBOARD.md). `index_ai.html.in` is the active template. `ai-cinema.js` renders the artwork and depth; `ai-master.js` drives that renderer, captions and fades from one absolute song clock. HyperFrames controls the original song.

## Depth and motion

The [depth helper](generate_ai_depth.py) uses **Depth Anything V2 Small**, pinned to revision `5426e4f0f36572d16453bbda7a8389317b1bef99` under Apache-2.0. It runs on the existing CPU PyTorch/Transformers environment and verifies the checkpoint and license hashes. To regenerate all maps:

```powershell
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/generate_ai_depth.py --manifest videos/bosston-pragon-good-fortune/ai-assets.json
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/prepare_ai.py
```

The model cache and raw depth fields remain under ignored `output/bosston-ai-v3/depth/`; source-size grayscale runtime maps live in `assets/depth/`. See the [depth notes](assets/depth/README.md) for normalization, licensing and regeneration details. Both the manifest and compiled data require depth maps; missing or stale pairs must fail validation.

These are **animated AI artworks**, not native AI-generated video. Relative monocular depth supports parallax, but does not recover hidden surfaces or physical geometry. Camera overscan, subtle material deformation and selected atmospheric effects preserve the generated imagery. The original WebGL renderer adds no separate 3D engine.

The project-local [motion skills](../../.agents/skills/README.md) inform camera direction, velocity continuity and opaque scene handoffs. [Reviewed upstream decisions](../../docs/research/bosston-ai-motion-v3-2026-11-18.md) record exact revisions, licenses and installation provenance. The project-specific [browser motion gate](verify_ai_motion.mjs) samples actual WebGL frames, checks repeated-time determinism and records seam/edge review candidates. It passed 35 selected seeks, 17 loaded depth maps with no fallback and three exact repeated-time canvas hashes. A 14-second, 420-frame 1080p30 motion proof fully decodes. Run the gate with:

```powershell
node videos/bosston-pragon-good-fortune/verify_ai_motion.mjs --project videos/bosston-pragon-good-fortune --output output/bosston-ai-v3/qa
```

## Render and verify

```powershell
videos/bosston-pragon-good-fortune/render.ps1
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/verify_delivery.py videos/bosston-pragon-good-fortune/renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema.mp4 --report auto --contact-sheet
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/share.py
```

`render.ps1` uses the tested HyperFrames 0.8.152 renderer, one hardware-browser worker and screenshot capture. Its default master is `renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema.mp4`; `share.py` creates `renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema-720p.mp4` with the same encoded AAC soundtrack.

The delivery target is **1920 × 1080, 30 fps, H.264/yuv420p with 48 kHz stereo AAC**. `verify_delivery.py` fully decodes the export and requires **185 seconds / 5,550 frames**, zero-offset correlation with both original soundtrack channels, complete ordered lyric text, all nine correctly spelled brand mentions, current source bindings and the 17 hashed image/depth pairs. It writes a JSON receipt and can sample every encoded shot into contact sheets. The sharing-copy helper checks its full decode, duration/frame count and byte-identical AAC payload. Final V3 results will be recorded after those checks and visual review finish.

Timing evidence remains in `timing-evidence/`; word alignment is model-derived and individual entrances may vary by several tenths of a second. [Media provenance](MEDIA.md) and [review notes](REVIEW.md) contain deeper production records. GitHub publication of this project is authorized; credentials, model weights, private audio and caches remain outside Git.

## Archived experiment

The earlier stock-footage route remains in `prepare.py`, `index.html.in`, `master.js`, `motion-assets.json` and its footage helpers, with [source credits](STOCK_CREDITS.md). It is not loaded by V3. Its `Cinematic.mp4` exports and receipts describe that earlier cut only. Running the archived compiler replaces the generated active files; run `prepare_ai.py` again to restore the AI Cinema composition.
