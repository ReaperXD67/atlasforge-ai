# Instagram and Facebook Reels

AtlasForge includes original Python adapters for the official Meta publishing APIs.
They publish to a Facebook Page and its linked professional Instagram account using
Facebook Login and a Page token. They do not create accounts, passwords, or developer
apps. Live publication has not been verified with this project's accounts.

## Connect the accounts

1. Create or select the Page and link an Instagram business/creator account.
2. Configure a Meta developer app for those assets. Obtain the applicable publishing
   permissions and complete any review required by Meta for the app's access level.
3. Store the Page token in a local secret store/environment, never Git or a campaign
   manifest. Configure `META_PAGE_ACCESS_TOKEN`, `META_PAGE_ID`,
   `META_INSTAGRAM_ACCOUNT_ID`, and `META_GRAPH_VERSION`.
4. Set the Graph version explicitly to a supported version shown in your developer
   app. No moving "latest" version or guessed default is sent.

Instagram's Facebook Login route needs the Page association and the relevant
`instagram_basic`, `instagram_content_publish`, `pages_show_list`, and
`pages_read_engagement` grants. Check Facebook Page publishing access, including
`pages_manage_posts`, for the Page token. Token presence is only configuration;
`authorization_status()` deliberately does not claim it verified live permissions.
See [Meta's Instagram collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
and [Meta's Page/Reels guide](https://developers.facebook.com/docs/video-api/guides/reels-publishing/).

## Media and API behavior

Use a public HTTPS MP4 URL that Meta can fetch. It must remain accessible throughout
processing. A local path or login-protected preview URL cannot be used. The campaign
worker checks that downloaded bytes match the verified local video before publishing.
The adapter does not add commercial music or media rights. The existing production
delivery gates remain responsible for the local render and publishing package.

Instagram creates a container, waits for its processing status, then publishes that
container. Facebook starts a Reel, transfers the hosted asset, submits the finish
request, and waits for the publishing phase to complete. A ready video alone is not
reported as published. These sequences were checked against Meta's maintained
[Instagram Reels collection](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing)
and [Facebook Reels collection](https://www.postman.com/meta/facebook/documentation/r56bjfd/facebook-api?entity=request-23987686-a9ea20fe-d410-4804-8bbe-5cc5985e9443)
on 2026-11-06. Direct developer-doc retrieval was rate limited; the collections are
Meta-owned primary references. Their examples are not a guarantee of an individual
app's permissions or current account limits.

## Python API

```python
from pathlib import Path
from daily_video_factory.publishing.meta import MetaPublisher

publisher = MetaPublisher()  # Reads the four META_* environment variables.
try:
    receipt = publisher.publish_instagram(
        video_url, caption, Path("output/social/receipts/episode-instagram.json")
    )
    # Or: publisher.publish_facebook(video_url, caption, receipt_path, title="...")
finally:
    publisher.close()
```

Calling these methods is an actual publication request. Use the campaign worker's
default dry run to inspect a queue before enabling execution.

## Recovery and limits

Receipts bind account, caption, API version and media URL, persist remote IDs before
the next stage, and exclude tokens/media URLs. Reuse the same receipt and identical
input on every retry. The campaign queue also deduplicates the local video hash,
platform and account across campaigns. Separate arbitrary receipt paths do not
provide global deduplication by themselves.

- `MetaProcessingPending`: processing is still underway; retry the same receipt later.
- `MetaPublishUncertain`: the remote result may have succeeded. Reconciliation uses
  saved IDs; ambiguous mutations are never blindly repeated. If creation returned no
  ID, inspect the account/app externally before an operator resolves the record.
- `ProviderFailed`: a read failed or the platform rejected/expired processing.
- `ConfigurationError`: account configuration, URL, text, or receipt inputs need fixing.

Only reads retry automatically, with bounded attempts. Mutation errors are treated
conservatively even when a service error might be safely retryable. A process crash
after submission therefore cannot silently create a second public post. Polling and
network timeouts are bounded; automation resumes later rather than waiting forever.
Receipts should stay under ignored `output/`. Never delete an uncertain receipt to
force a retry. Tokens still require normal renewal/revocation management.

The adapter accepts captions up to 2,200 characters for Instagram; AtlasForge imposes
a conservative 5,000-character Facebook caption limit and 255-character title limit.
These text guards are application choices, not a complete platform spec validator.
Account creation, token refresh, comment/DM automation, paid ads, rights clearance,
and API review are outside these adapters. Unit tests use mock HTTP; this is not
evidence of delivered posts or audience reach.
