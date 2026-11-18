# BOSSTON | Pragon — 好运来

**Current revision:** the user requested a return to the AI-generated cinematic worlds with additional AI scenes and stronger motion. That revision is in development. The verified stock-footage export documented below is retained as an earlier experiment; it is not the current creative target.

A 3:05 Chinese New Year lyric music film. The cinematic revision uses **moving footage throughout**: dragon and lion performances, live percussion, swimming koi, fireworks, lanterns and cloud aerials. **68 shots** use 20 reviewed source windows from nine licensed clips. The original song remains the only soundtrack.

All **71 lyric cues** preserve their measured vocal timing. The user-approved spelling is **Bosston**, including all nine brand lyric lines; the supplied logo correctly uses uppercase BOSSTON. Preparation and delivery verification reject the earlier Boston spelling. Raw recognition evidence and the original WAV filename remain unchanged.

## Run and edit

Use the repository's [Windows environment](../../SETUP.md), Node.js, Chrome and FFmpeg. Supply the local song, brand PNG, [fonts](assets/fonts/README.md) and the staged footage listed in `motion-assets.json`. The [footage credits](STOCK_CREDITS.md) record the sources, creators and Pexels License. Standalone stock files and the song stay outside Git.

From the repository root:

```powershell
# Optional: recreate graded clips from the pinned local source ledger.
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/prepare_motion_assets.py
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/prepare.py
Push-Location videos/bosston-pragon-good-fortune
npm run check
npm run dev
Pop-Location
videos/bosston-pragon-good-fortune/render.ps1
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/verify_delivery.py videos/bosston-pragon-good-fortune/renders/BOSSTON-Pragon-Good-Fortune-Cinematic.mp4 --report auto --contact-sheet
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/share.py
```

Edit lyric text and cue bounds in `captions.json`, then run `prepare.py`. The authored chapter/shot choices live in `prepare.py`; it compiles `scene-plan.json`, `film-data.js`, `index.html` and the [shot plan](STORYBOARD.md). `index.html.in` is the template. `master.js` selects the active footage window and typography from absolute song time; HyperFrames owns media seeking and playback. The local preview also opens the editable project in the HyperFrames desktop app.

## Motion and production checks

The 20 staged variants total **139.2 seconds of distinct selected source footage**. Every variant is silent 1920 × 1080, 30 fps, H.264/yuv420p with BT.709 metadata. Each has a source checksum, source window, reviewed crop, exact grading filter, output checksum and permitted playback range. The edit cycles these ranges rather than reversing motion. Source rates are converted by frame duplication/drop; no optical-flow accuracy is claimed.

The native footage stage uses the installed FFmpeg 7.1 NVENC binary because this machine's driver does not support FFmpeg 9's newer NVENC API. The final renderer pins HyperFrames 0.8.152, one hardware-browser worker and screenshot capture; the newer native capture API was benchmarked separately without a speed benefit. No driver or security-policy changes were made.

A Three.js motion study and an official Blender installation were evaluated during the revision. The procedural hero studies were not admitted into this cut. Windows Application Control prevents Blender and the cached local Wan runtime from starting, so neither produced footage for this delivery. `cinema.js`, `world3d.js` and the original image plates remain exploratory sources and are not loaded by the current film.

## Lyrics and provenance

Recognition observations, focused native Whisper/CTranslate2 alignment and explicit estimated-token flags remain in `timing-evidence/`. The spelling correction preserves every cue/word time, confidence and section. `prepare_captions.py` accepts the original ASR brand pronunciation as a matching alias while keeping Bosston as display text. Timing is model-derived; individual entrances may vary by several tenths of a second.

[Media provenance](MEDIA.md), [review findings](REVIEW.md) and [upstream decisions](../../docs/research/bosston-pragon-2026-11-18.md) explain the production and its limits. There is no external publishing step.

## Verified delivery

- [1080p cinematic film](renders/BOSSTON-Pragon-Good-Fortune-Cinematic.mp4): **185.000 seconds**, 1920 × 1080, 30 fps, H.264/yuv420p with 48 kHz stereo AAC; **462.2 MiB**. All **5,550 frames** decode successfully.
- [720p sharing copy](renders/BOSSTON-Pragon-Good-Fortune-Cinematic-720p.mp4): the same complete film, **71.7 MiB**. Full decoding passes; its encoded AAC payload is byte-identical to the master export.
- [Delivery receipt](renders/BOSSTON-Pragon-Good-Fortune-Cinematic.verification.json): all 71 lyric lines, Bosston spelling, cue ordering/bounds and source bindings pass. Both soundtrack channels correlate with the source at zero offset: **0.99683083 / 0.99686263**.
- All **68 encoded shot midpoints** were inspected across five [review sheets](renders/review-cinematic/contact-sheet-01.jpg), and all nine Bosston lyric appearances were separately cropped from the actual MP4 and visually checked. No missing scenes, spelling errors or clipped lyrics were found.
- A [sampled footage-binding audit](renders/Cinematic-motion-binding.json) compared one encoded shot from each of the nine sources against its selected source window and camera crop. All nine pass (SSIM 0.8891–0.9916), with an explicitly allowed two-frame search tolerance.

The full render took **492.8 seconds** on this Windows setup (including 24.0 seconds of media extraction and 461.0 seconds of frame capture). This excludes footage research, admission, preparation and authoring. These are technical and sampled visual checks, not a claim of human-auditioned syllable accuracy or audience response. The earlier image-led export is superseded; use the files containing `Cinematic` for this revision.
