# Atomy Quick Truths batch verification

Verified locally on 2026-10-05. This is delivery evidence, not a claim of views,
earnings or guaranteed reach. Facts and publishing caveats refer to the U.S. plan.

| Episode | Measured narration/timeline | Approved voice | Browser check | Final delivery |
| --- | --- | --- | --- | --- |
| PV is not money | 23.172s | af_heart | Passed | Passed |
| 44% shared pool | 25.625s | af_heart | Passed | Passed |
| 10,000 personal-PV gate | 24.260s | af_heart | Passed | Passed |
| Sponsor selection | 24.644s | af_heart | Passed | Passed |

- Full repository test suite: 174 tests passed.
- Focused batch, metadata, caption-preparation and CLI checks: 37 tests passed.
- Ruff passed for the changed Python sources and tests.
- All four browser checks included 17 runtime/layout/motion/contrast samples;
  browser validation was not skipped. Held text collisions were corrected in
  the actual layouts, not globally suppressed.
- Delivery gates verified H.264/yuv420p, 1080x1920, 30fps, 20–30s MP4s with AAC
  stereo 48kHz audio; every episode has a portrait thumbnail and upload text.
- Speech is locally generated with the locked, previously approved female voice.
  Captions use measured ASR word intervals and source-coverage checks.
- Music receives voice-aware carving and a baked end fade. Final audio mastering
  targets -14 LUFS / -2dBTP. Post-encode measurement: integrated loudness ranges
  from -14.39 to -14.17 LUFS, true peak from -1.98 to -1.90dBTP (AAC overshoot).
- A second batch invocation resumed all four verified outputs without encoding
  again, using unchanged source fingerprints and matching delivery hashes.
- The delivery ZIP contains four final MP4s, four thumbnails, per-video publishing
  text, consolidated titles/descriptions/hashtags, validation summary and a
  labelled five-state visual review for each episode.

No videos were uploaded to YouTube. The unredacted local diagnostic report stays
ignored because it includes absolute workstation paths. Reproduce with the
commands in `SHORTS_BATCH.md`; the committed MP4s and audio are the actual delivery.
