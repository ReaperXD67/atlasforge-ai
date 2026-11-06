# Build and export the six pilot deliveries

The six source projects are listed in
[the production manifest](../config/batches/biznex-first-six.production.json). All six final
MP4s passed the matching batch report on 6 November 2026: 1080 x 1920, 30fps, H.264 and
stereo 48kHz AAC. The export helper separately packages the verified files. Account and publication milestones are tracked in
[the launch guide](BIZNEX_LAUNCH_BRIEFS.md).

The export completed successfully at `output/deliveries/biznex-first-six.zip`
(40,642,538 bytes). Its SHA-256 is
`735b7cae1393ea6f02309207cf01e3580294faaf405d9151f7c31938b816569f`.
The exporter revalidated source fingerprints, delivery hashes and loudness. The separate
contact sheet contains 18 frames decoded from the six actual MP4s and was visually reviewed.
The existing export is preserved; the helper intentionally refuses to overwrite it.

## Rebuild from the authored briefs

Run from the repository root. Use the prepared Python environment with the cached Kokoro
and Whisper models required by `prepare_pilot_batch.py`, Node/npm, and `ffmpeg`/`ffprobe`
on PATH. Thumbnail capture uses installed Chrome; on Windows the default is
`C:/Program Files/Google/Chrome/Application/chrome.exe`. Set `HYPERFRAMES_BROWSER_PATH`
if Chrome is elsewhere. The projects pin HyperFrames 0.9.19.

Audio preparation writes measured timing and the production manifest. Build the visuals
after audio preparation so their durations, shots and captions use those measurements.
The first-three builder writes `THUMBNAIL.html`; its thumbnails are captured individually.
The last-three builder writes `thumbnail/index.html` and has a separate capture-only mode.

```powershell
# Generate narration, scored mixes, measured timing, captions and production metadata.
.\.venv\Scripts\python.exe scripts/prepare_pilot_batch.py

# Build all six compositions and their thumbnail HTML from measured timing.
node scripts/build_pilot_first_three.mjs
node scripts/build_pilot_last_three.mjs

# Capture the first three thumbnails; --only is required for these three commands.
node scripts/capture_production_thumbnails.mjs --creative config/batches/biznex-first-six.production.json --only biznex-two-paper-doors
node scripts/capture_production_thumbnails.mjs --creative config/batches/biznex-first-six.production.json --only biznex-card-under-the-cup
node scripts/capture_production_thumbnails.mjs --creative config/batches/biznex-first-six.production.json --only biznex-missing-index-card

# Capture the last three thumbnails after their HTML has been built.
node scripts/build_pilot_last_three.mjs --capture-thumbnails

# Run source/media checks and render or resume the serial batch.
.\.venv\Scripts\python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-first-six.production.json --resume

# Export only after the full six-episode report passes.
.\.venv\Scripts\python.exe scripts/package_pilot_delivery.py package
```

`--resume` reuses only unchanged, previously verified deliveries. Rebuilding source or
timing can invalidate that verification; capture fresh thumbnails and review changed
compositions before delivery. The commands above do not authorize or perform a platform
upload. For an already prepared source checkout, start with the render command and then
export; do not rerun preparation just to package an existing verified batch.

The six pilot source trees, production manifest and fingerprinted runner/verifier files
use scoped `-text` rules in `.gitattributes`. Their verified inputs contain both LF and
CRLF files; Git must preserve those exact bytes rather than normalize them on checkout.
This prevents `core.autocrlf` from invalidating an unchanged delivery. It does not relax
source or media hash checks, and deliberate content changes still require verification.

## Export verified files

The helper exports local final MP4s, thumbnails, upload copy, SRT/JSON captions, transcripts
and audio provenance. It never renders, logs into a platform, enqueues, or uploads.
Generated media stays under ignored `output/`; follow the source-only repository rule in
[CONTRIBUTING.md](../CONTRIBUTING.md).

After the six-episode production runner finishes successfully:

```powershell
.\.venv\Scripts\python.exe scripts/package_pilot_delivery.py package
```

The command requires `config/batches/PRODUCTION_BATCH_REPORT.json` to identify this exact
batch with all six episodes verified. It rechecks current source fingerprints, recorded
delivery hashes, media/editorial validation and measured loudness before exporting. It
does not reuse the older packaging helper that can trigger resumed rendering.

Output:

- `output/deliveries/biznex-first-six/`: one folder per episode plus `UPLOAD_ALL.md`.
- `output/deliveries/biznex-first-six.zip`: a shareable archive; fixed ZIP timestamps and
  entry order make identical package inputs reproducible.
- `output/deliveries/biznex-first-six.zip.sha256`: archive checksum.
- Inside the directory/ZIP, `DELIVERY_MANIFEST.json` records source and exported artifact
  hashes; `SHA256SUMS.txt` covers every other packaged file.

The exporter refuses to replace an existing directory or archive. Preserve or move an
earlier export before another run. Upload-copy paths are adapted only in the exported
copy. Source projects remain untouched. Platform/account credentials and the private
campaign drafts are never included.

For a separate visual review sheet from three actual decoded frames per final video:

```powershell
.\.venv\Scripts\python.exe scripts/package_pilot_delivery.py contact-sheet
# Review only an already-rendered subset while the other episodes are still pending:
.\.venv\Scripts\python.exe scripts/package_pilot_delivery.py contact-sheet --episodes biznex-two-paper-doors
```

This writes `output/deliveries/biznex-first-six-review/contact-sheet.png`, the extracted
frames, and a frame-time/source-hash record. Samples are at 10%, 50% and 85% of measured
duration. This review sheet is not a claim that the full batch passed validation and is
not automatically included in the share ZIP. `ffmpeg` and `ffprobe` must be on PATH;
Pillow is already a base dependency. No original video is modified.

CLI options and failure/success paths are covered by local tests with mocked media
decoders. A real export is established only when the helper actually completes against
the final six-video report; creating this script alone does not establish delivery.
