# BizNex: measured social growth

Research checked **6 November 2026**. This is an experiment plan, not evidence that a new
channel or a particular edit will gain reach. No account analytics were supplied for this
research, so the cause of previous videos' low reach is still unknown.

## What the research changes

YouTube describes Shorts distribution as a combination of viewer fit, viewing choice,
watch duration, percentage viewed and satisfaction. Topic demand, competing videos and
seasonality also affect reach; there is no required minimum posting cadence. The operating
decision is to test clear viewer problems and useful payoffs, rather than optimize for
upload volume alone. [YouTube search and discovery guidance](https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en).

Meta's Facebook guidance prioritizes original production and meaningful creative additions;
minor caption, border or speed edits to somebody else's video do not establish originality.
Use reference reels to study storytelling, then create original scripts, performances and
visuals. [Meta originality guidance, March 2026](https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/).

Instagram provides account-specific best-practice advice in its professional dashboard.
Review that advice and the account's recommendation eligibility alongside exported results;
do not assume a universal posting time or hashtag formula.
[Instagram professional dashboard guidance](https://about.fb.com/news/2024/10/best-practices-education-hub-creators-instagram/).

## Positioning and account copy

Keep **BizNex** as the display name, with the editorial line **“Better questions. Clearer
choices.”** Handle candidates, in order: `biznexexplains`, `biznexnotes`, `biznexguide`.
These are proposed names; availability and account creation must be verified separately.

Suggested short bio:

> Everyday product decisions, explained with evidence. Atomy guides without the hype.
> Independent education; not Atomy's official account.

Suggested YouTube description:

> BizNex makes complicated product and membership decisions easier to understand.
> Expect original short stories, practical checks and source-led Atomy explainers.
> We separate consumer choices from business opportunities and explain limitations.
> This is an independent educational channel, not an official Atomy corporate channel.
> Relevant commercial relationships and AI-produced media are disclosed in each video's details.

Use the same original avatar and consistent name across the YouTube channel, Instagram
professional account and Facebook Page. Account owners retain recovery access; publishing
uses revocable platform authorization. Do not invent a personal identity for Facebook.
Store passwords and recovery codes in a password manager, never in the repository or a
public publishing manifest. These recommendations do not represent created accounts.

## Market and facts

The existing profiles and source pack target **Atomy USA, English-speaking adults**. The
user's timezone is not evidence of the intended sales market. Keep U.S. facts labeled until
an intended market is selected and its official sources are researched.

The U.S. membership guide distinguishes consumer and distributor registration and says a
sponsor is needed. It also describes U.S. phone verification, with additional distributor
information requirements. Those are U.S. registration details, not a worldwide promise.
[Atomy USA registration guide](https://us.atomy.com/cst/userGuide/24100000001691).

Use the [editorial source workflow](EDITORIAL_SOURCES.md) for current product, membership
and compensation statements. Do not treat this research note as a refresh of the pipeline's
dated summaries. Keep claims within [POLICY.md](../POLICY.md): no invented results, earnings
promises, medical claims or fictional testimonials presented as real.

## A 30-day test

The machine-readable [experiment plan](../config/social/experiment-plan.json) is a planning
input, not a deployed schedule. Start Day 1 only after accounts and publishing authorization
work. The plan uses twelve original Shorts across thirty days, with separate measurements
for each platform; it does not require twelve unrelated content concepts.

| Days | Action | Decision/evidence |
| --- | --- | --- |
| 1–3 | Complete account ownership, bios, sources, media rights and one private upload test | Rendering and publishing receipts; no reach claim |
| 4–15 | Publish six original episodes, alternating three question-first and three evidence-first openings | Match audience, topic family, length band and posting-time band |
| 16 | Compare each platform's first 72 hours, then inspect retention curves and substantive comments | Three videos per variant and at least 1,000 observed views per variant are minimum workflow gates, not significance tests |
| 17–27 | Repeat both openings on six fresh but comparable topics | Seek repeatable direction rather than reproducing the highest-view clip |
| 28–30 | Compare matured 72-hour results and seven-day checkpoints separately | Keep, refine or retire the hypothesis; write the next batch from audience questions |

Predeclare `average_percentage_viewed` as the primary YouTube hook metric; import the exact
platform measure. For an Instagram/Facebook cohort where that metric is unavailable, use
`share_rate` as a separately declared hypothesis before observing outcomes. Keep shares,
saves and qualified site events as secondary context, not post-hoc ways to declare success.

Do not duplicate the same video repeatedly to manufacture an A/B test. These are matched
observational batches; topic, timing, audience selection and platform distribution remain
confounders. Change one creative factor per batch. A directional lead earns a replication,
not an automatic conclusion or a paid advertising budget increase.

## Creative brief for each episode

Lead with a concrete decision and show the object, document or action immediately. Resolve
one tension within 20–35 seconds: question, visual evidence, consequence, useful payoff.
Examples: “A shopping account or a business decision?”, “The step you cannot skip in this
U.S. signup flow”, or “What would actually change your product choice?” Each needs a new
verified source detail, demonstrated comparison or original story—not a renamed template.

Use narration with intentional pauses, readable captions anchored to speech and a visual
change only when the thought changes. Keep dialogue and quiet moments intelligible. An
emotional story must be labeled as fiction if invented; a demonstrator must not imply a
medical result. Atomy appears when it answers the topic, without a forced recruitment turn.

The ending delivers the promised decision tool first. A low-pressure next step can point
to the source notes or a relevant explainer. Define a “qualified click” before tracking:
for example, a tagged visit that opens the source/decision checklist. It is not a sale,
signup or income outcome. Use only aggregate event counts, with no personal data in imports.

## Import and compare real observations

`atlasforge social` and `SocialAnalyticsStore` provide CLI and Python workflows. They accept normalized JSON or CSV;
native platform export headers must be mapped to the schema below. It does **not** log into
accounts or retrieve live analytics. The existing YouTube publishing OAuth scopes do not
include `yt-analytics.readonly`; a future read-only importer requires that separate consent.
[YouTube Analytics authorization](https://developers.google.com/youtube/reporting/guides/authorization).

```powershell
atlasforge social import-metrics --source output/social/observations.csv
atlasforge social report --primary-metric average_percentage_viewed --output output/social/report.json
```

Both commands use `output/social/analytics.sqlite` by default. Pass `--database` to both
when using a different store. Queue and account commands are in the
[social automation guide](SOCIAL_AUTOMATION.md).

```python
from pathlib import Path
from daily_video_factory.social_analytics import SocialAnalyticsStore

store = SocialAnalyticsStore(Path("output/social/analytics.sqlite"))
print(store.ingest_file(Path("output/social/observations.csv")))
report = store.report(
    window_hours=72,
    tolerance_hours=12,
    min_videos=3,
    min_views=1000,
    primary_metric="average_percentage_viewed",
)
```

Required CSV columns (the example is illustrative, not measured performance):

```csv
platform,account_id,video_id,experiment_id,variant,published_at,observed_at,views,average_percentage_viewed,shares
youtube,channel-id,video-id,opening-01,question-first,2026-11-01T12:00:00Z,2026-11-04T12:00:00Z,500,76.5,8
```

JSON accepts an array of the same objects or `{ "observations": [...] }`.

| Field | Meaning |
| --- | --- |
| `platform` | `youtube`, `instagram`, or `facebook` |
| `account_id`, `video_id` | Actual platform identifiers; never tokens |
| `experiment_id`, `variant` | Fixed assignment made before publication |
| `published_at`, `observed_at` | ISO 8601 timestamps with timezone; measurements are cumulative since publication |
| `views` | Nonnegative total platform views at the checkpoint |
| `format` | Optional `short` (default) or `long`; never pooled |
| `impressions`, `engaged_views`, `completed_views` | Optional distinct counts; completion must use the same view denominator |
| `shares`, `saves`, `qualified_clicks` | Optional counts; blank means unknown, zero means measured zero |
| `duration_seconds`, `average_watch_seconds` | Optional seconds, copied from the corresponding platform measure |
| `average_percentage_viewed` | Optional percentage such as `76.5`, allowed above 100 for replays |
| `topic`, `hook` | Optional editorial labels returned with variant summaries |

YouTube Shorts average duration and percentage viewed use engaged views and their watch
time. They are not “total watch time divided by every play.” Import the explicit values;
the module deliberately does not infer them from incompatible counters. Impressions are
also not interchangeable with feed exposure. [YouTube metric definitions](https://support.google.com/youtube/answer/12220281?co=GENIE.Platform%3DDesktop&hl=en).

Imports validate all rows before committing, reject experiment reassignment and replace
corrected observations with the same video/timestamp. Reimporting an unchanged export is a
no-op. Multiple cumulative snapshots remain in the database; reports select the nearest
checkpoint once per video and never sum its repeated lifetime counts.

Reports separate platform, account, experiment and format. They compare per-video medians,
preserve unknown values, require primary-metric coverage for all included videos and refuse
to pick a candidate from sparse samples. `directional_signal` recommends a new replication;
`insufficient_evidence`, `needs_comparison` and `no_clear_difference` do not select a winner.
No observations produces `no_observations`; unavailable checkpoints produce
`no_matching_checkpoint`. Thresholds and medians are practical triage, not causal inference.

Verify with `python -m pytest tests/test_social_analytics.py`. Live account reach, recommendation
eligibility, leads and sales remain unverified until actual account measurements are imported.
