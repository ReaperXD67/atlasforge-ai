"""Archive/privacy contracts with verified-report stubs; no encoding or providers."""
from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package_production_batch.py"


@pytest.fixture
def packaging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    loader = importlib.util.spec_from_file_location("production_packaging_under_test", _SCRIPT)
    assert loader is not None and loader.loader is not None
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(module, "__file__", str(root / "scripts" / "package_production_batch.py"))
    episodes = []
    duration_by_id: dict[str, float] = {}
    for number, duration in enumerate([25.167, 26.633, 27.4, 332.7, 346.366], 1):
        episode_id = f"episode-{number}"
        format_name = "shorts" if number <= 3 else "youtube"
        project = root / "videos" / episode_id
        (project / "renders").mkdir(parents=True)
        (project / "assets" / "thumbnails").mkdir(parents=True)
        video = project / "renders" / "final.mp4"
        thumbnail = project / "assets" / "thumbnails" / "thumbnail.png"
        upload = project / "UPLOAD_PACKAGE.md"
        video.write_bytes(f"verified-video-{number}".encode())
        thumbnail.write_bytes(f"verified-thumbnail-{number}".encode())
        upload.write_text(
            f"## Title\nUseful episode {number}\n\n## Description\nA clear fictional example.\n\n"
            "## Hashtags\n#Business #BizNex #Learning\n",
            encoding="utf-8",
        )
        # Deliberately disagree with the verified media report: packaging must
        # consume observed delivery duration, not this planning/cache value.
        (project / "audio_meta.json").write_text('{"total_duration_s":999}', encoding="utf-8")
        episodes.append(SimpleNamespace(id=episode_id, format=format_name, project=project,
                                        output=video, thumbnail=thumbnail, upload_package=upload))
        duration_by_id[episode_id] = duration
    manifest_path = root / "config" / "batch.production.json"
    manifest = SimpleNamespace(batch_id="package-test", episodes=tuple(episodes))
    private_path = str(root / "private" / "PRODUCTION_BATCH_REPORT.json")
    report = {
        "status": "verified",
        "manifest": str(manifest_path),
        "report_path": private_path,
        "diagnostic_token": "do-not-publish-this-token",
        "episodes": [
            {"id": episode.id, "status": "verified", "output": str(episode.output),
             "report": {"duration_seconds": duration_by_id[episode.id]}}
            for episode in episodes
        ],
    }
    calls: list[tuple[Path, dict[str, Any]]] = []

    def resume_report(path: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append((path, kwargs))
        return report

    monkeypatch.setattr(module, "load_production_batch_manifest", lambda _: manifest)
    monkeypatch.setattr(module, "run_production_batch", resume_report)
    audio_quality = {"status": "verified", "episodes": [
        {"id": episode.id, "status": "verified", "integrated_lufs": -14.21, "true_peak_dbtp": -2.0}
        for episode in episodes
    ]}
    monkeypatch.setattr(module, "check_production_audio", lambda _: audio_quality)
    monkeypatch.setattr(sys, "argv", [str(_SCRIPT), "--manifest", str(manifest_path)])
    out = root / "output" / manifest.batch_id
    return SimpleNamespace(module=module, root=root, manifest=manifest, manifest_path=manifest_path,
                           report=report, calls=calls, out=out, duration_by_id=duration_by_id,
                           audio_quality=audio_quality,
                           archive=out / "biznex-three-shorts-two-videos.zip")


def test_verified_package_contains_exactly_five_delivery_triples_and_aggregate_files(
    packaging: SimpleNamespace,
) -> None:
    packaging.module.main()
    expected = {"UPLOAD_ALL.md", "DELIVERY_SUMMARY.json"}
    for episode in packaging.manifest.episodes:
        expected.update({f"{episode.id}/final.mp4", f"{episode.id}/thumbnail.png",
                         f"{episode.id}/UPLOAD_PACKAGE.md"})
    with zipfile.ZipFile(packaging.archive) as archive:
        assert len(archive.namelist()) == 17
        assert set(archive.namelist()) == expected
        assert all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
                   for name in archive.namelist())
        for episode in packaging.manifest.episodes:
            assert archive.read(f"{episode.id}/final.mp4") == episode.output.read_bytes()
            assert archive.read(f"{episode.id}/thumbnail.png") == episode.thumbnail.read_bytes()
            assert archive.read(f"{episode.id}/UPLOAD_PACKAGE.md") == episode.upload_package.read_bytes()
        assert archive.read("UPLOAD_ALL.md") == (packaging.out / "UPLOAD_ALL.md").read_bytes()
        assert archive.read("DELIVERY_SUMMARY.json") == (packaging.out / "DELIVERY_SUMMARY.json").read_bytes()


def test_summary_uses_actual_verified_duration_not_audio_plan_and_keeps_relative_paths(
    packaging: SimpleNamespace,
) -> None:
    packaging.module.main()
    summary = json.loads((packaging.out / "DELIVERY_SUMMARY.json").read_text(encoding="utf-8"))
    assert summary["batch_id"] == "package-test"
    assert summary["guaranteed_views"] is False
    assert summary["uploaded_to_youtube"] is False
    assert len(summary["episodes"]) == 5
    for episode in summary["episodes"]:
        assert episode["duration_seconds"] == packaging.duration_by_id[episode["id"]]
        assert episode["duration_seconds"] != 999
        assert episode["voice"] == "af_heart"
        assert episode["delivery_passed"] is True
        assert episode["video"] == f"{episode['id']}/final.mp4"
        assert episode["thumbnail"] == f"{episode['id']}/thumbnail.png"
        assert episode["audio_quality"] == {"integrated_lufs": -14.21, "true_peak_dbtp": -2.0}
    upload = (packaging.out / "UPLOAD_ALL.md").read_text(encoding="utf-8")
    assert "episode-4 (youtube, 332.7s)" in upload
    assert "999" not in upload


def test_published_text_and_summary_exclude_private_report_paths_and_diagnostics(
    packaging: SimpleNamespace,
) -> None:
    packaging.module.main()
    with zipfile.ZipFile(packaging.archive) as archive:
        assert not any("PRODUCTION_BATCH_REPORT" in name or "audio_meta" in name for name in archive.namelist())
        published = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist()
                              if name.endswith((".md", ".json")))
    assert str(packaging.root) not in published
    assert str(packaging.manifest_path) not in published
    assert "PRODUCTION_BATCH_REPORT" not in published
    assert "diagnostic_token" not in published
    assert "do-not-publish-this-token" not in published


def test_packager_requests_resume_verification_instead_of_trusting_cached_status(
    packaging: SimpleNamespace,
) -> None:
    packaging.module.main()
    assert packaging.calls == [(packaging.manifest_path, {"resume": True})]


@pytest.mark.parametrize("status", ["failed", "running", "dry_run"])
def test_unverified_report_refuses_to_create_an_archive(
    packaging: SimpleNamespace, status: str,
) -> None:
    packaging.report["status"] = status
    with pytest.raises(ValueError, match="All deliveries must pass"):
        packaging.module.main()
    assert not packaging.archive.exists()
    assert not (packaging.out / "UPLOAD_ALL.md").exists()
    assert not (packaging.out / "DELIVERY_SUMMARY.json").exists()


def test_failed_new_report_preserves_an_existing_package(packaging: SimpleNamespace) -> None:
    packaging.out.mkdir(parents=True)
    packaging.archive.write_bytes(b"previous verified package")
    packaging.report["status"] = "failed"
    with pytest.raises(ValueError, match="All deliveries must pass"):
        packaging.module.main()
    assert packaging.archive.read_bytes() == b"previous verified package"


def test_bad_final_audio_refuses_packaging_before_overwriting_files(packaging: SimpleNamespace) -> None:
    packaging.out.mkdir(parents=True)
    packaging.archive.write_bytes(b"previous verified package")
    packaging.audio_quality["status"] = "failed"
    with pytest.raises(ValueError, match="audio quality"):
        packaging.module.main()
    assert packaging.archive.read_bytes() == b"previous verified package"
    assert not (packaging.out / "DELIVERY_SUMMARY.json").exists()
    assert not (packaging.out / "UPLOAD_ALL.md").exists()
