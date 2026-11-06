from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime, timedelta

import pytest

from daily_video_factory import social_campaign as module
from daily_video_factory.exceptions import ConfigurationError, ProviderFailed
from daily_video_factory.publishing.meta import (
    MetaConfig,
    MetaProcessingPending,
    MetaPublishUncertain,
)
from daily_video_factory.social_campaign import SocialCampaignManager

CHANNEL = "UC" + "a" * 22
NOW = datetime(2026, 11, 6, 12, tzinfo=UTC)


class FakeYouTube:
    def __init__(self):
        self.channel = CHANNEL
        self.authorized = True
        self.uploads = 0
        self.thumbnails = 0
        self.captions = 0
        self.fail_upload = False
        self.fail_thumbnail = False
        self.fail_caption = False
        self.account_reads = 0

    def authorization_status(self):
        return {"authorized": self.authorized}

    def authenticate(self, interactive=False):
        return self

    def channels(self):
        return self

    def list(self, **kwargs):
        return self

    def execute(self):
        self.account_reads += 1
        return {"items": [{"id": self.channel}]}

    def upload_video(self, *args, **kwargs):
        self.uploads += 1
        self.uploaded_metadata = args[1]
        if self.fail_upload:
            raise RuntimeError("token=never-echo-this")
        return "video-id-123"

    def upload_thumbnail(self, *args):
        self.thumbnails += 1
        if self.fail_thumbnail:
            raise ProviderFailed("token=never-echo-this")

    def upload_captions(self, *args):
        self.captions += 1
        if self.fail_caption:
            raise RuntimeError("token=never-echo-this")


class FakeMeta:
    config = MetaConfig(
        graph_version="v24.0",
        page_id="100",
        instagram_account_id="200",
        page_access_token="token=never-echo-this",
    )

    def __init__(self):
        self.calls = 0
        self.error = None

    def publish_instagram(self, *args):
        self.calls += 1
        if self.error:
            raise self.error
        return {"published": True, "media_id": "300"}

    def publish_facebook(self, *args, **kwargs):
        return self.publish_instagram(*args)

    def close(self):
        pass


@pytest.fixture
def queue(tmp_path, settings, monkeypatch):
    original_clock = module._clock
    monkeypatch.setattr(module, "_clock", lambda value=None: original_clock(value or NOW))
    root = tmp_path / "repository"
    rows = []
    for episode_id, format_name in (("short", "shorts"), ("long", "youtube")):
        project = root / "videos" / episode_id
        (project / "renders").mkdir(parents=True)
        (project / "renders/final.mp4").write_bytes(f"verified {episode_id} video bytes".encode())
        for name in ("thumbnail.png", "audio_request.json", "SCRIPT.md", "THUMBNAIL_COPY.txt"):
            (project / name).write_text(name)
        (project / "UPLOAD_PACKAGE.md").write_text(
            "## Title\nA useful story\n\n## Description\nIndependent education.\n\n## Hashtags\n#Atomy #Education #Story\n"
        )
        (project / "EDITORIAL.json").write_text(
            json.dumps(
                {
                    "script": "SCRIPT.md",
                    "thumbnail_copy": "THUMBNAIL_COPY.txt",
                    "packaging": {"thumbnail_text": "A STORY"},
                    "sources": [{"checked_on": "2026-11-01"}],
                }
            )
        )
        rows.append(
            {
                "id": episode_id,
                "project": f"videos/{episode_id}",
                "output": "renders/final.mp4",
                "thumbnail": "thumbnail.png",
                "upload_package": "UPLOAD_PACKAGE.md",
                "voice_manifest": "audio_request.json",
                "editorial_manifest": "EDITORIAL.json",
                "format": format_name,
            }
        )
    (root / "production.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "test",
                "expected_voice": "af_heart",
                "episodes": rows,
            }
        )
    )

    def verify(episode):
        assert episode.output.is_file()
        return {
            "metadata": {"title": "A useful story"},
            "duration_seconds": 25 if episode.format == "shorts" else 320,
        }

    monkeypatch.setattr(module, "verify_production_episode", verify)
    manager = SocialCampaignManager(settings, root)
    manager.meta.close()
    manager.youtube = FakeYouTube()
    manager.meta = FakeMeta()
    remote_checks = []
    monkeypatch.setattr(manager, "_verify_remote_media", lambda *args: remote_checks.append(args))
    yield manager, root, remote_checks
    manager.close()


def campaign(root, *, posts=None, campaign_id="launch"):
    if posts is None:
        posts = [
            {
                "id": "one",
                "episode_id": "short",
                "platform": "youtube",
                "account_id": CHANNEL,
                "publish_at": NOW.isoformat(),
                "caption": "A small choice can change a conversation.",
            }
        ]
    path = root / f"{campaign_id}.json"
    path.write_text(
        json.dumps(
            {"campaign_id": campaign_id, "production_manifest": "production.json", "posts": posts}
        )
    )
    return path


def meta_post(**overrides):
    return {
        "id": "ig",
        "episode_id": "short",
        "platform": "instagram",
        "account_id": "200",
        "publish_at": NOW.isoformat(),
        "caption": "An original story.",
        "privacy": "public",
        "video_url": "https://media.example.com/video.mp4?sig=never-echo-this",
        **overrides,
    }


def test_dry_run_has_no_remote_reads_uploads_or_queue_mutations(queue):
    manager, root, checks = queue
    before = manager.enqueue(campaign(root))
    result = manager.run_due(now=NOW)
    assert result[0]["readiness"] == "would_publish"
    assert result[0]["live_checks_pending"] is True
    assert manager.list_posts() == before
    assert manager.youtube.account_reads == manager.youtube.uploads == 0
    assert checks == []


def test_hold_survives_restart_and_excludes_manual_execute_without_resetting_receipts(queue):
    manager, root, checks = queue
    manager.enqueue(campaign(root, posts=[meta_post()]))
    manager._update(
        "launch:ig", attempts=3, next_attempt_at=(NOW + timedelta(hours=1)).isoformat(),
        receipt=json.dumps({"container_id": "existing-container"}), error="Safe retry status",
    )
    with manager._connect() as conn:
        before = dict(conn.execute("SELECT * FROM social_posts").fetchone())
    result = manager.hold_posts(["launch:ig"])
    assert result[0]["state"] == "held"
    assert "never-echo-this" not in json.dumps(result)
    assert "video_url" not in json.dumps(result)
    restarted = SocialCampaignManager(manager.settings, root, database=manager.database)
    restarted.meta.close()
    restarted.youtube = manager.youtube
    restarted.meta = manager.meta
    try:
        assert restarted.run_due(execute=True, now=NOW + timedelta(days=10)) == []
        assert restarted.list_posts()[0]["state"] == "held"
    finally:
        restarted.close()
    with manager._connect() as conn:
        held = dict(conn.execute("SELECT * FROM social_posts").fetchone())
    assert {k: v for k, v in held.items() if k not in {"state", "updated_at"}} == {
        k: v for k, v in before.items() if k not in {"state", "updated_at"}
    }
    assert manager.youtube.uploads == manager.meta.calls == 0
    assert checks == []


def test_hold_and_resume_are_idempotent_and_keep_backoff_and_approved_payload(queue, monkeypatch):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    retry_at = (NOW + timedelta(hours=1)).isoformat()
    manager._update("launch:one", attempts=3, next_attempt_at=retry_at)
    held = manager.hold_posts(["launch:one"])
    monkeypatch.setattr(module, "_clock", lambda value=None: value or NOW + timedelta(minutes=2))
    assert manager.hold_posts(["launch:one"]) == held
    resumed = manager.resume_posts(["launch:one"])
    assert resumed[0]["state"] == "pending"
    assert resumed[0]["attempts"] == 3
    assert resumed[0]["next_attempt_at"] == retry_at
    monkeypatch.setattr(module, "_clock", lambda value=None: value or NOW + timedelta(minutes=3))
    assert manager.resume_posts(["launch:one"]) == resumed
    assert manager.run_due(execute=True, now=NOW) == []
    assert manager.run_due(execute=True, now=NOW + timedelta(hours=2))[0]["state"] == "published"
    assert manager.youtube.uploads == 1


@pytest.mark.parametrize("state", ["published", "uploading", "uncertain", "blocked"])
@pytest.mark.parametrize("operation", ["hold_posts", "resume_posts"])
def test_hold_resume_reject_mixed_groups_atomically_and_preserve_terminal_rows(queue, state, operation):
    manager, root, _ = queue
    path = campaign(root)
    data = json.loads(path.read_text())
    data["posts"].append({**data["posts"][0], "id": "two", "episode_id": "long"})
    path.write_text(json.dumps(data))
    manager.enqueue(path)
    manager._update("launch:two", state=state, receipt='{"video_id":"keep-me"}')
    before = manager.list_posts()
    with pytest.raises(ConfigurationError, match="pending or held"):
        getattr(manager, operation)(["launch:one", "launch:two"])
    assert manager.list_posts() == before


@pytest.mark.parametrize("keys", [[], [""], [" "], ["launch:one", "launch:one"], ["launch:one", "missing"]])
def test_hold_refuses_invalid_selection_without_partial_mutation(queue, keys):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    before = manager.list_posts()
    with pytest.raises(ConfigurationError):
        manager.hold_posts(keys)
    assert manager.list_posts() == before


def test_hold_uses_worker_lock_and_does_not_claim_to_interrupt_an_active_worker(queue):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    before = manager.list_posts()
    with (
        module.portalocker.Lock(str(manager.database) + ".worker.lock", timeout=0),
        pytest.raises(module.portalocker.exceptions.LockException),
    ):
        manager.hold_posts(["launch:one"])
    assert manager.list_posts() == before


def test_reenqueue_and_retry_blocked_cannot_release_a_hold(queue):
    manager, root, _ = queue
    path = campaign(root)
    manager.enqueue(path)
    held = manager.hold_posts(["launch:one"])
    assert manager.enqueue(path) == held
    with pytest.raises(ConfigurationError):
        manager.retry_blocked("launch:one")
    assert manager.list_posts() == held


def test_schedule_requires_timezone_and_future_posts_wait(queue):
    manager, root, _ = queue
    path = campaign(root, posts=[meta_post(publish_at="2026-11-06T12:00:00")])
    with pytest.raises(ConfigurationError, match="timezone"):
        manager.enqueue(path)
    path = campaign(root, posts=[meta_post(publish_at=(NOW + timedelta(hours=1)).isoformat())])
    manager.enqueue(path)
    assert manager.run_due(execute=True, now=NOW) == []
    assert manager.meta.calls == 0


def test_enqueue_validates_all_posts_before_atomic_insert(queue):
    manager, root, _ = queue
    path = campaign(root, posts=[meta_post(), meta_post(id="invalid", episode_id="missing")])
    with pytest.raises(ConfigurationError):
        manager.enqueue(path)
    assert manager.list_posts() == []


def test_meta_default_private_cannot_be_published_accidentally(queue):
    manager, root, _ = queue
    post = meta_post()
    del post["privacy"]
    with pytest.raises(ConfigurationError, match="public"):
        manager.enqueue(campaign(root, posts=[post]))


def test_cross_campaign_dedupe_and_immutable_post_identity(queue):
    manager, root, _ = queue
    first = manager.enqueue(campaign(root))
    repeated = manager.enqueue(campaign(root, campaign_id="another"))
    assert repeated[0]["deduplicated"] is True
    assert repeated[0]["post_key"] == first[0]["post_key"]
    assert len(manager.list_posts()) == 1
    path = campaign(root)
    data = json.loads(path.read_text())
    data["posts"][0]["caption"] = "A changed caption."
    path.write_text(json.dumps(data))
    with pytest.raises(ConfigurationError, match="immutable"):
        manager.enqueue(path)


@pytest.mark.parametrize("change", ["video", "script", "settings"])
def test_changed_approved_inputs_block_publication(queue, change):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    if change == "video":
        (root / "videos/short/renders/final.mp4").write_bytes(b"different final render")
    elif change == "script":
        (root / "videos/short/SCRIPT.md").write_text("different script")
    else:
        manager.settings.channel.name = "A changed channel"
    result = manager.run_due(execute=True, now=NOW)
    assert result[0]["state"] == "blocked"
    assert manager.youtube.uploads == 0


def test_wrong_youtube_channel_blocks_before_upload(queue):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    manager.youtube.channel = "UC" + "b" * 22
    result = manager.run_due(execute=True, now=NOW)
    assert result[0]["state"] == "blocked"
    assert manager.youtube.uploads == 0
    manager.youtube.channel = CHANNEL
    manager.retry_blocked(result[0]["post_key"])
    assert manager.run_due(execute=True, now=NOW)[0]["state"] == "published"


def test_youtube_upload_once_and_private_default_retained(queue):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    result = manager.run_due(execute=True, now=NOW)
    assert result[0]["state"] == "published"
    assert result[0]["privacy"] == "private"
    assert manager.run_due(execute=True, now=NOW + timedelta(days=1)) == []
    assert manager.youtube.uploads == 1
    assert manager.youtube.thumbnails == 0  # Shorts cover is not a long-form thumbnail.


def test_youtube_description_appends_only_hashtags_missing_from_upload_copy(queue):
    manager, root, _ = queue
    (root / "videos/short/UPLOAD_PACKAGE.md").write_text(
        "## Title\nA useful story\n\n## Description\nIndependent education.\n\n"
        "#BizNex #InformedChoices #SourceCheck\n\n## Hashtags\n"
        "#BizNex #informedchoices #SourceCheck #Shorts\n"
    )
    manager.enqueue(campaign(root))
    assert manager.run_due(execute=True, now=NOW)[0]["state"] == "published"
    metadata = manager.youtube.uploaded_metadata
    for tag in ("#biznex", "#informedchoices", "#sourcecheck", "#shorts"):
        assert metadata.description.casefold().count(tag) == 1
    assert metadata.hashtags == ["#BizNex", "#InformedChoices", "#SourceCheck", "#Shorts"]
    assert "Independent education." in metadata.description
    assert metadata.description.endswith("Disclosure: AI-generated narration.")


def test_youtube_caption_hashtags_are_detected_without_matching_tag_prefixes(queue):
    manager, root, _ = queue
    path = campaign(root)
    payload = json.loads(path.read_text())
    payload["posts"][0]["caption"] = "A useful question. #ATOMY #Storyline"
    path.write_text(json.dumps(payload))
    manager.enqueue(path)
    assert manager.run_due(execute=True, now=NOW)[0]["state"] == "published"
    description = manager.youtube.uploaded_metadata.description
    assert description.casefold().count("#atomy") == 1
    assert "#Education #Story" in description  # #Storyline must not suppress #Story.
    assert "#Storyline" in description


def test_youtube_ambiguous_upload_is_not_automatically_replayed(queue):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    manager.youtube.fail_upload = True
    result = manager.run_due(execute=True, now=NOW)
    assert result[0]["state"] == "uncertain"
    assert "never-echo-this" not in json.dumps(result)
    manager.youtube.fail_upload = False
    assert manager.run_due(execute=True, now=NOW + timedelta(days=1)) == []
    with pytest.raises(ConfigurationError, match="uncertain"):
        manager.retry_blocked(result[0]["post_key"])
    assert manager.youtube.uploads == 1


def test_interrupted_process_marker_recovers_as_uncertain(queue):
    manager, root, _ = queue
    post = manager.enqueue(campaign(root))[0]
    manager._update(post["post_key"], state="uploading", receipt='{"upload_started":true}')
    recovered = manager.run_due(execute=True, now=NOW)
    assert recovered[0]["post_key"] == post["post_key"]
    assert recovered[0]["state"] == "uncertain"
    assert manager.list_posts()[0]["state"] == "uncertain"
    assert manager.youtube.uploads == 0
    assert manager.run_due(execute=True, now=NOW + timedelta(minutes=5)) == []


def test_optional_thumbnail_retry_reuses_saved_video_id(queue):
    manager, root, _ = queue
    path = campaign(root)
    payload = json.loads(path.read_text())
    payload["posts"][0]["episode_id"] = "long"
    path.write_text(json.dumps(payload))
    manager.enqueue(path)
    manager.youtube.fail_thumbnail = True
    first = manager.run_due(execute=True, now=NOW)
    assert first[0]["state"] == "pending"
    assert first[0]["video_id"] == "video-id-123"
    assert "never-echo-this" not in json.dumps(first)
    manager.youtube.fail_thumbnail = False
    second = manager.run_due(execute=True, now=NOW + timedelta(minutes=6))
    assert second[0]["state"] == "published"
    assert manager.youtube.uploads == 1
    assert manager.youtube.thumbnails == 2


def test_caption_timeout_keeps_video_id_and_marks_uncertain(queue):
    manager, root, _ = queue
    manager.settings.publishing.upload_caption_track = True
    path = campaign(root)
    payload = json.loads(path.read_text())
    payload["posts"][0]["subtitles"] = "captions.srt"
    (root / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nA story.\n")
    path.write_text(json.dumps(payload))
    manager.enqueue(path)
    manager.youtube.fail_caption = True
    result = manager.run_due(execute=True, now=NOW)
    assert result[0]["state"] == "uncertain"
    assert result[0]["video_id"] == "video-id-123"
    assert manager.run_due(execute=True, now=NOW + timedelta(days=1)) == []
    assert manager.youtube.uploads == manager.youtube.captions == 1


def test_meta_execution_verifies_remote_hash_and_hides_signed_url(queue):
    manager, root, checks = queue
    manager.enqueue(campaign(root, posts=[meta_post()]))
    result = manager.run_due(execute=True, now=NOW)
    assert result[0]["state"] == "published"
    assert (
        checks[0][2]
        == hashlib.sha256((root / "videos/short/renders/final.mp4").read_bytes()).hexdigest()
    )
    assert "never-echo-this" not in json.dumps(result)
    assert "never-echo-this" not in json.dumps(manager.list_posts())


def test_remote_hash_failure_prevents_meta_publish(queue, monkeypatch):
    manager, root, _ = queue
    manager.enqueue(campaign(root, posts=[meta_post()]))
    monkeypatch.setattr(
        manager,
        "_verify_remote_media",
        lambda *_: (_ for _ in ()).throw(ConfigurationError("Hosted bytes mismatch.")),
    )
    result = manager.run_due(execute=True, now=NOW)
    assert result[0]["state"] == "blocked"
    assert manager.meta.calls == 0


def test_meta_processing_retries_are_bounded_and_uncertainty_is_not_retried(queue):
    manager, root, _ = queue
    manager.max_attempts = 2
    manager.enqueue(campaign(root, posts=[meta_post()]))
    manager.meta.error = MetaProcessingPending("private provider response")
    assert manager.run_due(execute=True, now=NOW)[0]["state"] == "pending"
    assert manager.run_due(execute=True, now=NOW + timedelta(hours=2))[0]["state"] == "blocked"
    manager.retry_blocked("launch:ig")
    manager.meta.error = MetaPublishUncertain("private provider response")
    assert manager.run_due(execute=True, now=NOW + timedelta(hours=3))[0]["state"] == "uncertain"
    assert manager.run_due(execute=True, now=NOW + timedelta(hours=4)) == []


def test_hosted_media_private_dns_is_rejected_before_connect(queue, monkeypatch):
    manager, root, _ = queue
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ConfigurationError, match="public internet"):
        SocialCampaignManager._verify_remote_media(
            manager,
            "https://media.example.com/video",
            root / "videos/short/renders/final.mp4",
            "hash",
        )


@pytest.mark.parametrize("mode", ["match", "mismatch", "oversize", "redirect"])
def test_remote_media_stream_pins_checked_ip_and_compares_bytes(queue, monkeypatch, mode):
    manager, root, _ = queue
    video = root / "videos/short/renders/final.mp4"
    source = video.read_bytes()
    delivered = (
        source
        if mode in {"match", "redirect"}
        else b"x" * (len(source) + (1 if mode == "oversize" else 0))
    )
    recorded = {}

    class FakeSocket:
        def settimeout(self, value):
            recorded["timeout"] = value

        def close(self):
            pass

    class FakeContext:
        def wrap_socket(self, raw, server_hostname):
            recorded["tls_hostname"] = server_hostname
            return raw

    class FakeResponse:
        status = 302 if mode == "redirect" else 200
        done = False

        def read(self, amount):
            if self.done:
                return b""
            self.done = True
            return delivered

    class FakeConnection:
        def __init__(self, host, **kwargs):
            recorded["http_host"] = host

        def request(self, method, target, headers):
            recorded["request"] = (method, target, headers)

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    def connect(address, **kwargs):
        recorded["address"] = address
        return FakeSocket()

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    monkeypatch.setattr(socket, "create_connection", connect)
    monkeypatch.setattr(module.ssl, "create_default_context", FakeContext)
    monkeypatch.setattr(module.http.client, "HTTPSConnection", FakeConnection)

    def action():
        SocialCampaignManager._verify_remote_media(
            manager,
            "https://media.example.com/video?sig=private",
            video,
            hashlib.sha256(source).hexdigest(),
        )

    if mode == "match":
        action()
    else:
        with pytest.raises((ConfigurationError, ProviderFailed)):
            action()
    assert recorded["address"] == ("8.8.8.8", 443)
    assert recorded["tls_hostname"] == recorded["http_host"] == "media.example.com"
    assert recorded["request"][1] == "/video?sig=private"


def test_caption_policy_and_repository_traversal_are_rejected(queue):
    manager, root, _ = queue
    with pytest.raises(ConfigurationError):
        manager.enqueue(
            campaign(root, posts=[meta_post(caption="Earn $10000 per week guaranteed.")])
        )
    path = campaign(root)
    data = json.loads(path.read_text())
    data["production_manifest"] = "../production.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ConfigurationError, match="escapes"):
        manager.enqueue(path)


@pytest.mark.parametrize("checked_on", ["2026-01-01", "2026-12-01"])
def test_editorial_evidence_must_be_current_at_enqueue(queue, checked_on):
    manager, root, _ = queue
    path = root / "videos/short/EDITORIAL.json"
    data = json.loads(path.read_text())
    data["sources"][0]["checked_on"] = checked_on
    path.write_text(json.dumps(data))
    with pytest.raises(ConfigurationError, match="future-dated or stale"):
        manager.enqueue(campaign(root))
    assert manager.list_posts() == []


def test_evidence_that_expires_while_queued_blocks_execution(queue):
    manager, root, _ = queue
    manager.enqueue(campaign(root))
    result = manager.run_due(execute=True, now=NOW + timedelta(days=100))
    assert result[0]["state"] == "blocked"
    assert "stale" in result[0]["error"]
    assert manager.youtube.uploads == 0


def test_script_and_publication_metadata_cannot_bypass_claim_gate(queue):
    manager, root, _ = queue
    script = root / "videos/short/SCRIPT.md"
    script.write_text("This product cures diabetes.")
    with pytest.raises(ConfigurationError, match="prohibited medical claim"):
        manager.enqueue(campaign(root))
    script.write_text("No medical outcome is promised.")
    package = root / "videos/short/UPLOAD_PACKAGE.md"
    package.write_text(
        package.read_text().replace("Independent education.", "Earn $5000 per week.")
    )
    with pytest.raises(ConfigurationError, match="prohibited earnings promise"):
        manager.enqueue(campaign(root))
