# 兄弟同心 — Dato Benz

An image music film built around the supplied trimmed recording. **Rebuilt under the current brief:** the 60-shot composition contains no photo, portrait or depiction of Benz. Its active artwork set contains 22 person-free scenes and one transparent glass foreground. The previous portrait render was stopped and is not the current delivery; the replacement is undergoing final export and review.

The direction, **以光相伴 / The Light We Carry**, expresses brotherhood through storm coastlines, rope sharing a load, a workshop, a community table, protective roots, converging rivers and a bright working harbour. Close objects, overhead compositions and open landscapes give the edit different scales. Benz is named only in the lyrics and dedication. Hock Siew remains a separate delivered project.

## Pipeline improvements

- Explicit `identityPolicy: "excluded"` is enforced by the compiler, runtime and verifier. Person metadata and portrait/card layers fail the build; local path/hash exclusions block the supplied photo and all eight rejected portrait plates, including renamed copies.
- Image-coverage trajectory guards, restrained environment depth and finite foreground motion. Rain, water and bounded light movement use the song clock rather than an independent loop.
- Recording-duration checks against the actual local WAV, locally aligned canonical lyric cues and exact-frame encode bindings. The cut introduction is not restored or captioned as singing.
- Clause cuts use measured word timing, often changing the subject as well as the scale: rope to support, roots to homes, table to community, workshop to harbour. The final chorus opens into a new daylight world.
- Reused reviewed Three.js r187, GSAP 3.14.2, HyperFrames 0.9.72 and the narrow MIT luma shader. Offline depth uses the pinned Apache-2.0 Small model on the 22 face-free plates. No new rendering framework or Runway video generation is needed. The reusable legacy subject-protection mode is not used in this film.

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
powershell -NoProfile -ExecutionPolicy Bypass -File render.ps1 -Output ../../renders/Dato-Benz-Person-Free-picture.mp4 -Quality delivery
Pop-Location
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/finalize.py --picture videos/dato-benz-tribute/renders/Dato-Benz-Person-Free-picture.mp4 --share
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/verify.py --file videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-1080p.mp4 --share videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-720p.mp4 --contact-sheets
.venv\Scripts\python.exe videos/dato-benz-tribute/pipeline/audit_motion.py --file videos/dato-benz-tribute/renders/Benz-Brothers-One-Heart-1080p.mp4
```

The revised pipeline passed nine compiler and six runtime policy cases; rejected runtime cases fetched no images. Verifier rejection cases cover declared identity, old portraits, person layers, the original JPEG and renamed hash matches. These checks enforce source declarations and known excluded bytes; a visual review is still required to inspect image content. Fresh source preflight and the official composition check pass. The new build has 300 image-coverage checks, zero identity/face checks, 122 browser samples without errors and identical repeated seeks. All 22 artwork sources have been visually inspected for incidental people; encoded review is still required. Old portrait-film receipts do not validate this revised cut.

The finalizer preserves the picture bitstream and uses the original WAV directly for 320 kbps AAC; the smaller viewing copy shares that AAC payload. Final-file checks and client creative approval remain separate gates.
