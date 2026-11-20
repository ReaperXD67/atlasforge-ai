# 兄弟同心 — Dato Benz

An image music film built around the supplied trimmed recording. **Production in progress:** the18 main artworks and32 measured lyric cues are ready; the57-shot1080p composition is undergoing visual preflight. Client creative approval is not claimed.

The new direction, **以光相伴 / The Light We Carry**, places Benz inside coherent rain-lit rooms, glass arcades and a brighter shared courtyard. There are no portrait cards, frames or separate identity overlays. The person is integrated in the finished image; foreground, environment and light supply cinematic movement. Hock Siew remains a different person and delivered project.

## Pipeline improvements

- Subject-protected rain, water reflections and a bounded light pass. Same-camera prototype comparisons measured **zero pixel change** inside the protected artwork region for all three effects, while the background changed. This protects the finished generated portrait; it is not a claim of original-photo pixel identity.
- Face-margin and image-coverage trajectory guards; integrated identity plates reject depth deformation and card/photo layers. Foreground PNGs use explicit finite parallax motion.
- Recording-duration checks against the actual local WAV, locally aligned canonical lyric cues and exact-frame encode bindings. The cut introduction is not restored or captioned as singing.
- Reused reviewed Three.js r187, GSAP3.14.2, HyperFrames0.9.72 and the narrow MIT luma shader. Offline depth uses the pinned Apache-2.0 Small model on the ten face-free plates only. No new rendering framework or Runway video generation is needed.

See [BRIEF.md](BRIEF.md), [design direction](design/direction.md), [primary-source research](design/research.md) and the [renderer guide](pipeline/renderer/README.md). Existing libraries and local model/font caches are required; a clean install has not been separately tested.

## Local workflow

The actual183.025500-second48kHz stereo PCM recording, photo,19 generated assets, captions, alignment evidence, plans, receipts and renders stay **local and ignored**. The first sung line starts12.890s; all32 supplied sung lines are present. Git publication is limited to pipeline code, design documents and READMEs, as requested. The root ignore allowlist enforces this scope.

From the repository root with the private local inputs available:

```powershell
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/generate_depth.py
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/author_edit.py
node videos/dato-benz-tribute/pipeline/renderer/build.mjs --plan videos/dato-benz-tribute/edit-plan.json
node videos/dato-benz-tribute/pipeline/renderer/smoke.mjs --gpu
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/verify.py --preflight
Push-Location videos/dato-benz-tribute/pipeline/renderer
npm run check
npm run preview
powershell -NoProfile -ExecutionPolicy Bypass -File render.ps1 -Output ../../renders/Dato-Benz-picture.mp4 -Quality delivery
Pop-Location
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/finalize.py --picture videos/dato-benz-tribute/renders/Dato-Benz-picture.mp4 --share
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/verify.py --file videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-1080p.mp4 --share videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-720p.mp4 --contact-sheets
```

Source/depth preparation and the renderer prototype have passed. Full production smoke, official composition check, export, finalization and encoded verification are still being completed. The finalizer preserves the picture bitstream and uses the original WAV directly for320kbps AAC; the smaller viewing copy shares that AAC payload.
