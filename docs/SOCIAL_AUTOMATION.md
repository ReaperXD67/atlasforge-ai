# Social Operator

AtlasForge can render authored production batches and story projects, verify deliveries,
enqueue dated posts, publish through supported APIs, retain verified browser publication
receipts, and compare exported measurements. The queue and learning tools run locally.
Account ownership and platform authorization are prerequisites; Meta API publishing also
needs hosted media. Installing this code does not create accounts or grant platform access.

## Delivery status

As of 7 November 2026, the adapters, queue, local analytics importer and directed narration
are implemented and tested. Gmail, the BizNex YouTube channel,
[Instagram creator profile](https://www.instagram.com/biznex.stories/) and
[Facebook Page](https://www.facebook.com/profile.php?id=61595985973734) have been created in
the authorized browser session. YouTube OAuth completed,
and a live authenticated channel check returned the expected channel
[`UCEoGrcisSgAFiu0EkBuDq8w`](https://www.youtube.com/channel/UCEoGrcisSgAFiu0EkBuDq8w).
The first pilot is now [public on YouTube](https://www.youtube.com/watch?v=bQlvLxzPRSc).
It was uploaded once, verified privately, then promoted using the same video ID. API readback
confirmed the exact channel and title, successful processing, and public visibility.

The first pilot is also public on [Instagram](https://www.instagram.com/p/DfZZeJoKLBl/),
with its AI label enabled, and on the Facebook Page (published item `122104950951532865`).
These Meta releases were completed through the browser. Meta API setup is still waiting
for the SMS code required by developer phone verification; Meta also refused the
Instagram–Page link. Instagram/Facebook API publishing permissions and API publishing
receipts have not been established. Account passwords and OAuth tokens remain
outside repository documentation and campaign files.

The [six-pilot production batch](../config/batches/biznex-first-six.production.json) has
original compositions, measured narration, aligned captions and captured thumbnails.
All six MP4s are rendered and passed the matching production batch's delivery verification:
1080 x 1920 at 30fps, H.264 video and stereo 48kHz AAC audio. See the
[delivery guide](PILOT_DELIVERY.md) for reproducible export and review commands.
The verified 40,642,538-byte ZIP was exported, and 18 decoded frames from the six actual
videos were reviewed. The user subsequently rejected the batch's creative quality. The five
unpublished YouTube follow-ups are now **held**, retaining their original 7–11 November dates
and immutable inputs in `output/social/biznex-first-six.queue.sqlite`. A future dry run finds
zero eligible posts; the first published row and all receipts remain unchanged. The private
campaign is `output/social/biznex-next-five.public.campaign.json`. Re-enqueueing it does not
release the hold. Meta follow-ups are not included in this queue. Technical delivery passes
did not establish creative acceptance; [the cinematic acceptance brief](CINEMATIC_ACCEPTANCE.md)
sets the replacement review criteria.
The initial analytics report returned `no_observations`. Real YouTube and Instagram
observations were retained locally on 9 November; unequal post ages and missing retention
prevent a controlled performance comparison. No causal improvement is claimed.

The owner subsequently authorized **The Yes Machine**, now public on
[YouTube](https://www.youtube.com/shorts/Dc4aBDQfQ9w),
[Instagram](https://www.instagram.com/p/Dfch-tjKvp7/) and
[Facebook](https://www.facebook.com/reel/1759901191770877). Its verified final file is
`videos/biznex-the-yes-machine/renders/final.mp4`, SHA256
`ccd05da3eca962865eb92a197d92c5feb2f1a5df9ab0d79442ddb32b3060cc43`.
YouTube API readback confirmed successful processing, public visibility and all 16 exact
subtitle cues. Instagram and Facebook were confirmed through their signed-in browser flows,
with public visibility and AI labels; this does not establish Meta API authorization.
Ignored evidence is retained under `output/social/2026-11-07/`.

The owner **paused recurring operation on 9 November 2026** and requested work
only on explicit instruction. The Codex automation is PAUSED, with no new automatic
production or publishing. The requested Borrowed Countdown release is a single manual
operation. Existing receipts and the five rejected-pilot holds remain in place.
See [the operating brief](SOCIAL_OPERATOR.md) and [campaign contracts](SOCIAL_CAMPAIGNS.md).

The system does not yet automatically fetch platform analytics, refresh Meta tokens, host
media, buy ads, answer comments/DMs, or create account identities. The daily agent can prepare
and review production work; the queue worker publishes only configured, verified jobs.

## Account setup

**BizNex** is the channel identity. [The growth plan](SOCIAL_GROWTH.md) contains the editorial
positioning and original handle proposals; proposals are not a record of assigned handles.
Publishing requires a Google-owned YouTube channel, a professional Instagram account,
and a Facebook Page managed by a legitimate owner account. Keep recovery details under the
owner's control. Passwords are not needed by the publishing worker and never go in campaign
files, Git, logs, or public docs.

The current YouTube connection is authenticated to the channel above. For a new installation,
install the `youtube` extra, create a Desktop OAuth client, save its JSON at
the configured `YOUTUBE_CLIENT_SECRETS_FILE`, and complete `youtube-auth` once. The worker
checks the authenticated channel ID against the campaign before upload. A new/unverified API
project can have platform restrictions; follow the current
[YouTube upload documentation](https://developers.google.com/youtube/v3/docs/videos/insert).

The current Google OAuth app remains in **Testing**. For an external app requesting YouTube
scopes, Google documents a seven-day refresh-token lifetime in this state. Plan for
reauthorization while Testing remains in use; the verified connection does not establish
indefinitely unattended operation. [Google refresh-token expiration](https://developers.google.com/identity/protocols/oauth2/#expiration).

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

Inspect the actual pilot follow-up queue with its explicit database path:

```powershell
.\.venv\Scripts\python.exe -m daily_video_factory.cli social status --database output/social/biznex-first-six.queue.sqlite
.\.venv\Scripts\python.exe -m daily_video_factory.cli social run-due --database output/social/biznex-first-six.queue.sqlite
```

The second command is a dry run. The general examples below use the default queue unless
an explicit database is supplied.

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
| `held` | Scheduling deliberately suspended in the persistent database | Preserve the approved payload and receipts; explicitly resume selected keys only when release is authorized |
| `browser_claimed` | A browser job was reserved before a possible remote mutation | Inspect the same account/post and record confirmed evidence; never automatically repeat the upload |
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

Hold or resume exact keys with repeatable options; neither command publishes anything:

```powershell
.\.venv\Scripts\python.exe -m daily_video_factory.cli social hold --database output/social/queue.sqlite --post-key campaign-id:post-id --post-key campaign-id:another-post
.\.venv\Scripts\python.exe -m daily_video_factory.cli social resume --database output/social/queue.sqlite --post-key campaign-id:post-id
```

The full selection is validated and changed atomically under the same lock as the worker.
Missing, published, uploading, blocked or uncertain keys reject the entire operation. Repeated
hold/resume calls are idempotent. Only state and its update timestamp change; payloads, receipts,
attempt counts, original publication dates and retry delays stay intact. Held rows survive
restarts and are skipped by both `watch` and manual `run-due --execute`. This is a local queue
hold, not a cancellation of an already completed or in-flight platform operation: an active
worker owns the lock and the hold fails until it finishes. Verify `status` after a lock error.

**Resuming an overdue job makes it eligible for the next worker run.** Resume does not re-date
it, run it, or revalidate it immediately; normal source, source-age and delivery checks still
run before publication. For this rejected batch, leave all five held. Replacement creative
needs new production and post IDs and a reviewed schedule; do not reset old receipts.

The existing APScheduler 3.11.3 dependency (MIT) supports pausing scheduler jobs, but that
does not protect a separate manual queue execution. The persistent queue-state design uses
the existing SQLite/portalocker stack with no additional dependency or copied upstream code.
See the [APScheduler pause/resume contract](https://apscheduler.readthedocs.io/en/3.x/userguide.html#pausing-and-resuming-jobs).

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
The [first six pilots](BIZNEX_LAUNCH_BRIEFS.md) include exact scripts, source mappings,
original compositions and measured voice/caption timing. Final renders and complete-film
review must pass before a dated publication campaign is enqueued.

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
