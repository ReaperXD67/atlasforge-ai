# 兄弟同心 — Dato Benz

An image music film built around the supplied trimmed recording. **Rendering:** the 57-shot composition has passed source, framing and sampled visual review. Its 22 main artworks include eight integrated portraits and 14 environments/details, with one additional transparent glass foreground. Full export and encoded verification are in progress.

The new direction, **以光相伴 / The Light We Carry**, places Benz inside coherent rain-lit rooms, glass arcades and a brighter shared courtyard. There are no portrait cards, frames or separate identity overlays. The person is integrated in the finished image; foreground, environment and light supply cinematic movement. Hock Siew remains a different person and delivered project.

## Pipeline improvements

- Subject-protected rain, water reflections and a bounded light pass. Same-camera prototype comparisons measured **zero pixel change** inside the protected artwork region for all three effects, while the background changed. This protects the finished generated portrait; it is not a claim of original-photo pixel identity.
- Face-margin and image-coverage trajectory guards; integrated identity plates reject depth deformation and card/photo layers. Foreground PNGs use explicit finite parallax motion.
- Recording-duration checks against the actual local WAV, locally aligned canonical lyric cues and exact-frame encode bindings. The cut introduction is not restored or captioned as singing.
- Native detail-to-wide cuts show structural supports, refracted light, an open threshold and a community table before their wider consequences. Clause cuts use measured word timing; the final chorus has a new daylight world.
- Reused reviewed Three.js r187, GSAP 3.14.2, HyperFrames 0.9.72 and the narrow MIT luma shader. Offline depth uses the pinned Apache-2.0 Small model on the 14 face-free plates only. No new rendering framework or Runway video generation is needed.

See [BRIEF.md](BRIEF.md), [design direction](design/direction.md), [primary-source research](design/research.md) and the [renderer guide](pipeline/renderer/README.md). Existing libraries and local model/font caches are required; a clean install has not been separately tested.

## Local workflow

The actual 183.025500-second, 48 kHz stereo PCM recording, photo, 23 generated assets, captions, alignment evidence, plans, receipts and renders stay **local and ignored**. The first sung line starts at 12.890 seconds; all 32 supplied sung lines are present. Git publication is limited to pipeline code, design documents and READMEs, as requested. The root ignore allowlist enforces this scope.

From the repository root with the private local inputs available:

```powershell
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/generate_depth.py
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/author_edit.py
node videos/dato-benz-tribute/pipeline/renderer/build.mjs --plan videos/dato-benz-tribute/edit-plan.json
node videos/dato-benz-tribute/pipeline/renderer/smoke.mjs --gpu
node videos/dato-benz-tribute/pipeline/renderer/smoke.mjs --gpu --bindings --times 0,11.7,26.8,49.2,67,94,131,149,179.5
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/verify.py --preflight
Push-Location videos/dato-benz-tribute/pipeline/renderer
npm run check
npm run preview
powershell -NoProfile -ExecutionPolicy Bypass -File render.ps1 -Output ../../renders/Dato-Benz-picture.mp4 -Quality delivery
Pop-Location
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/finalize.py --picture videos/dato-benz-tribute/renders/Dato-Benz-picture.mp4 --share
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/verify.py --file videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-1080p.mp4 --share videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-720p.mp4 --contact-sheets
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/audit_motion.py --file videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-1080p.mp4
```

The production source preflight, official composition check and revised visual gate have passed. Current-plan browser checks cover 55 face-framing and 285 image-coverage samples, with no browser errors and identical repeated seeks. A bounded encoded chorus study also decoded successfully. The finalizer preserves the picture bitstream and uses the original WAV directly for 320 kbps AAC; the smaller viewing copy shares that AAC payload. Final-file checks and client creative approval remain separate gates.
