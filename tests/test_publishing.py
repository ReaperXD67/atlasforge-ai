import json
import time
from datetime import date
from pathlib import Path

import pytest

from daily_video_factory.config import Settings
from daily_video_factory.models import RunManifest, RunStatus, VideoMetadata
from daily_video_factory.publishing.package import PublishManager, PublishSubmission
from daily_video_factory.publishing.youtube import YouTubePublisher
from daily_video_factory.state import RunStore


def test_publish_submission_rejects_oversized_tag_payload() -> None:
    with pytest.raises(ValueError, match="500-character"):
        PublishSubmission(
            title="Ready",
            description="Ready to publish",
            tags=[f"{index}-{'x' * 95}" for index in range(6)],
        )


class FakeYouTubePublisher:
    def __init__(self) -> None:
        self.video_uploads = 0
        self.thumbnail_uploads = 0
        self.caption_uploads = 0
        self.fail_thumbnail = True

    def authorization_status(self) -> dict[str, object]:
        return {
            "client_configured": True,
            "token_present": True,
            "authorized": True,
            "detail": "YouTube is connected and ready.",
        }

    def upload_video(self, *args, on_progress=None, **kwargs) -> str:
        self.video_uploads += 1
        if on_progress:
            on_progress(1.0)
        return "youtube-test-id"

    def update_video_metadata(self, *args, **kwargs) -> None:
        return None

    def upload_thumbnail(self, *args, **kwargs) -> None:
        self.thumbnail_uploads += 1
        if self.fail_thumbnail:
            raise RuntimeError("simulated thumbnail failure")

    def upload_captions(self, *args, **kwargs) -> None:
        self.caption_uploads += 1


def make_ready_run(settings: Settings) -> tuple[RunStore, dict[str, object], Path]:
    output = settings.output_directory.resolve()
    root = output / "2026-08-25-publish-test"
    video = root / "final" / "video.mp4"
    thumbnail = root / "thumbnails" / "thumbnail.jpg"
    subtitles = root / "subtitles" / "subtitles.srt"
    metadata_file = root / "metadata" / "metadata.json"
    report = root / "metadata" / "quality_report.json"
    for path in [video, thumbnail, subtitles, metadata_file, report]:
        path.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"finished video")
    thumbnail.write_bytes(b"finished thumbnail")
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nAtomy\n", encoding="utf-8")
    metadata = VideoMetadata(
        title="How to Join Atomy USA",
        description="A factual registration guide.",
        tags=["Atomy", "joining guide"],
        hashtags=["#Atomy"],
        chapters=[],
        thumbnail_text="JOIN ATOMY",
    )
    metadata_file.write_text(metadata.model_dump_json(), encoding="utf-8")
    report.write_text(json.dumps({"passed": True, "warnings": []}), encoding="utf-8")
    store = RunStore(output)
    manifest = RunManifest(
        run_id="publish-test",
        publication_date=date(2026, 8, 25),
        status=RunStatus.ready,
        topic="How to join Atomy",
        output_root=root,
        final_video=video,
        thumbnail=thumbnail,
    )
    store.save_manifest(manifest)
    return store, store.get_run("publish-test"), root


def wait_for_job(manager: PublishManager, publish_id: str):
    for _ in range(100):
        job = manager.get_job(publish_id)
        if job and job.state in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("publish job did not finish")


def test_publish_preview_contains_the_complete_package(settings: Settings) -> None:
    store, run, root = make_ready_run(settings)
    manager = PublishManager(settings, store)
    manager.publisher = FakeYouTubePublisher()

    preview = manager.preview(run, root)

    assert preview.can_publish is True
    assert preview.title == "How to Join Atomy USA"
    assert preview.captions_available is True
    assert preview.quality_state == "passed"
    assert preview.video_bytes > 0
    assert preview.thumbnail_bytes > 0


def test_publish_retry_reuses_video_after_thumbnail_failure(settings: Settings) -> None:
    store, run, root = make_ready_run(settings)
    manager = PublishManager(settings, store)
    fake = FakeYouTubePublisher()
    manager.publisher = fake
    submission = PublishSubmission(
        title="How to Join Atomy USA",
        description="A factual registration guide.",
        tags=["Atomy", "joining guide"],
    )

    first = wait_for_job(manager, manager.create(run, root, submission).publish_id)
    assert first.state == "failed"
    assert fake.video_uploads == 1
    receipt = json.loads((root / "metadata" / "youtube_publish.json").read_text())
    assert receipt["video_id"] == "youtube-test-id"

    fake.fail_thumbnail = False
    second = wait_for_job(manager, manager.create(run, root, submission).publish_id)

    assert second.state == "completed"
    assert fake.video_uploads == 1
    assert fake.thumbnail_uploads == 2
    assert fake.caption_uploads == 1
    published = store.get_run("publish-test")
    assert published["status"] == "published"
    assert published["youtube_video_id"] == "youtube-test-id"


def test_cli_publish_receipt_also_prevents_duplicate_video_uploads(
    settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    configured = settings.model_copy(deep=True)
    configured.publishing.upload_thumbnail = True
    configured.publishing.upload_caption_track = True
    video = tmp_path / "run" / "final" / "video.mp4"
    thumbnail = tmp_path / "run" / "thumbnails" / "thumbnail.jpg"
    subtitles = tmp_path / "run" / "subtitles" / "subtitles.srt"
    for path in [video, thumbnail, subtitles]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"artifact")
    metadata = VideoMetadata(
        title="Atomy guide",
        description="Description",
        tags=["Atomy"],
        hashtags=["#Atomy"],
        chapters=[],
        thumbnail_text="ATOMY",
    )
    publisher = YouTubePublisher(configured)
    calls = {"video": 0, "metadata": 0, "thumbnail": 0, "captions": 0}

    def upload_video(*args, **kwargs) -> str:
        calls["video"] += 1
        return "cli-video-id"

    def update_metadata(*args, **kwargs) -> None:
        calls["metadata"] += 1

    def upload_thumbnail(*args, **kwargs) -> None:
        calls["thumbnail"] += 1
        if calls["thumbnail"] == 1:
            raise RuntimeError("thumbnail failed")

    def upload_captions(*args, **kwargs) -> None:
        calls["captions"] += 1

    monkeypatch.setattr(publisher, "upload_video", upload_video)
    monkeypatch.setattr(publisher, "update_video_metadata", update_metadata)
    monkeypatch.setattr(publisher, "upload_thumbnail", upload_thumbnail)
    monkeypatch.setattr(publisher, "upload_captions", upload_captions)

    try:
        publisher.upload(video, thumbnail, subtitles, metadata, date(2026, 8, 25))
    except RuntimeError as exc:
        assert str(exc) == "thumbnail failed"
    else:
        raise AssertionError("The simulated accessory failure should escape")

    video_id = publisher.upload(video, thumbnail, subtitles, metadata, date(2026, 8, 25))

    assert video_id == "cli-video-id"
    assert calls == {"video": 1, "metadata": 1, "thumbnail": 2, "captions": 1}
    receipt = json.loads(
        (tmp_path / "run" / "metadata" / "youtube_publish.json").read_text()
    )
    assert receipt["package_completed"] is True
