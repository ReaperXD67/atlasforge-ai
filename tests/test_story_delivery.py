from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

import pytest

from daily_video_factory.story_pipeline import PipelineError


def load_script(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location("test_" + path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package_fixture(tmp_path: Path, monkeypatch):
    package = load_script("package_story_delivery.py")
    monkeypatch.setattr(package, "ROOT", tmp_path)
    project = tmp_path / "videos/test-story"
    contents = {
        "renders/final.mp4": b"fixture media; real MP4 verification is delegated to tested existing verifier",
        "renders/final.report.json": b"{}", "assets/audio/narration.srt": b"1\n00:00:00,000 --> 00:00:01,000\nA story.\n",
        "script.txt": b"A story.", "BRIEF.md": b"Authored fixture.", "UPLOAD_COPY.md": b"Prepared, not posted.",
        "CREDITS.md": b"Original test fixture; no third-party media.",
        "qa/audio/encoded-audio-verification.json": b"{}", "qa/audio/audition-independent-evidence.json": b"{}",
        "qa/frames/frame-review.json": b"{}", "qa/frames/sheet-01.jpg": b"fixture review sheet",
    }
    for name, payload in contents.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (project / "PIPELINE.json").write_text(json.dumps({"project_id": project.name, "stages": [
        {"id": "render", "executor": "python", "entrypoint": "scripts/render.py", "outputs": ["renders/final.mp4"]},
    ]}))
    video = project / "renders/final.mp4"
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    verified = {"video": video, "video_sha256": digest, "snapshot": {}, "report": {"output": {"sha256": digest}}}
    monkeypatch.setattr(package, "verify_current_render", lambda *a, **k: verified)
    monkeypatch.setattr(package, "verify_story_qa", lambda *a, **k: {"frames": {"files": {"sheet-01.jpg": "unused"}}})
    return package, project


def test_consumer_package_checksums_and_video_identity_are_exact(tmp_path: Path, monkeypatch) -> None:
    package, project = package_fixture(tmp_path, monkeypatch)
    result = package.package(project, include_source=False)
    assert result["status"] == "verified_technical_export"
    assert not result["visual_review_verified"] and not result["published"]
    archive = project / result["archive"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == result["archive_sha256"]
    with zipfile.ZipFile(archive) as bundle:
        for line in bundle.read("SHA256SUMS.txt").decode().splitlines():
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(bundle.read(name)).hexdigest() == digest
        assert hashlib.sha256(bundle.read("final.mp4")).hexdigest() == result["video_sha256"]
        assert not any(name.startswith("sources/") for name in bundle.namelist())


def test_failed_qa_cannot_replace_prior_delivery(tmp_path: Path, monkeypatch) -> None:
    package, project = package_fixture(tmp_path, monkeypatch)
    prior = project / "renders/delivery.zip"
    prior.write_bytes(b"existing delivery")
    def failed(*args, **kwargs):
        raise PipelineError("Stale encoded speech evidence")
    monkeypatch.setattr(package, "verify_story_qa", failed)
    with pytest.raises(PipelineError, match="Stale"):
        package.package(project, include_source=False)
    assert prior.read_bytes() == b"existing delivery"
    assert not (project / "STORY_PACKAGE.json").exists()


def test_private_paths_are_redacted_only_in_metadata_and_secrets_are_rejected(tmp_path: Path) -> None:
    package = load_script("package_story_delivery.py")
    secret = re.compile(r'"refresh_token"\s*:\s*"[^"]+"')
    source = tmp_path / "provenance.json"
    source.write_text('{"file":"C:/Users/Example/private/voice.wav"}')
    payload, changed = package.export_payload(source, exact=False, secret_pattern=secret)
    assert changed and b"Example" not in payload
    with pytest.raises(PipelineError, match="exact runtime"):
        package.export_payload(source, exact=True, secret_pattern=secret)
    source.write_text('{"refresh_token":"private-value"}')
    with pytest.raises(PipelineError, match="credentials"):
        package.export_payload(source, exact=False, secret_pattern=secret)


def test_empty_and_silent_audio_cannot_produce_alignment_success() -> None:
    import numpy as np

    module = load_script("verify_story_audio.py")
    for samples in (np.empty((0, 2)), np.zeros((1000, 2))):
        with pytest.raises((PipelineError, ValueError)):
            module.alignment(samples, samples)
