from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from daily_video_factory.config import Settings
from daily_video_factory.dashboard import create_app
from daily_video_factory.models import RunManifest, RunStatus
from daily_video_factory.state import RunStore


def test_dashboard_health_and_system_status(settings: Settings) -> None:
    client = TestClient(create_app(settings, Path("config/profiles")))

    assert client.get("/health").json() == {"status": "ok"}
    status = client.get("/api/system").json()
    assert status["width"] == 1920
    assert status["height"] == 1080
    assert status["profiles"] >= 3


def test_dashboard_serves_finished_run_artifacts(settings: Settings) -> None:
    output = settings.output_directory.resolve()
    run_root = output / "2026-08-15" / "test-run"
    video = run_root / "final" / "video.mp4"
    thumbnail = run_root / "thumbnails" / "thumbnail.jpg"
    video.parent.mkdir(parents=True)
    thumbnail.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    thumbnail.write_bytes(b"thumbnail")

    store = RunStore(output)
    store.save_manifest(
        RunManifest(
            run_id="test-run",
            publication_date=date(2026, 8, 15),
            status=RunStatus.ready,
            output_root=run_root,
            final_video=video,
            thumbnail=thumbnail,
        )
    )
    client = TestClient(create_app(settings, Path("config/profiles")))

    assert client.get("/api/runs/test-run/video").content == b"video"
    assert client.get("/api/runs/test-run/thumbnail").content == b"thumbnail"
    assert client.get("/api/runs/missing/video").status_code == 404
