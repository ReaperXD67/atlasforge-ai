# Verified social campaigns

The campaign queue connects completed production batches and verified story projects to YouTube, Instagram and
Facebook. It adds persistent schedules, immutable delivery checks, account matching,
cross-campaign duplicate protection and bounded retries. The queue does not predict
reach, create accounts, or replace the creative production workflow.

The implementation has automated tests with mocked platform responses. No live
social account or post is implied by those tests. Connect the real accounts and
complete their platform requirements before enabling execution.

## Verified story projects and browser receipts

Use `story_project` instead of `production_manifest` for a film with the procedural
story delivery contract. Exactly one source is required. Posts must match the project directory's
episode ID and supply an explicit title. The adapter checks current render/source
hashes, encoded audio QA, decoded-frame coverage and the matching sampled
`DELIVERY_REVIEW.json`. It also checks script/copy policy, synthetic disclosure
and exact canonical SRT. These checks do not establish subjective listening, factual
source freshness or audience success; factual lines require the operator's source review.

```json
{
  "schema_version": 1,
  "campaign_id": "new-story-2026-11-08",
  "story_project": "videos/YOUR_VERIFIED_PROJECT",
  "posts": [{
    "id": "instagram",
    "episode_id": "YOUR_VERIFIED_PROJECT",
    "platform": "instagram",
    "account_id": "@YOUR_PROFILE",
    "publish_at": "2026-11-08T18:30:00+05:30",
    "title": "An explicit reviewed title",
    "caption": "Complete prepared copy, including fictional context and synthetic narration disclosure.",
    "privacy": "public",
    "transport": "browser"
  }]
}
```

`transport` defaults to `api`. YouTube API posts use the existing durable uploader
and live channel check; supply `subtitles` as the repository-relative
`assets/audio/narration.srt` inside that project when caption upload is enabled.
Meta API posts still need numeric account IDs, authorization and a hosted URL whose
bytes match the verified local video. Browser Instagram jobs may use their exact
`@handle`; browser Facebook jobs use the numeric Page identity observed in its
user-facing profile. Browser jobs need neither a hosted URL nor a Meta API token.

`run-due`, including `--execute`, returns `browser_action_required` for browser jobs
without contacting a publisher. Reserve the job **before** the browser mutation:

```powershell
.venv/Scripts/python.exe -m daily_video_factory.cli social enqueue --campaign output/social/story.json --database output/social/biznex-stories.queue.sqlite
.venv/Scripts/python.exe -m daily_video_factory.cli social run-due --database output/social/biznex-stories.queue.sqlite
.venv/Scripts/python.exe -m daily_video_factory.cli social claim-browser --post-key new-story-2026-11-08:instagram --database output/social/biznex-stories.queue.sqlite
```

A `browser_claimed` post cannot be claimed again and never automatically replays.
After observing the actual public post, write a local observation JSON:

```json
{
  "platform": "instagram",
  "account_id": "@YOUR_PROFILE",
  "video_sha256": "REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS",
  "title": "An explicit reviewed title",
  "remote_id": "REAL_POST_CODE",
  "url": "https://www.instagram.com/p/REAL_POST_CODE/",
  "privacy": "public",
  "verified_at": "2026-11-08T18:32:00+05:30",
  "method": "browser_observation",
  "evidence_file": "output/social/proof/actual-post.jpg",
  "evidence_sha256": "REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS",
  "confirmed_published": true
}
```

```powershell
.venv/Scripts/python.exe -m daily_video_factory.cli social record-observed --post-key new-story-2026-11-08:instagram --evidence output/social/observation.json --database output/social/biznex-stories.queue.sqlite
```

The command verifies local evidence hashes, platform URL/ID consistency and exact
queued identity/content/privacy, then records the operator's observation. It does
**not** authenticate a screenshot or perform fresh API readback. Use
`method: "api_readback"` only with retained real API evidence. It can reconcile a
completed publication from pending, claimed or uncertain state without uploading
again. Repeating the same ID is idempotent; a different saved remote ID, changed
approved files, wrong account or held job is rejected.

Keep one stories database for deduplication by video SHA, platform and account.
A date-slot cap and cross-database deduplication are not implemented; the operator
enforces one new episode per IST day. On 7 November, all three already published
Yes Machine posts were adopted into `output/social/biznex-stories.queue.sqlite`.
Repeated enqueue returned the same published records and `run-due --execute`
returned no jobs. That adoption campaign uses browser dispatch for all three rows
to prevent accidental replay of the completed YouTube upload; its actual YouTube
receipt explicitly records API readback. Future YouTube jobs can use `api` normally.

The legacy `run_social_cycle.ps1` remains production-batch-only. Story projects use
`run_story_pipeline.py`, followed by the queue commands above. Publication never
runs automatically inside the render pipeline.

### Architecture decision

Retain the existing standard-library SQLite store and Portalocker rather than add
Redis/RQ. SQLite's [immediate transactions](https://www.sqlite.org/lang_transaction.html)
support atomic queue insertion; the started/finished separation in
[RQ's documented job lifecycle](https://python-rq.org/docs/jobs/) reinforces explicit
claim and confirmation states. No upstream code or new dependency was copied.
This extends existing scheduling, hold and receipt behavior rather than migrating it.

## Campaign format

Start with [the example](../config/campaigns/biznex-launch.example.json). Replace its
account and hosted-media placeholders. Choose publication times deliberately;
every `publish_at` must include an explicit UTC offset, such as `+05:30`.

```json
{
  "schema_version": 1,
  "campaign_id": "biznex-pilot-01",
  "production_manifest": "config/batches/biznex-unsent-stories.creative.production.json",
  "posts": [{
    "id": "unsent-youtube",
    "episode_id": "unsent-message",
    "platform": "youtube",
    "account_id": "REPLACE_WITH_YOUR_UC_PREFIXED_CHANNEL_ID",
    "publish_at": "2026-11-07T18:30:00+05:30",
    "caption": "A recommendation can wait. What did your friend actually ask?",
    "privacy": "private"
  }]
}
```

This example intentionally cannot be queued until its real account ID is supplied.
The production manifest must reference existing final media that passes the normal
production delivery and editorial gates. All referenced paths are relative to the
repository. An optional per-post `subtitles` path supplies the SRT file when
`publishing.upload_caption_track` is enabled.

- YouTube defaults to `private`. Set `public` or `unlisted` explicitly when intended.
  A queued due time controls when the worker submits the upload; it is not a promise
  that platform processing will finish at that exact time.
- Instagram/Facebook require `privacy: "public"` explicitly and a direct public
  HTTPS `video_url`. There is no private Meta preview in this queue.
- Meta posts must reference a vertical Shorts episode. The current Facebook adapter
  uses a conservative 4–60-second contract; longer Reels are not enabled here.
- The YouTube title and base description come from the verified upload package.
  Campaign copy and an AI narration disclosure are appended/prepended as appropriate;
  existing source disclosures are retained. Shorts covers remain a platform-surface
  task; their portrait images are not submitted as long-form custom thumbnails.

## Python workflow

```python
from pathlib import Path
from daily_video_factory.config import load_settings
from daily_video_factory.social_campaign import SocialCampaignManager

root = Path.cwd()
manager = SocialCampaignManager(load_settings(root / "config/default.yaml"), root)
try:
    queued = manager.enqueue(root / "config/campaigns/my-campaign.json")
    preview = manager.run_due()  # Default: local/config checks; no platform calls.
    # After account setup and intentional authorization to publish:
    # result = manager.run_due(execute=True, limit=5)
finally:
    manager.close()
```

The CLI exposes these same operations; run `atlasforge --help` for its command list.
Scheduling a recurring worker does not create credentials or populate the queue.
Use a stable machine/service account, repository directory and configuration for
enqueue and execution. Preserve `output/social/queue.sqlite` and its receipt folder.
Tokens belong in local secrets/environment; signed URLs stay in the ignored local
database, never in status output. Campaign files containing private signed URLs
also belong under ignored `output/`, not Git.

## What execution verifies

Enqueue validates the entire campaign before inserting any new row. For production-batch sources, it hashes the
final video, publication package, thumbnail, voice declaration, editorial evidence,
referenced script/timing files, production manifest, post fields and realized
configuration. Execution reruns delivery verification and compares that fingerprint.
Changing approved inputs or settings blocks the post. An identical video cannot be
queued twice for the same account/platform, even through another campaign.
For those production-batch sources, editorial source dates must be real and no older than the configured
`research.max_official_source_age_days` at enqueue and execution; the existing
unqualified earnings/medical-claim checks also run on scripts and publication copy.

Dry runs are local readiness checks only and report `live_checks_pending: true`.
Execution also checks the authenticated YouTube channel ID, or the configured Meta
asset ID. Before Meta publishing, the hosted file must exactly match the local video
SHA-256 and size. The downloader checks public addresses, pins the checked IP while
preserving TLS hostname verification, refuses redirects, and bounds size/time.
Use a stable, immutable media URL: hash verification cannot stop a host from serving
different bytes to Meta later. A changed or renewed signed URL changes the approved
input and cannot silently replace a pending publication's source.

## States and recovery

| State | Meaning | Next action |
| --- | --- | --- |
| `pending` | Not due, or a bounded safe retry is scheduled | Run the worker later |
| `blocked` | Configuration, changed files, failed local checks, or retry budget needs attention | Fix the cause, then `retry_blocked(post_key)` |
| `uncertain` | A platform mutation may have succeeded | Reconcile externally; no automatic replay |
| `published` | Platform accepted the publication; YouTube may still be private/processing | Inspect the saved platform ID and privacy |

Attempts back off from five minutes to one hour and stop after eight attempts.
One worker lock protects execution; SQLite transactions protect queue changes.
Before an initial YouTube upload or caption insertion, the worker persists an
in-flight marker. A crash or ambiguous response becomes `uncertain`, so a second
video/caption is never blindly inserted. Confirmed video IDs are saved before
optional thumbnail/caption stages; a retryable thumbnail failure reuses the video.

The Meta adapter additionally checkpoints container/video IDs in JSON receipts;
see [Meta recovery](META_PUBLISHING.md). It can reconcile known IDs when explicitly
called with the same receipt, but the queue deliberately does not automatically
replay rows already marked `uncertain`. Unknown creation results require inspecting
the platform account. There is no "force retry" escape hatch. Do not delete the
database or receipts to resolve a failed upload.

`retry_blocked` cannot change an approved fingerprint or reset an uncertain/public
post. Restore the approved inputs when appropriate. A deliberately revised version
needs a new post ID; duplicate-media checks still apply. Deleting posts or changing
their publication metadata after delivery is not implemented in this queue.
