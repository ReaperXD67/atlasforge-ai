from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image


@pytest.fixture
def delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    source = Path(__file__).resolve().parents[1] / "scripts/package_pilot_delivery.py"
    spec = importlib.util.spec_from_file_location("pilot_delivery_under_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    report_path = tmp_path / "PRODUCTION_BATCH_REPORT.json"
    episodes = []
    for index in range(6):
        project = tmp_path / "videos" / f"pilot-{index}"
        files = {
            "renders/final.mp4": b"fixture MP4; decoder mocked",
            "assets/thumbnails/thumbnail.png": b"fixture PNG; decoder mocked",
            "UPLOAD_PACKAGE.md": b"## Files\n- renders/final.mp4\n- assets/thumbnails/thumbnail.png\n",
            "audio_request.json": b"{}", "narration.txt": b"Approved fixture transcript",
            "assets/audio/narration.exact.srt": b"1\n00:00:00,000 --> 00:00:01,000\nHello.\n",
            "assets/audio/narration.captions.json": b"[]",
            "assets/audio/narration.words.json": b"[]",
            "assets/audio/provenance.json": b"{}",
        }
        for name, content in files.items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        episodes.append(SimpleNamespace(
            id=f"pilot-{index}", project=project, format="shorts",
            output=project / "renders/final.mp4",
            thumbnail=project / "assets/thumbnails/thumbnail.png",
            upload_package=project / "UPLOAD_PACKAGE.md", voice_manifest=project / "audio_request.json",
        ))
    manifest = SimpleNamespace(path=manifest_path, report_path=report_path,
                               batch_id=module.BATCH_ID, expected_voice="af_heart", episodes=episodes)
    report = {"schema_version": 1, "status": "verified", "batch_id": module.BATCH_ID,
              "manifest": str(manifest_path), "expected_voice": "af_heart",
              "episodes": [{"id": ep.id, "status": "verified", "source_fingerprint": "source",
                            "deliverable_hashes": module.deliverable_hashes(ep)} for ep in episodes]}
    module.write_json(report_path, report)
    monkeypatch.setattr(module, "load_production_batch_manifest", lambda *a, **k: manifest)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: ("source", []))
    monkeypatch.setattr(module, "verify_production_episode", lambda ep: {
        "metadata": {"title": ep.id}, "duration_seconds": 26, "width": 1080, "height": 1920,
        "fps": 30, "voice": {"provider": "kokoro", "voice": "af_heart"},
    })
    monkeypatch.setattr(module, "measure_video_loudness",
                        lambda _: {"integrated_lufs": -14, "true_peak_dbtp": -2})
    return SimpleNamespace(module=module, manifest=manifest, report=report, root=tmp_path)


@pytest.mark.parametrize("bad_report", ["failed", "missing_episode"])
def test_incomplete_report_never_creates_a_delivery(delivery, bad_report: str) -> None:
    if bad_report == "failed":
        delivery.report["status"] = "failed"
    else:
        delivery.report["episodes"].pop()
    delivery.module.write_json(delivery.manifest.report_path, delivery.report)
    with pytest.raises(ValueError, match="verified"):
        delivery.module.package_delivery(delivery.manifest.path, root=delivery.root)
    assert not (delivery.root / "output").exists()


def test_changed_final_media_is_rejected_before_export(delivery) -> None:
    delivery.manifest.episodes[0].output.write_bytes(b"changed since verification")
    with pytest.raises(ValueError, match="delivery bytes changed"):
        delivery.module.package_delivery(delivery.manifest.path, root=delivery.root)
    assert not (delivery.root / "output").exists()


def test_changed_sources_are_rejected_before_export(delivery, monkeypatch) -> None:
    monkeypatch.setattr(delivery.module, "source_fingerprint", lambda *a: ("changed", []))
    with pytest.raises(ValueError, match="sources changed"):
        delivery.module.package_delivery(delivery.manifest.path, root=delivery.root)
    assert not (delivery.root / "output").exists()


def test_package_contains_exact_media_captions_hashes_and_reproducible_zip(delivery) -> None:
    result = delivery.module.package_delivery(delivery.manifest.path, root=delivery.root)
    directory, archive = Path(result["directory"]), Path(result["archive"])
    summary = json.loads((directory / "DELIVERY_MANIFEST.json").read_text(encoding="utf-8"))
    assert len(summary["episodes"]) == 6 and len(summary["files"]) == 48
    assert summary["published_by_packager"] is False
    for episode in delivery.manifest.episodes:
        assert (directory / episode.id / "final.mp4").read_bytes() == episode.output.read_bytes()
        assert (directory / episode.id / "captions.srt").read_bytes() == (
            episode.project / "assets/audio/narration.exact.srt"
        ).read_bytes()
        copy = (directory / episode.id / "UPLOAD_PACKAGE.md").read_text()
        assert "- final.mp4" in copy and "- thumbnail.png" in copy
        assert "renders/final.mp4" in episode.upload_package.read_text()  # source untouched
    for line in (directory / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert delivery.module.sha256(directory / name) == digest
    with zipfile.ZipFile(archive) as bundle:
        assert len(bundle.namelist()) == 52
        assert all(".." not in name and not name.startswith("/") for name in bundle.namelist())
    repeat = delivery.root / "repeated.zip"
    delivery.module.archive_directory(directory, repeat)
    assert delivery.module.sha256(repeat) == result["sha256"]
    with pytest.raises(ValueError, match="already exists"):
        delivery.module.package_delivery(delivery.manifest.path, root=delivery.root)


def test_contact_sheet_uses_actual_video_inputs_at_recorded_times(delivery, monkeypatch) -> None:
    episode = delivery.manifest.episodes[0]
    original = episode.output.read_bytes()
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[0] == "ffprobe":
            return SimpleNamespace(stdout='{"format":{"duration":"30"}}')
        assert command[command.index("-i") + 1] == str(episode.output)
        Image.new("RGB", (270, 480), "blue").save(command[-1])
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(delivery.module.subprocess, "run", run)
    sheet = delivery.module.contact_sheet(
        delivery.manifest.path, episode_ids=[episode.id], root=delivery.root,
    )
    assert sheet.is_file()
    frames = json.loads((sheet.parent / "frames.json").read_text())
    assert frames["status"] == "visual_review_only"
    assert [sample["at_seconds"] for sample in frames["samples"]] == [3, 15, 25.5]
    assert all(sample["video_sha256"] == delivery.module.sha256(episode.output)
               for sample in frames["samples"])
    assert len(commands) == 4
    assert episode.output.read_bytes() == original
