# BizNex Repair Lab experiment

## Observed, not inferred

The user supplied YouTube Studio screenshots for 11 September–8 October 2026. Channel overview: 161 views, 0.8 watch hours, +1 subscriber; realtime: 33 views in 48 hours. Shorts traffic: search 57.8%, Shorts feed 19.0%, channel pages 12.0%, notifications 6.3%, browse 2.8%, other 2.1%. Shorts engagement: 54.2% stayed, 45.8% swiped. These are channel aggregates with a small sample, not per-video causal evidence. No long-video impressions, CTR or first-30-second retention graph was supplied. Private screenshots are not committed.

The earlier public screenshots show an Atomy-heavy channel with low raw views. They cannot establish shadow banning, a bad voice as the cause, or any particular thumbnail failure.

## What changes in this batch

Test broader, searchable beginner problems aligned with BizNex's business-help positioning. Two linked teaching pairs show a visible before/after immediately: sales-message repairs and a one-page offer. A third Short explains the pay-to-unlock task-scam pattern using FTC guidance. Each clip has one actionable payoff rather than an abstract Atomy rule, sales hype or a long subscribe intro.

The visual system uses a case-file repair workspace, accurate negative/positive markup, fictional Sunny Café menu rows and measured spoken-cue reveals. The older approved female narrator is locked to local Kokoro `af_heart`. No cloud generation charges. Local word alignment is estimated ASR, not native TTS timing; zero-duration ASR tokens stay bundled with an adjacent measured interval rather than receiving invented boundaries.

Marketing templates and the five-second reader exercise are original educational heuristics, not empirically validated conversion rules. Café, prices, project scope and sample messages are fictional. Do not claim real client results or guaranteed clients, income, replies or viral reach.

## Reproduce

Initialize new HyperFrames projects with the appropriate aspect ratio and pinned CLI before prep, then write their BRIEF.md. Assets must include the embedded fonts and local GSAP file. Generation is separate from rendering:

```powershell
$taskSkillsRoot = "C:/path/to/HyperFrames/skills"
.venv/Scripts/python.exe scripts/prepare_production_batch.py --creative config/batches/biznex-repair-lab.creative.json
node scripts/build_production_compositions.mjs --creative config/batches/biznex-repair-lab.creative.json
node scripts/refine_production_audio.mjs --creative config/batches/biznex-repair-lab.creative.json --skills-root $taskSkillsRoot --core-project videos/biznex-sales-message-repair
node scripts/capture_production_thumbnails.mjs --creative config/batches/biznex-repair-lab.creative.json
.venv/Scripts/python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-repair-lab.creative.production.json --dry-run
.venv/Scripts/python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-repair-lab.creative.production.json --resume
.venv/Scripts/python.exe scripts/check_production_audio.py --manifest config/batches/biznex-repair-lab.creative.production.json
.venv/Scripts/python.exe scripts/package_production_batch.py --manifest config/batches/biznex-repair-lab.creative.production.json
```

Replace `--skills-root` with your installed HyperFrames skills directory; install the project-pinned `@hyperframes/core` in `--core-project` before the audio step. It writes speech-following music EQ and level envelopes into existing HTML using the public audio helper. Rebuilding HTML requires rerunning this finishing step.

Preparation caches narration per spoken line, voice, speed and pause settings. Audio digests and measured intervals are checked before reuse. Changing text invalidates only that cue; visual changes do not regenerate the voice. The mixed runner source-hashes final assets/plans but excludes regenerable production caches. Long videos receive 60 browser samples; Shorts 17. Export uses the Windows Chrome fallback, one software worker, voice-aware music carving and loudness mastering. Delivery gates check real codecs, dimensions, frame rate, duration, voice, thumbnails, metadata/chapters and literal editorial anchors. These checks do not predict audience response or automatically prove factual/semantic quality; a human-style visual/script review remains necessary.

Packaging resumes the renderer if a delivery is missing or stale, then measures actual MP4 audio before writing the bundle. It rejects nonfinite/silent readings, integrated loudness outside −15.5 to −12.5 LUFS, or true peaks above −1 dBTP. These are this pipeline's chosen delivery tolerances, not a claim about YouTube requirements or a substitute for listening. The publishable summary uses verified video runtimes and measured levels, not planning estimates or private diagnostic paths.

## Evaluate after publishing

Publish manually. Link each relevant Short to its matching long video using YouTube's related-video control when available; do not invent watch URLs before uploads. Keep the first titles consistent with the delivered promise. Use the supplied long-video thumbnail; select the designed in-video cover for Shorts when the upload surface supports it.

Record results separately for Shorts and long videos, at comparable 24-hour and 7-day windows. For Shorts, inspect shown-in-feed, stayed-to-watch, average percentage viewed and retention dips. For long videos, inspect impressions, CTR by traffic source, first 30 seconds, average view duration and traffic sources. Search-heavy viewing and feed viewing should not be conflated. One small sample is not evidence of a winning format. Change one meaningful variable for the next test instead of declaring victory or redesigning everything after a single upload.

## Verified delivery — 10 October 2026

All five final MP4s passed media, voice, metadata and measured audio gates. All use the approved `af_heart` narrator. The observed integrated loudness ranges from −14.60 to −14.20 LUFS; true peaks remain at or below −1.82 dBTP. These readings do not predict views. The videos have not been uploaded to YouTube.

| Episode | Verified runtime | Repository project |
| --- | --- | --- |
| Sales message repair | 25.7 seconds | [Video, thumbnail and upload copy](../videos/biznex-sales-message-repair/) |
| Five-second offer test | 25.9 seconds | [Video, thumbnail and upload copy](../videos/biznex-five-second-offer/) |
| Pay-first job warning | 27.5 seconds | [Video, thumbnail and upload copy](../videos/biznex-pay-first-job-warning/) |
| Sales messages: five fixes | 5:32.7 | [Video, thumbnail and upload copy](../videos/biznex-sales-message-five-fixes/) |
| One-page offer | 5:46.3 | [Video, thumbnail and upload copy](../videos/biznex-one-page-offer/) |

The [combined publishing copy](../videos/BIZNEX_REPAIR_LAB_UPLOADS.md) contains all titles, descriptions, hashtags and long-video chapters. The [delivery summary](BIZNEX_REPAIR_LAB_DELIVERY.json) records actual runtimes and audio measurements; its relative media paths refer to files inside the generated download ZIP, not repository paths. Packaging creates the local bundle at `output/biznex-repair-lab/biznex-three-shorts-two-videos.zip` with five MP4s, five thumbnails, five upload packages and these two summary files.

Official references:

- [YouTube content-performance metrics](https://support.google.com/youtube/answer/12220281)
- [YouTube analytics guidance for content](https://support.google.com/youtube/answer/12942217?co=YOUTUBE)
- [Audience retention](https://support.google.com/youtube/answer/9314415?hl=en)
- [FTC task-scam warning](https://consumer.ftc.gov/consumer-alerts/2025/08/how-spot-avoid-task-scams)
- [FTC unsolicited job-text warning](https://consumer.ftc.gov/consumer-alerts/2026/04/job-offer-text-probably-scam)
- [SBA marketing-plan background](https://www.sba.gov/counseling/manage-your-business/)
