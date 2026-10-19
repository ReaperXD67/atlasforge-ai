# Story-first production: The Unsent Message

The current experiment replaces brand-led lessons with original fictional stories about friendship,
shopping and attention. Atomy is disclosed conversational context after the opening human problem,
not a concealed sales reveal. Every Short resolves its own story; no purchase or conversion is needed
for a good ending. The user reported fewer than four views on recent uploads, but no fresh per-video
impression/retention data was supplied, so this is a new test—not a causal diagnosis or promise of reach.

YouTube recommends making niche subjects accessible through universal problems and delivering the
title/thumbnail promise promptly. This informed the experiment; it does not establish that this format
will perform better. See [official performance guidance](https://support.google.com/youtube/answer/16559650?hl=en)
and the [official Shorts storytelling interview](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/).

## Current batch

| Episode | Format | Human choice |
| --- | --- | --- |
| [She Almost Sent the Wrong Message](../videos/biznex-unsent-message/README.md) | Short | Notice an unanswered request before sending a recommendation |
| [Her Cart Was Full. So Was the Cupboard.](../videos/biznex-full-cupboard/README.md) | Short | Check existing supplies and choose not to order |
| [Her Friend Said No. She Deleted the Follow-Up.](../videos/biznex-already-answered/README.md) | Short | Leave a refusal alone and make an ordinary lunch plan |
| [She Deleted the Perfect Pitch. Here’s What She Sent Instead.](../videos/biznex-the-unsent-message/README.md) | Full video | An illustrated evening ends in a conversation, not a sale |

These are standalone fictional moments with recurring characters, not documentary customer records.
The creative file is [the batch's source of truth](../config/batches/biznex-unsent-stories.creative.json);
the [design spec](UNSENT_STORIES_DESIGN.md) fixes character continuity, fonts, palette and safe zones.

## What the pipeline adds

- Optional spoken-fiction and narrative-marker contracts checked against measured audio cues.
- Arbitrary batch format counts and chapters that reference segment IDs instead of fixed scene numbers.
- Six authored visual worlds: room, phone, cupboard, paper, calendar and a two-person split view.
- Original character artwork and generic supplies; plain-text Atomy context, without copied logos or packaging.
- Literal speech-anchored message/action events; missing anchors fail instead of receiving guessed times.
- The approved local `af_heart` voice, per-line audio cache, measured captions, restrained action sound
  marks, voice-aware music carving and observed final loudness gates.
- A final MP4, thumbnail and upload package per episode, plus one ZIP and combined publishing copy.

Narrative checks establish ordering and literal consistency, not semantic accuracy or viral potential.
ASR word times are measured estimates, not native TTS alignment. When ASR bundles words into one
measured interval, an event uses that interval rather than inventing a narrower timestamp.

## Rebuild on Windows

Install the repository's Python environment, local Kokoro/Whisper models, FFmpeg and Node 22+ first.
New projects must be initialized with HyperFrames, briefed, and supplied with the local fonts/vendor
assets before preparation. The four included projects pin HyperFrames `0.8.174`; old projects are
not silently upgraded. Run these commands from the repository root:

```powershell
.venv/Scripts/python.exe scripts/prepare_production_batch.py --creative config/batches/biznex-unsent-stories.creative.json
node scripts/build_story_compositions.mjs --creative config/batches/biznex-unsent-stories.creative.json
$taskSkillsRoot = "C:/path/to/HyperFrames/skills"
node scripts/refine_production_audio.mjs --creative config/batches/biznex-unsent-stories.creative.json --skills-root $taskSkillsRoot --core-project videos/biznex-unsent-message
node scripts/capture_production_thumbnails.mjs --creative config/batches/biznex-unsent-stories.creative.json
.venv/Scripts/python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-unsent-stories.creative.production.json --dry-run
```

The audio finishing helper needs the matching `@hyperframes/core` installed in the first project:
`npm --prefix videos/biznex-unsent-message install` restores its pinned dependency. Set the skills
path to your actual installation. Inspect scene-midpoint snapshots, resolve the browser audits, and
open the editable Studio preview before the approved delivery render:

```powershell
.venv/Scripts/python.exe -m daily_video_factory.cli render-production-batch --manifest config/batches/biznex-unsent-stories.creative.production.json --resume
.venv/Scripts/python.exe scripts/package_production_batch.py --manifest config/batches/biznex-unsent-stories.creative.production.json
```

The runner performs 17 browser samples for Shorts and 60 for full videos. Existing exports are reused
only when current media, voice, metadata, story checks and source hashes pass. Packaging resumes the
runner if necessary; it is not a read-only archive command. Do not rebuild HTML after carving or
while a render is running. Use `--only <episode-id>` during preparation/build for a targeted repair.

Local delivery package: `output/biznex-unsent-stories/biznex-unsent-stories.zip`, with four MP4s,
four thumbnails, four upload packages, `UPLOAD_ALL.md` and `DELIVERY_SUMMARY.json`—14 members.
Final runtimes and measured audio outcomes belong in the delivery summary, not planning estimates.

## Publishing and learning

This workflow does not upload to YouTube. Review the fiction label, title promise, complete video,
applicable member/media permissions and any material connection before posting. The
[U.S. member agreement](https://us.atomy.com/common/footerTermsInfo?isHtml=Y&tabIndex=1)
is a market-specific ethics/reference check, not proof of approval in another country. The films do
not assert real product results, prices, recruitment obligations, customer experiences or earnings.

Use the delivered landscape thumbnail for the full video; Shorts cover selection depends on the
upload surface. Record format-specific results at comparable 24-hour and seven-day windows. For
Shorts, compare shown-in-feed, stayed-to-watch and retention; for full videos, compare impressions,
CTR by traffic source and first-30-second retention. With tiny samples, preserve uncertainty and
change one meaningful variable rather than declaring either a winning formula or a shadow ban.

## Delivery status

All four final exports are verified: Shorts at **25.1, 25.6 and 28.9 seconds**, and the full film at
**303.6 seconds (5:03.6)**. Project READMEs link the committed MP4s, thumbnails and publishing copy.
The 34,427,215-byte local archive contains all 14 expected members and passed its CRC integrity check.

- Every MP4 passed complete decoding and media/voice/editorial checks. All four were reused without
  re-encoding when packaging rechecked current source and output hashes, including after README updates.
- All 37 scene midpoints were reviewed; the full film's final MP4 also received matching-time scene,
  opening and ending review. Strict browser audits used 17 samples per Short and 60 for the film.
- Final audio measures −14.44 to −14.15 LUFS, with true peaks no higher than −1.40 dBTP.
- Regression validation passed **377 Python tests** and **30 Node tests**, including actual GSAP
  forward/backward seeking of established drafts and deletions.

See [combined titles, descriptions, hashtags and chapters](../videos/BIZNEX_UNSENT_STORIES_UPLOADS.md)
and the [measured delivery summary](BIZNEX_UNSENT_STORIES_DELIVERY.json). Summary media paths refer
to files inside the ZIP; project READMEs are the repository's clickable media entry points.
No YouTube upload or audience-outcome claim is made.

## Share the complete bundle

[Download the public Discord-ready ZIP](https://raw.githubusercontent.com/ReaperXD67/atlasforge-ai/main/deliveries/biznex-unsent-stories-discord.zip).
Share that URL directly; the recipient does not need access to the creator's local files.
This distribution copy preserves all 14 original archive members and adds `START_HERE.txt`,
which explains the folders and supplies four comma-separated YouTube tag lists, separate from
the supplied hashtags. Its 15 members passed CRC verification and the original members' hashes
match the verified delivery archive. Extract it before using the media and upload copy.
