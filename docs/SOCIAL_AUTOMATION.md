# Social Operator

AtlasForge can render an authored production batch, verify its deliveries, enqueue dated
posts, publish through the YouTube and Meta APIs, and compare exported measurements. The
queue and learning tools run locally. Account ownership, platform authorization and hosted
Meta media are prerequisites, not outcomes of installing the code.

## Delivery status

As of 6 November 2026, the adapters, queue, local analytics importer and directed narration
are implemented and tested. Google registration was started in the side browser and reached
password creation. It was not completed. No new Gmail, YouTube, Instagram or Facebook account
was verified, and no new credentials or live publishing receipts exist. The local connection
check reports missing YouTube OAuth configuration and Meta credentials. No audience metrics
were available; the analytics report correctly returns `no_observations`.

The system does not yet automatically fetch platform analytics, refresh Meta tokens, host
media, buy ads, answer comments/DMs, or create account identities. The daily agent can prepare
and review production work; the queue worker publishes only configured, verified jobs.

## Account setup

Keep **BizNex**, using the bios and handle candidates in [the growth plan](SOCIAL_GROWTH.md).
The required assets are a Google-owned YouTube channel, a professional Instagram account,
and a Facebook Page managed by a legitimate owner account. Keep recovery details under the
owner's control. Passwords are not needed by the publishing worker and never go in campaign
files, Git, logs, or public docs.

For YouTube, install the `youtube` extra, create a Desktop OAuth client, save its JSON at
the configured `YOUTUBE_CLIENT_SECRETS_FILE`, and complete `youtube-auth` once. The worker
checks the authenticated channel ID against the campaign before upload. A new/unverified API
project can have platform restrictions; follow the current
[YouTube upload documentation](https://developers.google.com/youtube/v3/docs/videos/insert).

For Meta, follow [Meta setup](META_PUBLISHING.md): Page linkage, professional account,
publishing permissions, app access requirements, explicit Graph API version and Page token.
Store the four `META_*` values in ignored `.env` or the process environment. The worker does
not automate app review. Public HTTPS media must be reachable without a login and remain
available during processing. Use a stable direct URL; expiring URLs are a poor unattended
publishing input. Its bytes must equal the verified local MP4.

```powershell
.\.venv\Scripts\python.exe -m daily_video_factory.cli social doctor
.\.venv\Scripts\python.exe -m daily_video_factory.cli youtube-auth
```

The doctor is an offline configuration check. It does not verify live Meta permissions.

## From production to publication

Start with an original [production batch](PRODUCTION_BATCH.md) or
[story batch](STORY_BATCH.md). Its sources, script, voice, thumbnail and final render must
pass the existing editorial and media gates. Use the [voice direction plan](VOICE_DIRECTION.md)
to direct pace/pauses; confirm the selected provider's report before assuming emotion control.

Copy [the example campaign](../config/campaigns/biznex-launch.example.json) to a private local file
under `output/social/`, replace account IDs, schedule offsets, media URLs and subtitle paths,
and point it at the production manifest. All media/document references are repository-relative;
`publish_at` must have an explicit timezone. Every post ID is stable within its campaign.
See [the complete campaign contract](SOCIAL_CAMPAIGNS.md) for fingerprint, freshness and recovery details.

YouTube visibility defaults to `private`. Instagram/Facebook posts must explicitly use
`privacy: "public"`; these adapters do not implement a private Meta rehearsal. `--execute`
publishes to the specified destination. A dry run sends no upload and does not verify remote
permissions or hosted bytes.

```powershell
# One local cycle: render/resume, verify, enqueue, preview due posts, write learning report.
.\scripts\run_social_cycle.ps1 -Campaign output/social/campaign.json
# Existing verified renders can skip rendering, but still undergo delivery validation.
.\scripts\run_social_cycle.ps1 -Campaign output/social/campaign.json -SkipRender
# Actual publishing after account setup; YouTube uses each post's declared privacy.
.\scripts\run_social_cycle.ps1 -Campaign output/social/campaign.json -SkipRender -Publish
```

The cycle enqueues the selected campaign, then processes up to five globally due jobs from
the shared queue, which may include other previously enqueued campaigns. Check `social status`
before executing. It does not automatically import metrics or author the production brief.

Individual commands work on Windows and other Python environments:

```powershell
.\.venv\Scripts\python.exe -m daily_video_factory.cli social enqueue --campaign output/social/campaign.json
.\.venv\Scripts\python.exe -m daily_video_factory.cli social status
.\.venv\Scripts\python.exe -m daily_video_factory.cli social run-due
.\.venv\Scripts\python.exe -m daily_video_factory.cli social run-due --execute
.\.venv\Scripts\python.exe -m daily_video_factory.cli social watch --execute --interval-minutes 5
```

`watch` is a foreground process, not an installed Windows service. It handles up to five
due posts per tick, serializes workers with a file lock, and coalesces missed ticks. Keep the
machine awake and process running. The optional Codex daily operator is separate: it follows
the [operator instructions](SOCIAL_OPERATOR.md), prepares work and reports meaningful changes.
It does not turn missing credentials into connected accounts.

## Queue behavior and recovery

`output/social/queue.sqlite` binds each job to its verified files, complete settings,
publication metadata and account. The same video hash cannot be enqueued twice for the same
platform/account, even under another campaign. Changed queued artifacts/settings block
publication. Re-enqueueing an unchanged campaign is safe; it does not reset receipts.

| State | Meaning | Action |
| --- | --- | --- |
| `pending` | Due later, processing remotely, or awaiting a bounded read retry | Run the worker on its schedule; inspect `next_attempt_at` |
| `blocked` | Setup, verification or retry limit requires attention | Correct the cause, then use `retry-blocked` |
| `uploading` | A YouTube mutation began; a crash may leave its result unknown | Next executing worker changes an interrupted job to `uncertain` |
| `uncertain` | A remote mutation may have succeeded | Reconcile with the actual platform; never delete the receipt or blindly upload again |
| `published` | Adapter confirmed the upload/publication operation | The receipt records its remote ID; YouTube privacy may still be private |

```powershell
.\.venv\Scripts\python.exe -m daily_video_factory.cli social retry-blocked --post-key campaign-id:post-id
```

The retry command refuses uncertain/published jobs. There is deliberately no blind reset for
an ambiguous result. A confirmed YouTube video ID survives accessory failures. An ambiguous
caption insertion stops for reconciliation too. Meta receipt files live beside the queue;
do not discard them. An `--execute` run returns a nonzero status when a processed job becomes
blocked/uncertain. `status` shows all jobs, including ones no longer eligible for automatic retry.

If a signed media URL expires after enqueue, the immutable job cannot silently change that
input. Reconcile any remote receipt before replacing a job through a reviewed migration;
there is no supported automatic URL-rotation command in this release.

## Learning and creative decisions

Import normalized platform exports using [the analytics schema](SOCIAL_GROWTH.md). Preserve
missing values and metric definitions. The report keeps platform/account/format cohorts
separate and matches cumulative snapshots at 24/72 hours or a selected age. A new channel,
a single large view count, or a new voice does not establish a repeatable improvement.

Use [the experiment plan](../config/social/experiment-plan.json) to compare question-first
and evidence-first openings on fresh topics. It is planning data, not a populated publish
queue. Keep U.S. Atomy details labeled until another market's official sources are reviewed.
The [first six briefs](BIZNEX_LAUNCH_BRIEFS.md) include exact scripts, source mappings, planned
shots and validated voice directions. They still require production and media review.

## Reference reel and research

The supplied [Instagram reel](https://www.instagram.com/p/De90LRWT20V/) was inspected in the
browser on 6 November 2026. The player reported 74.68 seconds. Viewed moments showed a
presenter with editing demonstrations, a stylized low-poly character, inset clips and short
captions. Its caption asks viewers to comment “EDIT” for a link. Selected visual observations
are not a full transcript or evidence that this format converts Atomy prospects. The creative
adaptation is to show a concrete decision and its evidence early, then deliver a useful payoff;
no creator footage, voice or script was copied.

[The upstream review](UPSTREAM_RESEARCH.md) records exact revisions, code/model licenses,
maintenance and dependency costs for BRAG and expressive voice/alignment candidates. Existing
HyperFrames skills remain the composition workflow; no unrelated skill pack was installed.
