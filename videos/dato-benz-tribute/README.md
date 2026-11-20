# 兄弟同心 — Dato Benz

An image music film built around the supplied trimmed recording. **Verified 1080p and 720p exports are available locally.** The 60-shot composition contains no photo, portrait or depiction of Benz. Its active artwork set contains 22 person-free scenes and one transparent glass foreground. The previous portrait render was stopped and is superseded. Client creative approval remains pending.

The direction, **以光相伴 / The Light We Carry**, expresses brotherhood through storm coastlines, rope sharing a load, a workshop, a community table, protective roots, converging rivers and a bright working harbour. Close objects, overhead compositions and open landscapes give the edit different scales. Benz is named only in the lyrics and dedication. Hock Siew remains a separate delivered project.

## Pipeline improvements

- Explicit `identityPolicy: "excluded"` is enforced by the compiler, runtime and verifier. Person metadata and portrait/card layers fail the build; local path/hash exclusions block the supplied photo and all eight rejected portrait plates, including renamed copies.
- Image-coverage trajectory guards, restrained environment depth and finite foreground motion. Rain, water and bounded light movement use the song clock rather than an independent loop.
- Recording-duration checks against the actual local WAV, locally aligned canonical lyric cues and exact-frame encode bindings. The cut introduction is not restored or captioned as singing.
- Clause cuts use measured word timing, often changing the subject as well as the scale: rope to support, roots to homes, table to community, workshop to harbour. The final chorus opens into a new daylight world.
- Reused reviewed Three.js r187, GSAP 3.14.2, HyperFrames 0.9.72 and the narrow MIT luma shader. Offline depth uses the pinned Apache-2.0 Small model on the 22 face-free plates. No new rendering framework or Runway video generation is needed. The reusable legacy subject-protection mode is not used in this film.

See [BRIEF.md](BRIEF.md), [design direction](design/direction.md), [executed scene prompts](design/scene-prompts.md), [primary-source research](design/research.md) and the [renderer guide](pipeline/renderer/README.md). Existing libraries and local model/font caches are required; a clean install has not been separately tested.

## Local outputs

Both MP4s are complete H.264 files at 24 fps, with 4,393 frames and the original song encoded directly to 48 kHz stereo AAC at 320 kbps. The master preserves the picture bitstream; the smaller copy shares its exact AAC payload. Media stays local rather than being uploaded to GitHub.

| Local file | Picture | Size |
| --- | --- | --- |
| `renders/Benz-Brothers-One-Heart-1080p.mp4` | 1920×1080 | 421.0 MB |
| `renders/Benz-Brothers-One-Heart-720p.mp4` | 1280×720 | 116.8 MB |

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

## Validation

- The current build passes source preflight, nine compiler and six runtime policy cases. Rejected runtime cases fetched no images. Verifier rejection cases cover old portraits, person layers, the original JPEG and renamed hash matches. All 22 actual artwork sources were visually inspected; declarations alone do not prove image content.
- The new build has 300 image-coverage checks, zero identity/face checks, 122 browser samples without errors and identical repeated seeks. The official composition check has zero errors. Its one timeline-density and 37 DOM-only stillness warnings do not inspect the canvas; a separate encoded audit sampled 366 frames at 2 fps and found no near-black interval or low-change interval outside the intended closing hold.
- Both completed files decode fully. All nine exact-frame picture bindings pass without resizing, alignment or colour fitting (38.7–40.9 dB PSNR). The 4,393 frames cover 183.041667 seconds, within one frame of the unchanged 183.025500-second recording.
- Audio correlation exceeds 0.9996 in both channels; all eight measured lag checks return zero samples. Master picture bytes are preserved and the viewing copy has the identical AAC payload.
- Independent visual review covers all 60 pre-encode interiors, all 60 encoded shot midpoints, 12 named-lyric samples and full-resolution title, long lyric and dedication. No observed person/portrait, clipping, contrast or consecutive-wide repetition blocker remained. Technical checks and sampled images are distinct from continuous playback/listening and client approval.

Local evidence lives in `renders/qa/technical-verification.json`, `picture-binding.json`, `motion-audit.json` and the shot/name-art contact images. The master SHA-256 is `a72972ade66268f40a2f3e78816158eccc56a23d834c3f51e2c4e196f703e2dd`; the 720p copy is `95db7c9ab73eff285ef1998e246dc733e6b9e4b81c4cebb7ed78430f0eeb2fbf`. Media, cues and receipts remain local; only pipeline, design and README sources are published.
