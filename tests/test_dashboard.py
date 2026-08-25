import json
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
    assert "fal_wan_s2v" in status
    male = client.get("/api/assets/performers/male")
    female = client.get("/api/assets/performers/female")
    assert male.status_code == 200 and male.headers["content-type"] == "image/png"
    assert female.status_code == 200 and female.headers["content-type"] == "image/png"
    assert client.get("/api/assets/performers/other").status_code == 404


def test_dashboard_serves_finished_run_artifacts(settings: Settings) -> None:
    output = settings.output_directory.resolve()
    run_root = output / "2026-08-15" / "test-run"
    video = run_root / "final" / "video.mp4"
    thumbnail = run_root / "thumbnails" / "thumbnail.jpg"
    scene = run_root / "scenes" / "scene_001.jpg"
    scene_index = run_root / "scenes" / "images.json"
    video.parent.mkdir(parents=True)
    thumbnail.parent.mkdir(parents=True)
    scene.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    thumbnail.write_bytes(b"thumbnail")
    scene.write_bytes(b"scene")
    scene_index.write_text(
        json.dumps([{"scene": 1, "provider": "test", "path": str(scene)}]),
        encoding="utf-8",
    )

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

    video_response = client.get("/api/runs/test-run/video")
    assert video_response.content == b"video"
    assert video_response.headers["accept-ranges"] == "bytes"
    partial = client.get("/api/runs/test-run/video", headers={"Range": "bytes=1-2"})
    assert partial.status_code == 206
    assert partial.content == b"id"
    assert client.get("/api/runs/test-run/thumbnail").content == b"thumbnail"
    assert client.get("/api/runs/test-run/scenes/1").content == b"scene"
    assert client.get("/api/runs/test-run/scenes/2").status_code == 404
    assert client.get("/api/runs/missing/video").status_code == 404


def test_dashboard_exposes_publish_package_without_uploading(settings: Settings) -> None:
    output = settings.output_directory.resolve()
    run_root = output / "2026-08-15-publish-preview"
    video = run_root / "final" / "video.mp4"
    thumbnail = run_root / "thumbnails" / "thumbnail.jpg"
    metadata = run_root / "metadata" / "metadata.json"
    quality = run_root / "metadata" / "quality_report.json"
    video.parent.mkdir(parents=True)
    thumbnail.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    thumbnail.write_bytes(b"thumbnail")
    metadata.write_text(
        json.dumps(
            {
                "title": "Upload-ready Atomy guide",
                "description": "Description",
                "tags": ["Atomy"],
                "hashtags": ["#Atomy"],
                "chapters": [],
                "thumbnail_text": "ATOMY GUIDE",
                "category_id": "27",
            }
        ),
        encoding="utf-8",
    )
    quality.write_text(json.dumps({"passed": True}), encoding="utf-8")
    RunStore(output).save_manifest(
        RunManifest(
            run_id="publish-preview",
            publication_date=date(2026, 8, 15),
            status=RunStatus.ready,
            output_root=run_root,
            final_video=video,
            thumbnail=thumbnail,
        )
    )

    response = TestClient(create_app(settings, Path("config/profiles"))).get(
        "/api/runs/publish-preview/publish-package"
    )

    assert response.status_code == 200
    package = response.json()
    assert package["title"] == "Upload-ready Atomy guide"
    assert package["quality_state"] == "passed"
    assert package["video_bytes"] == 5
    assert package["can_publish"] is False
    assert "YouTube OAuth client is not configured" in package["blockers"]


def test_dashboard_maps_host_paths_to_the_current_output_mount(settings: Settings) -> None:
    output = settings.output_directory.resolve()
    run_root = output / "2026-08-15-foreign-run"
    video = run_root / "final" / "video.mp4"
    report = run_root / "quality" / "ai_clip_report.json"
    video.parent.mkdir(parents=True)
    report.parent.mkdir(parents=True)
    video.write_bytes(b"portable-video")
    report.write_text(
        json.dumps({"decision": "accepted", "selected_score": 0.91}),
        encoding="utf-8",
    )
    store = RunStore(output)
    store.save_manifest(
        RunManifest(
            run_id="foreign-run",
            publication_date=date(2026, 8, 15),
            status=RunStatus.ready,
            output_root=Path(r"C:\host\atlasforge\output\2026-08-15-foreign-run"),
            final_video=Path(r"C:\host\atlasforge\output\2026-08-15-foreign-run\final\video.mp4"),
        )
    )
    client = TestClient(create_app(settings, Path("config/profiles")))

    payload = client.get("/api/runs/foreign-run").json()
    assert payload["ai_quality"]["decision"] == "accepted"
    assert client.get("/api/runs/foreign-run/video").content == b"portable-video"
