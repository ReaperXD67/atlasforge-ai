# Resumable Shorts batches

One manifest queues several independent Shorts. Rendering is sequential to avoid
four browser encoders competing for the workstation's memory. Authoring and
packaging can happen in parallel. This creates files locally; it never uploads
videos to YouTube.

## Current example: Atomy Quick Truths

The creative spec is `config/batches/atomy-quick-truths.creative.json`. It contains
four distinct hooks, locked source facts, narration cues, title/description/hashtags
and custom portrait poster copy. These episodes cover the **U.S. plan**, not every
Atomy market. Consult the linked official sources before adapting them elsewhere.

The current approved narrator is **Kokoro `af_heart`**. Provider fallback is not
allowed to silently change this batch's voice. Local generation incurs no paid
cloud calls. Neither the scripts nor thumbnails promise earnings or viral reach.

## Preparation

Initialize each episode's HyperFrames project before preparing it. The supplied
example projects already exist. Then run from the repository root:

```powershell
.venv\Scripts\python.exe scripts/prepare_local_shorts_batch.py --creative config/batches/atomy-quick-truths.creative.json
node scripts/build_shorts_thumbnails.mjs config/batches/atomy-quick-truths.creative.json
```

The audio helper needs cached local Kokoro models, `kokoro-onnx`, `soundfile`,
`numpy`, `faster-whisper` and the local small.en Whisper model. It reuses audio
when the locked request is unchanged, measures each cue, refuses runtimes outside
20–30 seconds and transcribes speech for caption timing. ASR word boundaries are
estimates, not native TTS timestamps; review them for omissions and proper nouns.
Do not replace speech timing with uniformly distributed words.

The thumbnail builder writes an editable poster HTML file to each project's
`thumbnail/index.html`. Capture it with system Chrome at exactly 1080×1920 into
`assets/thumbnails/thumbnail.png`. Use a disposable profile outside the repository
and **wait for each Chrome capture to exit** before starting the next one.

Author each episode's visual frame from its measured `STORYBOARD.md`. Assemble
all four authored frames, measured captions and voice-aware music with:

```powershell
node scripts/finalize_shorts_batch.mjs --creative config/batches/atomy-quick-truths.creative.json --skills-root C:/Users/Aman/.agents/skills --core-project videos/atomy-pv-not-money-short
```

Change `--skills-root` to your installed HyperFrames skills location. This step
does not regenerate speech. Preparation bakes a clean music end-fade into each
episode; assembly carves speech frequencies and levels out of the music bed.
Run the full check and visually inspect midpoint frames before delivery.

## Render all four with one command

```powershell
.venv\Scripts\python.exe -m daily_video_factory.cli render-shorts-batch --manifest config/batches/atomy-quick-truths.batch.json --dry-run
.venv\Scripts\python.exe -m daily_video_factory.cli render-shorts-batch --manifest config/batches/atomy-quick-truths.batch.json
```

Default `--resume` skips only previously successful episodes whose source
fingerprint **and output hashes** still match and whose delivery validates.
`--fresh` re-renders everything. Updating a script, composition, local media,
thumbnail or upload text invalidates the affected episode. Failed episodes do
not prevent independent episodes from running; the overall command exits with
failure until every episode succeeds.

`BATCH_REPORT.json` is written beside the manifest and records per-episode
success/failure, source hashes, commands and delivery results. It includes local
absolute paths for diagnostics; do not publish it unredacted.

## Delivery gates

- Local system Chrome, one worker, software browser mode and pinned CLI version.
- Full HyperFrames runtime/layout/motion/contrast check before encoding.
- Final H.264/yuv420p MP4, 1080×1920, 30 fps, 20–30 seconds.
- Voice-preserving audio mastering targeting −14 LUFS / −2 dBTP, AAC stereo 48 kHz.
- Required 1080×1920 thumbnail, title/description/at least three hashtags, voice manifest.
- Final media, thumbnail, metadata and `af_heart` voice-lock validation.

Each project has `UPLOAD_PACKAGE.md` with copy-ready publishing text. A separate
portrait PNG is included even where the Shorts upload surface only lets you pick
an in-video cover. Select a legible hook/reveal frame in that case. Upload remains
a separate, explicit user action.

Package the verified MP4s, four PNG thumbnails, publishing text and five-state
review sheet with:

```powershell
.venv\Scripts\python.exe scripts/package_shorts_batch.py --creative config/batches/atomy-quick-truths.creative.json
```

The packager refuses missing review snapshots instead of silently shipping a
thumbnail-only review sheet. Files are written to `output/atomy-quick-truths/`.
