import json

import httpx
import pytest

from daily_video_factory.exceptions import ConfigurationError, ProviderFailed
from daily_video_factory.publishing.meta import (
    MetaConfig,
    MetaProcessingPending,
    MetaPublisher,
    MetaPublishUncertain,
)

MEDIA = "https://media.example.com/episode.mp4?signature=private-media-signature"
CAPTION = "An original educational story. AI narration. Independent Atomy discussion."


def make_publisher(handler, **overrides):
    config = MetaConfig(
        **{
            "graph_version": "v24.0",
            "page_id": "100",
            "instagram_account_id": "200",
            "page_access_token": "secret-never-print",
            "poll_attempts": 2,
            "poll_interval_seconds": 0,
            "get_attempts": 2,
            **overrides,
        }
    )
    return MetaPublisher(
        config, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None
    )


def test_config_reports_configured_without_claiming_authentication():
    publisher = make_publisher(lambda _: pytest.fail("No network call expected"))
    assert publisher.authorization_status()["instagram"]["configured"] is True
    assert publisher.authorization_status()["authorization_verified"] is False
    assert "secret-never-print" not in repr(publisher.config)


@pytest.mark.parametrize(
    "url",
    [
        "http://media.example.com/a.mp4",
        "https://127.0.0.1/a",
        "https://localhost/a",
        "https://user:pass@media.example.com/a",
        "https://media.example.com/a#x",
    ],
)
def test_rejects_nonpublic_media_locations(url, tmp_path):
    publisher = make_publisher(lambda _: pytest.fail("No network call expected"))
    with pytest.raises(ConfigurationError, match="public HTTPS"):
        publisher.publish_instagram(url, CAPTION, tmp_path / "receipt.json")


def test_missing_token_is_a_configuration_error(tmp_path):
    publisher = make_publisher(
        lambda _: pytest.fail("No network call expected"), page_access_token=""
    )
    with pytest.raises(ConfigurationError, match="META_PAGE_ACCESS_TOKEN"):
        publisher.publish_facebook(MEDIA, CAPTION, tmp_path / "receipt.json")


def test_instagram_publishes_once_and_receipt_contains_no_secrets(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer secret-never-print"
        assert "access_token" not in str(request.url)
        if request.url.path.endswith("/media"):
            assert b"media_type=REELS" in request.content
            return httpx.Response(200, json={"id": "300"})
        if request.url.path.endswith("/300"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        assert request.url.path.endswith("/media_publish")
        return httpx.Response(200, json={"id": "400"})

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    first = publisher.publish_instagram(MEDIA, CAPTION, path)
    second = publisher.publish_instagram(MEDIA, CAPTION, path)
    assert first == second
    assert first["media_id"] == "400"
    assert len(calls) == 3
    assert "secret-never-print" not in path.read_text()
    assert "private-media-signature" not in path.read_text()
    assert MEDIA not in path.read_text()


def test_instagram_timeout_reconciles_container_without_second_publish(tmp_path):
    published = False
    post_count = 0

    def handle(request):
        nonlocal published, post_count
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "300"})
        if request.method == "GET":
            return httpx.Response(
                200, json={"status_code": "PUBLISHED" if published else "FINISHED"}
            )
        post_count += 1
        published = True
        raise httpx.ReadTimeout("request might have published", request=request)

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    with pytest.raises(MetaPublishUncertain):
        publisher.publish_instagram(MEDIA, CAPTION, path)
    receipt = publisher.publish_instagram(MEDIA, CAPTION, path)
    assert receipt["published"] is True
    assert "media_id" not in receipt  # A container confirms publication, not its media ID.
    assert post_count == 1


def test_instagram_uncertain_finished_status_does_not_repeat_mutation(tmp_path):
    posts = 0

    def handle(request):
        nonlocal posts
        if request.method == "GET":
            return httpx.Response(200, json={"status_code": "FINISHED"})
        posts += 1
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "300"})
        return httpx.Response(502, text="proxy failed secret-never-print")

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    for _ in range(2):
        with pytest.raises(MetaPublishUncertain):
            publisher.publish_instagram(MEDIA, CAPTION, path)
    assert posts == 2  # One create and one publish total, across both calls.


def test_instagram_processing_resumes_existing_container(tmp_path):
    ready = False
    creates = 0

    def handle(request):
        nonlocal creates
        if request.url.path.endswith("/media"):
            creates += 1
            return httpx.Response(200, json={"id": "300"})
        if request.method == "GET":
            return httpx.Response(200, json={"status_code": "FINISHED" if ready else "IN_PROGRESS"})
        return httpx.Response(200, json={"id": "400"})

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    with pytest.raises(MetaProcessingPending):
        publisher.publish_instagram(MEDIA, CAPTION, path)
    ready = True
    assert publisher.publish_instagram(MEDIA, CAPTION, path)["published"] is True
    assert creates == 1


def test_expired_instagram_container_cannot_be_recreated(tmp_path):
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, json={"id": "300"} if request.method == "POST" else {"status_code": "EXPIRED"}
        )

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    for _ in range(2):
        with pytest.raises(ProviderFailed):
            publisher.publish_instagram(MEDIA, CAPTION, path)
    assert calls == 2


def test_uncertain_creation_prevents_blind_replay_and_redacts_error(tmp_path):
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            400, json={"error": {"code": 190, "message": "secret-never-print " + MEDIA}}
        )

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    for _ in range(2):
        with pytest.raises(MetaPublishUncertain) as exc:
            publisher.publish_instagram(MEDIA, CAPTION, path)
        assert "secret-never-print" not in str(exc.value)
    assert calls == 1


def test_receipt_mismatch_and_corruption_cannot_create_another_post(tmp_path):
    path = tmp_path / "receipt.json"
    publisher = make_publisher(lambda _: pytest.fail("No network call expected"))
    path.write_text("not-json")
    with pytest.raises(ConfigurationError, match="unreadable"):
        publisher.publish_instagram(MEDIA, CAPTION, path)
    path.write_text(json.dumps({"fingerprint": "another-account-or-caption"}))
    with pytest.raises(ConfigurationError, match="does not match"):
        publisher.publish_instagram(MEDIA, CAPTION, path)


def test_facebook_finishes_then_requires_publishing_confirmation(tmp_path):
    calls = []
    complete = False

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": {
                        "video_status": "ready",
                        "publishing_phase": {"status": "complete" if complete else "in_progress"},
                    }
                },
            )
        if request.url.host == "rupload.facebook.com":
            assert request.headers["file_url"] == MEDIA
            assert request.headers["Authorization"] == "OAuth secret-never-print"
            return httpx.Response(200, json={"success": True})
        if b"upload_phase=start" in request.content:
            return httpx.Response(
                200,
                json={
                    "video_id": "300",
                    "upload_url": "https://rupload.facebook.com/video-upload/v24.0/300",
                },
            )
        assert b"video_state=PUBLISHED" in request.content
        return httpx.Response(200, json={"success": True})

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    with pytest.raises(MetaProcessingPending):
        publisher.publish_facebook(MEDIA, CAPTION, path, title="A story")
    assert json.loads(path.read_text())["published"] is False
    complete = True
    result = publisher.publish_facebook(MEDIA, CAPTION, path, title="A story")
    assert result["published"] is True
    assert len([request for request in calls if request.method == "POST"]) == 3
    assert publisher.publish_facebook(MEDIA, CAPTION, path, title="A story") == result


def test_facebook_refuses_remote_upload_host_that_could_steal_token(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200, json={"video_id": "300", "upload_url": "https://evil.example/upload"}
        )

    publisher = make_publisher(handle)
    with pytest.raises(MetaPublishUncertain):
        publisher.publish_facebook(MEDIA, CAPTION, tmp_path / "receipt.json")
    assert len(calls) == 1


def test_facebook_lost_transfer_response_reconciles_without_second_upload(tmp_path):
    uploads = 0

    def handle(request):
        nonlocal uploads
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": {
                        "uploading_phase": {"status": "complete"},
                        "publishing_phase": {"status": "complete"},
                    }
                },
            )
        if request.url.host == "rupload.facebook.com":
            uploads += 1
            raise httpx.ReadTimeout("uncertain", request=request)
        if b"upload_phase=start" in request.content:
            return httpx.Response(
                200,
                json={
                    "video_id": "300",
                    "upload_url": "https://rupload.facebook.com/video-upload/v24.0/300",
                },
            )
        return httpx.Response(200, json={"success": True})

    publisher = make_publisher(handle)
    path = tmp_path / "receipt.json"
    with pytest.raises(MetaPublishUncertain):
        publisher.publish_facebook(MEDIA, CAPTION, path)
    assert publisher.publish_facebook(MEDIA, CAPTION, path)["published"] is True
    assert uploads == 1


def test_only_transient_reads_are_retried(tmp_path):
    reads = 0

    def handle(request):
        nonlocal reads
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "300"})
        if request.method == "GET":
            reads += 1
            if reads == 1:
                return httpx.Response(429, json={"error": {"code": 4}})
            return httpx.Response(200, json={"status_code": "FINISHED"})
        return httpx.Response(200, json={"id": "400"})

    publisher = make_publisher(handle)
    assert (
        publisher.publish_instagram(MEDIA, CAPTION, tmp_path / "receipt.json")["published"] is True
    )
    assert reads == 2


def test_graph_read_errors_do_not_echo_token_or_response(tmp_path):
    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"id": "300"})
        return httpx.Response(401, json={"error": {"code": 190, "message": "secret-never-print"}})

    publisher = make_publisher(handle)
    with pytest.raises(ProviderFailed) as exc:
        publisher.publish_instagram(MEDIA, CAPTION, tmp_path / "receipt.json")
    assert "API code 190" in str(exc.value)
    assert "secret-never-print" not in str(exc.value)
