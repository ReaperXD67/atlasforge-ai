# Daily BizNex operator

**Paused by the owner on 9 November 2026.** Work only when explicitly requested.
Do not start daily production, posting, analytics checks or background workers.
The recurring Codex automation is PAUSED. Each explicit request authorizes one
reviewed episode across the requested destinations; it does not resume future
scheduled runs. The operating procedure below is for requested runs.

## Preserve the right state

- Use `output/social/biznex-stories.queue.sqlite` for new verified story campaigns.
- Keep all five rejected pilot follow-ups **held** in
  `output/social/biznex-first-six.queue.sqlite`. Do not resume, duplicate, re-date or
  re-enqueue them to bypass the hold. The first public pilot remains intact.
- The Yes Machine is already public on [YouTube](https://www.youtube.com/shorts/Dc4aBDQfQ9w),
  [Instagram](https://www.instagram.com/p/Dfch-tjKvp7/) and
  [Facebook](https://www.facebook.com/reel/1759901191770877). Its uploaded local SHA256
  is `ccd05da3eca962865eb92a197d92c5feb2f1a5df9ab0d79442ddb32b3060cc43`.
  All three publications were adopted into the stories queue with exact IDs and
  verification methods. Repeated enqueue preserved their published states; an
  execute run returned no eligible jobs. Never upload this film again.
- Accounts: YouTube `UCEoGrcisSgAFiu0EkBuDq8w`; Instagram browser profile
  `@biznex.stories`; Facebook browser Page `61595985973734` / BizNex. The separate
  Meta business asset `1484822874707996` is not a substitute browser identity.
- Target **one new episode per IST calendar date**, syndicated to all three accounts.
  Inspect dates and actual receipts before planning another episode. The queue
  dedupes video bytes per platform/account within one database; a daily episode
  cap and cross-database deduplication remain operator responsibilities.

## Each daily run

1. Read [the automation guide](SOCIAL_AUTOMATION.md),
   [the editorial plan](BIZNEX_EDITORIAL_PLAN.md), previous local operator reports
   and repository instructions. Inspect Git status and preserve unrelated work.
   Run `social doctor` and `social status` for both databases above. Confirm the old
   five remain held. Existing claimed, uncertain or published records require
   reconciliation, never a fresh upload.
2. Import only real normalized observations from `output/social/inbox/` through
   `social import-metrics`. Retain missing values and use predeclared metrics.
   Improve a concrete hook, story or packaging choice from the observations;
   never invent views, retention, signups or audience feedback.
3. Author a new project for today's episode. Use current primary sources when
   making Atomy product, price, availability or business-plan statements; record
   market and observation date and apply `POLICY.md`. Prefer an original fictional
   human problem, causal progression and a practical payoff. Keep visible
   fiction/synthetic disclosure and independent-community context. Do not imply
   health results, earnings, a real customer testimonial or official endorsement.
4. Use [the story pipeline](NEXT_STORY_PIPELINE.md): authored brief and shot meanings,
   complete expressive voice thoughts, measured words, original procedural/3D/SVG
   scenes and deliberate sound design. The Yes Machine world is a reusable technique,
   not a universal story generator; do not reskin its exact sequence every day.
   Avoid new image/video models and paid services. Respect licenses and voice rights;
   do not impersonate a real person. Render and inspect the actual film.
5. Require fresh `renders/final.report.json`, encoded audio QA, decoded frame coverage,
   and a matching `DELIVERY_REVIEW.json` with no blocking sampled visual findings.
   Listen for intelligibility, expressive fit and sound balance when possible;
   report any unperformed review honestly. Technical or transcript checks do not
   establish natural acting or creative quality. Fix material defects before release.
6. Create a new `story_project` campaign with explicit titles, complete captions,
   real account IDs, public privacy, exact SRT and timezone-aware dates. Follow
   [the verified campaign contract](SOCIAL_CAMPAIGNS.md). Reuse the stories database.
   Enqueue and dry-run; current files and publishing settings must match their
   immutable fingerprint at execution. Do not alter queued inputs to reuse a job ID.
   For the 09:00 heartbeat, make today's reviewed episode due when it is ready;
   a future clock time needs an available worker or another scheduled run.
7. Publish YouTube through the authorized API queue after live channel matching.
   Read back processing, visibility and the uploaded subtitle track before reporting
   the release as verified; an upload ID alone does not prove processing succeeded.
   Meta API setup remains incomplete; use the signed-in browser while that access
   remains available. Run `claim-browser` before a browser upload, verify the active
   account, select the exact verified MP4 once, retain prepared disclosure and the
   appropriate AI label, then observe public success and its permalink. Record
   exact file/account/title/URL and hashed evidence using `record-observed`.
   A sharing spinner is not success: inspect that pending post instead of uploading
   another copy. A claimed browser job is excluded from automatic workers.
8. Preserve confirmed remote IDs and evidence. The queue can record an independently
   confirmed earlier publication without uploading again. API readback and browser
   observation remain distinct receipt methods. Do not report browser actions as
   working Meta API automation. Never delete uncertainty markers or release held
   jobs to force progress.
9. If login, OAuth, review or platform availability blocks a destination, record the
   concrete blocker once in `output/social/operator-status.json`, retain the completed
   local delivery and continue useful authorized work. Do not repeatedly request
   the same credentials. YouTube's OAuth app remains in External Testing; its refresh
   token may expire seven days after authorization. Stop on authentication failure
   and report the actual recovery need. Secrets never enter Git or reports.
10. Save a concise dated report separating exports, verified live posts, observed
    metrics and proposed changes. Update affected README/docs for significant
    delivered capabilities, run relevant tests and use the authorized Git workflow
    for reviewed source/docs. Keep private media, credentials and platform evidence
    in ignored storage. Do not message users, answer DMs, buy ads or change account
    ownership under this publishing authorization.

Success means useful original content, correct publication and evidence-informed
iteration. No automation promises virality, revenue, Atomy signups or repository stars.
