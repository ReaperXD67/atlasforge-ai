# BOSSTON | Pragon — 好运来

A complete **3:05 lyric film** built around **17 AI-generated worlds**, retaining the seven original scenes and adding ten matching environments. **52 authored shots** combine relative-depth parallax, continuous camera travel, selective water/silk/lantern motion, atmosphere and short optical transitions. The original song is the only soundtrack.

All **71 lyric cues** retain their measured vocal timing. All **nine encoded brand lines** were visually checked and read **Bosston** with two s characters. The supplied lockup correctly retains uppercase BOSSTON. Only the reference's upper-left logo is used.

## Verified local delivery

- [1080p AI Cinema master](renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema.mp4): **185.000 seconds**, 1920 × 1080, 30 fps, H.264/yuv420p, 48 kHz stereo AAC; **752.1 MiB**. All **5,550 frames** decode.
- [720p sharing copy](renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema-720p.mp4): **59.3 MiB**; complete decode passes and its encoded AAC payload is byte-identical to the master.
- Both master soundtrack channels match the source at zero offset: correlation **0.99683083 / 0.99686263**. All 17 artwork/depth hashes and dimensions pass; all 71 lyric lines are complete and ordered.
- All 52 encoded shot midpoints were reviewed across four [contact sheets](renders/review-ai-cinema/contact-sheet-01.jpg). Nine native-resolution spelling crops were reviewed separately. These are sampled visual checks; vocal timing remains model-derived.

The render took **398.5 seconds** on this Windows setup, including **391.2 seconds** of screenshot capture. See the committed [delivery summary](DELIVERY.json), local [full receipt](renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema.verification.json) and [review](REVIEW.md). Media binaries remain local; GitHub contains the editable pipeline, manifests, runtime depth maps, reviewed skills and notices.

## Build and edit

Use the repository's [Windows environment](../../SETUP.md), Node.js, Chrome and FFmpeg. Supply `assets/bgm.wav`, the extracted brand PNG, the [local font](assets/fonts/README.md) and all artwork listed in [ai-assets.json](ai-assets.json). The manifest pins the image bytes; [ai-depths.json](ai-depths.json) binds each depth map to its source.

From the repository root:

```powershell
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/prepare_ai.py
Push-Location videos/bosston-pragon-good-fortune
npm run check
npm run dev
Pop-Location
videos/bosston-pragon-good-fortune/render.ps1
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/verify_delivery.py videos/bosston-pragon-good-fortune/renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema.mp4 --report auto --contact-sheet
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/share.py
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/review_spelling.py videos/bosston-pragon-good-fortune/renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema.mp4 --output output/bosston-ai-v3/spelling-qa
```

Edit text/cue bounds in `captions.json`, or shot choices/camera paths in `prepare_ai.py`, then compile again. It writes the active `index.html` from `index_ai.html.in`, plus `scene-plan.json`, `film-data.js`, `motion-ledger.json`, asset hashes and the [storyboard](STORYBOARD.md). `ai-cinema.js` renders image/depth motion; `ai-master.js` and the inline paused timeline drive it alongside editable HTML lyrics. HyperFrames owns soundtrack playback. The preview remains editable in the HyperFrames desktop app.

## Depth and motion checks

The [depth helper](generate_ai_depth.py) uses Apache-2.0 **Depth Anything V2 Small**, pinned to revision `5426e4f0f36572d16453bbda7a8389317b1bef99`. CPU PyTorch/Transformers produced 17 maps in **22.585 seconds**. To regenerate:

```powershell
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/generate_ai_depth.py --manifest videos/bosston-pragon-good-fortune/ai-assets.json
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/prepare_ai.py
node videos/bosston-pragon-good-fortune/verify_ai_motion.mjs --project videos/bosston-pragon-good-fortune --output output/bosston-ai-v3/qa
```

The model cache/raw fields stay under ignored `output/`; runtime maps are small grayscale PNGs. Both manifests and compiled data require matching depth maps. See [depth setup/licensing](assets/depth/README.md). The browser gate finds an installed project-local Puppeteer or the HyperFrames npm cache; run the HyperFrames check first. It passed 35 selected seeks, 17 loaded maps with no fallback and three exact repeated-time canvas hashes. A 14-second actual-composition proof passes 420-frame 1080p30 decoding and zero-offset audio comparison.

`render.ps1` pins HyperFrames 0.8.152, one hardware-browser worker and screenshot capture. The optional [encoded-image diagnostic](verify_ai_binding.py) compares exact-clock native picture crops against browser screenshots and rejects the superseded stock cut. Its RGB and BT.709-luma results are separate: required 4:2:0 chroma subsampling makes the original strict raw-RGB SSIM gate fail even for a lossless reference roundtrip. See [review findings](REVIEW.md); no time/crop fitting or threshold reduction is used.

These are **animated AI artworks**, not native generated-video footage. Relative depth cannot reveal hidden surfaces or generate fully articulated creature performances. The [three reviewed motion skills](../../.agents/skills/README.md) inform continuity and opaque handoffs; [research decisions](../../docs/research/bosston-ai-motion-v3-2026-11-18.md) record exact licenses and adoption evidence. [Media provenance](MEDIA.md) explains the artwork, soundtrack, brand and timing evidence.

## Archived experiment

The earlier stock route remains in `prepare.py`, `index.html.in`, `master.js`, `motion-assets.json` and its [source credits](STOCK_CREDITS.md). It is inactive in V3. Its `Cinematic.mp4` exports describe the earlier cut. Running that compiler replaces the active generated files; run `prepare_ai.py` again to restore AI Cinema.
