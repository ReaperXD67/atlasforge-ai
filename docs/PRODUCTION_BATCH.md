# Mixed-format YouTube production batches

`render-production-batch` queues independent Shorts and full YouTube videos in
one run. It creates local deliverables; it does not publish or modify YouTube.
The existing `render-shorts-batch` command and its manifest remain unchanged.

```powershell
.venv\Scripts\python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/example.production.json --dry-run
.venv\Scripts\python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/example.production.json
```

Rendering stays sequential to keep browser/encoder memory bounded. Research,
scripts, voice generation and visual authoring can run in parallel before this
stage. Use the approved Kokoro `af_heart` narrator for every episode: a provider
fallback must not silently substitute another voice.

## Production manifest

Projects resolve relative to the repository. All deliverable paths resolve inside
their own project; absolute paths, escaping paths, duplicate projects/IDs/outputs
and conflicts with intermediate renders are rejected. Each episode requires an
explicit format and editorial manifest.

```json
{
  "schema_version": 1,
  "batch_id": "example",
  "expected_voice": "af_heart",
  "episodes": [
    {
      "id": "cost-question",
      "project": "videos/cost-question-short",
      "format": "shorts",
      "min_seconds": 20,
      "max_seconds": 35,
      "output": "renders/final.mp4",
      "thumbnail": "assets/thumbnails/thumbnail.png",
      "upload_package": "UPLOAD_PACKAGE.md",
      "voice_manifest": "audio_request.json",
      "editorial_manifest": "EDITORIAL.json"
    },
    {
      "id": "cost-guide",
      "project": "videos/cost-guide",
      "format": "youtube",
      "min_seconds": 300,
      "max_seconds": 360,
      "output": "renders/final.mp4",
      "thumbnail": "assets/thumbnails/thumbnail.png",
      "upload_package": "UPLOAD_PACKAGE.md",
      "voice_manifest": "audio_request.json",
      "editorial_manifest": "EDITORIAL.json"
    }
  ]
}
```

Duration defaults are 20–35 seconds for Shorts and 300–360 seconds for full videos.
Override them per episode when the creative brief calls for another runtime;
Shorts cannot exceed 180 seconds. Bounds must be finite and strictly increasing.
These are delivery requirements, not permission to pad or time-stretch narration.
The separate legacy `verify-shorts-delivery`/Shorts-only workflow still defaults
to 20–30 seconds; the mixed production workflow deliberately passes its own bounds.

## Story-first creative preparation

The reusable preparation script accepts optional series direction, story markers,
chapter references and delivery bounds. This abbreviated **creative** fragment
shows those additional fields; a complete episode also supplies its title,
description, thumbnail copy, hashtags, supported sources and authored segments.
It is not a replacement for the production manifest above.

```json
{
  "schema_version": 1,
  "batch_id": "biznex-unsent-stories",
  "voice": "af_heart",
  "speed": 1.0,
  "series": {
    "name": "The Unsent Message",
    "angle": "A friendship before a pitch",
    "direction": "A fictional character makes a choice; reveal the consequence through actions and props."
  },
  "episodes": [{
    "id": "story-video",
    "project": "videos/story-video",
    "format": "youtube",
    "delivery_bounds": {"min_seconds": 300, "max_seconds": 360},
    "chapter_segments": [
      "setup",
      {"segment_id": "turn", "title": "The message she did not send"},
      "payoff"
    ],
    "story": {
      "fictional": true,
      "disclosure": "This is a fictional story.",
      "protagonist": "Mira",
      "setup_segment": "setup",
      "turn_segment": "turn",
      "brand_connection_segment": "context",
      "payoff_segment": "payoff"
    }
  }]
}
```

`series` requires non-empty `name`, `angle` and `direction`. For story episodes,
existing authored `BRIEF.md` and `frame.md` remain authoritative: preparing cached
audio does not overwrite them. Initialize and brief every project before preparation.
An absent story design receives a generic series-based design, not the old Repair
Lab template.

Each segment keeps its normal `id`, `title`, `kind`, spoken `text`, `display` and
literal `beat_phrases`. Optional `narrative_role` and nested `visual` data pass
through unchanged into measured cues and `EPISODE.json`. For example:

```json
{
  "narrative_role": "turn",
  "visual": {"type": "phone", "location": "kitchen", "expression": "hesitant", "prop": "unsent message"}
}
```

Unknown visual keys are retained for the renderer. Generated storyboards describe
character actions and location/prop continuity, rather than advice cards or a
closing product CTA. They cite the selected HyperFrames motion rules: phone/paper
text states, room/split framing, cupboard reveals and calendar strokes.

Story preparation rejects unknown/duplicate segment IDs and requires an explicit
`fictional: true`, a protagonist and a spoken disclosure that labels the story as
fiction. Marker segment texts must literally occur in the script. The connection
segment must contain the word **Atomy**; this identifies context, not an endorsement,
product claim or conversion payoff. The marker ordering is:

- Setup precedes the dramatic turn; the turn precedes the payoff.
- Setup also precedes the brand connection; the connection precedes the payoff.
- Connection may precede, follow or share the turn's segment; it cannot be the setup.

After narration, those checks use actual measured cue starts, not guessed times.
The generated `EDITORIAL.json` references `audio_meta.json` through
`story.timing_manifest`; delivery reads those cues again, checks their literal
script anchors and requires the editorial payoff time to match its measured cue.
The disclosure is also included in publishing copy.

`chapter_segments` accepts ordered segment-ID strings or `{segment_id, title}`
objects. Long videos require at least three known, distinct references, beginning
with the first segment. Exported chapters start at `00:00` and are at least ten
seconds apart using measured narration starts. Explicit IDs work with arbitrary
scene counts, including a 21-scene story. Without explicit references, legacy
18-scene Repair Lab chapter choices remain unchanged; other counts receive an
automatic selection of up to six cues.

Optional `delivery_bounds` uses the same finite, increasing duration contract as
the production manifest and is propagated to it. Preparation rejects measured
narration outside the bounds instead of stretching speech or adding padding.

The story checks establish completeness, ordering and literal consistency only.
They do **not** prove that a fictional situation accurately represents Atomy,
that sources support every implication, or that the edit will attract views.
Review the complete script, rendered actions, disclosures, factual claims and
title/thumbnail promise before release. No semantic or viral verification is claimed.

### Prepare, build and verify

Run from the repository root after authoring the creative file and project briefs:

```powershell
.venv/Scripts/python.exe scripts/prepare_production_batch.py --creative config/batches/biznex-unsent-stories.creative.json
node scripts/build_production_compositions.mjs --creative config/batches/biznex-unsent-stories.creative.json
node scripts/capture_production_thumbnails.mjs --creative config/batches/biznex-unsent-stories.creative.json
.venv/Scripts/python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-unsent-stories.creative.production.json --dry-run
.venv/Scripts/python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-unsent-stories.creative.production.json
.venv/Scripts/python.exe scripts/package_production_batch.py --manifest config/batches/biznex-unsent-stories.creative.production.json
```

Preparation caches approved narration and ASR per spoken line; visual-only edits
reuse that speech. `--only <episode-id>` on preparation and the composition builder
limits a repair to one known episode. Finish any voice-aware music refinement and
preview review before rendering; rebuilding compositions later invalidates source
fingerprints and can remove authored audio treatment.

## Editorial preparation gate

Each project supplies `SCRIPT.md`, `THUMBNAIL_COPY.txt`, `UPLOAD_PACKAGE.md`, and
an `EDITORIAL.json` shaped like this Short example:

```json
{
  "schema_version": 1,
  "script": "SCRIPT.md",
  "thumbnail_copy": "THUMBNAIL_COPY.txt",
  "audience_problem": "Beginners confuse revenue with profit",
  "hook": {"text": "What did it really cost?", "at_seconds": 0},
  "payoff": {"text": "Subtract all the costs first.", "at_seconds": 23},
  "packaging": {
    "title": "Find the real cost before starting",
    "thumbnail_text": "REAL COST?",
    "promise": "A cost checklist, not an earnings forecast",
    "evidence_anchor": "Subtract all the costs first.",
    "reviewed": true
  },
  "sources": [
    {
      "claim": "The factual claim supported by the linked source",
      "url": "https://www.ftc.gov/business-guidance",
      "checked_on": "2026-10-10"
    }
  ],
  "retention_beats": [
    {"at_seconds": 0, "purpose": "Open with the real question"},
    {"at_seconds": 10, "purpose": "Show a concrete example"},
    {"at_seconds": 23, "purpose": "Deliver the promised checklist"}
  ]
}
```

The example schema is not a fact-checked script: replace its claim and URL with
the precise primary evidence used in the real episode. The preparation gate:

- Requires an audience problem, an early hook, a later payoff and a script anchor
  for the title/thumbnail promise. The hook starts by 2 seconds for Shorts and
  10 seconds for full videos.
- Checks that the hook/payoff/evidence text literally exists in the authored
  script, the title exactly matches publishing text, and thumbnail copy matches
  its declared copy file. Whitespace is normalized for script/copy matching.
- Requires source claims, credential-free HTTPS URLs and ISO source-check dates.
- Requires an explicit creator review declaration for title/thumbnail alignment.
- Requires at least three ordered planned beats, starting at zero, with gaps no
  larger than 12 seconds for Shorts or 45 seconds for full videos. Timing is
  rechecked against the actual delivered video, including its final stretch.

This is a completeness and consistency gate. It does **not** establish semantic
accuracy, verify source pages automatically, inspect actual thumbnail pixels or
prove that planned beats occur in the video. Review sources, rendered thumbnails,
speech timing and scene previews separately. The report explicitly distinguishes
planned beats from observed audience analytics. No view/retention forecasts or
viral guarantees are generated.

## Media verification and resume

Both formats must deliver H.264/yuv420p MP4 at 30 fps, with AAC stereo 48 kHz audio.
The full HyperFrames pre-render check samples 60 points for full videos and 17
for Shorts, so a five-minute timeline is not reviewed with Shorts-only density.
Mastering preserves voice/video and targets −14 LUFS / −2 dBTP using FFmpeg
loudness normalization. It is a mastering target, not an observed measurement.

Shorts route through `-VerifyShorts` and must be 1080×1920 with an equally sized
portrait thumbnail. Full videos route through `-VerifyYouTube`, must be 1920×1080,
and require a 16:9 JPEG/PNG thumbnail at least 1280px wide. Both require publishing
metadata and at least three hashtags; full-video descriptions also require three
or more valid timestamped chapters starting at 00:00. Voice lock and editorial
gates apply equally to both formats.

`--resume` is the default. An episode is skipped only when an earlier success,
source/implementation fingerprints, format/duration contract and final output
hashes match, and all current delivery gates pass again. Missing or replaced MP4s
are never accepted merely because an earlier report exists. Tool caches and
render outputs do not invalidate source fingerprints. `--fresh` rerenders all
episodes; `--dry-run` validates preparation and prints commands without encoding
or overwriting a completed report.

A failed episode does not block independent episodes. The overall command exits
unsuccessfully until all episodes verify. A fresh raw render and a fresh mastered
render are required before the mastered file can replace `final.mp4`; source
changes during rendering reject that attempt. Each completion is saved atomically
in `PRODUCTION_BATCH_REPORT.json` beside the manifest for recovery. That diagnostic
report includes local absolute paths: do not publish it unredacted.

## Download package

Packaging resumes delivery verification first and may rerender a missing or stale
episode; it is not a read-only packaging shortcut. It then measures each actual MP4
and rejects silent/nonfinite audio, integrated loudness outside −15.5 to −12.5 LUFS,
or true peaks above −1 dBTP before writing the new bundle. These are chosen pipeline
tolerances, not claims about YouTube's publishing requirements.

New batches produce `output/<batch_id>/<batch_id>.zip`, `UPLOAD_ALL.md` and
`DELIVERY_SUMMARY.json`. Headings and `format_counts` derive from the manifest,
not a fixed three-Shorts/two-video assumption. Each episode contributes its final
MP4, thumbnail and upload copy; the two aggregate files are included as well.
A three-Shorts/one-video batch therefore contains **14 archive members**. The
summary records verified runtimes, observed audio measurements and ZIP-relative
media paths, while excluding private diagnostic paths. It does not upload anything.

Existing Repair Lab creative files, production manifests and delivery gates remain
supported. The `biznex-repair-lab` batch alone retains its published legacy archive
name, `biznex-three-shorts-two-videos.zip`, so existing download links stay valid.
