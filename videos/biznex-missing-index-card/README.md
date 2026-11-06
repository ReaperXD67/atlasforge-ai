# One Card Was Missing From Her Checklist

An original fictional BizNex story about source-check. The empty space becomes a specific question to verify, not a recruitment prompt.

**Rendered and delivery-verified on 6 November 2026:** 26.900 seconds,
1080 x 1920 at 30fps, H.264 video and stereo 48kHz AAC audio. The matching
`config/batches/PRODUCTION_BATCH_REPORT.json` records this episode as verified.
The measured narration/score mix is 26.900 seconds; container
padding can make the encoded duration slightly longer.

A public YouTube post is enqueued for 2026-11-08 at 09:00 Asia/Kolkata in the dedicated pilot queue. It has not yet published; no audience performance is claimed.

Local generated outputs are `renders/final.mp4` and `assets/thumbnails/thumbnail.png`.
They are excluded from Git. The approved `af_heart` voice, original score/foley and exact
captions are backed by [measured timing](timing.json), [editorial sources](EDITORIAL.json)
and [upload copy](UPLOAD_PACKAGE.md). [REVIEW.md](REVIEW.md) records the pre-render visual
review; the batch report establishes the final technical delivery.

## Rebuild

From the repository root, with cached Kokoro/Whisper models and installed Chrome:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_pilot_batch.py --episodes biznex-missing-index-card
node scripts/build_pilot_first_three.mjs --only biznex-missing-index-card
node scripts/capture_production_thumbnails.mjs --creative config/batches/biznex-first-six.production.json --only biznex-missing-index-card
.\.venv\Scripts\python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-first-six.production.json --resume
```

The batch runner reuses unchanged, verified sibling episodes and verifies the rebuilt
sources and delivery. Preview and review changed visuals before release. Rebuilding
invalidates the earlier verification until the runner succeeds again; these commands
perform no platform upload.

See [the full preparation/export guide](../../docs/PILOT_DELIVERY.md) for all-six rebuilds,
share packages and decoded-frame review. [The launch guide](../../docs/BIZNEX_LAUNCH_BRIEFS.md)
tracks account/publication state and the experiment without promising reach.
