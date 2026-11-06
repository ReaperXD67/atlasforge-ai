from __future__ import annotations

import importlib.util
import json
import posixpath
import re
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import pytest


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    repository = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("package_cinematic_under_test", repository / "scripts/package_cinematic_delivery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project = tmp_path / "videos" / module.PROJECT_ID
    project.mkdir(parents=True)
    plan = {"project_id": module.PROJECT_ID, "duration_seconds": 20, "duration_frames": 600,
            "width": 1080, "height": 1920, "fps": 30}
    captions = [{"start": 0.1, "end": 1.0, "text": "Read before deciding."}]
    files = {
        "index.html": b"<html>original project</html>",
        "EDIT_PLAN.json": json.dumps({"timing_file": "timing.json"}).encode(),
        "timing.json": json.dumps({"voice_variant": "expressive", "captions": captions,
                                   "words": [{"text": word} for word in ["Read", "before", "deciding."]]}).encode(),
        "assets/audio/narration.srt": b"1\n00:00:00,100 --> 00:00:01,000\nRead before deciding.\n",
        "assets/audio/narration.wav": b"verified selected narration; decoder tested by cinematic runner",
        "assets/audio/master.wav": b"verified mixed master fixture",
        "assets/audio/voice-reference.wav": b"authorized original synthetic reference",
        "assets/audio/voice-reference.provenance.json": b'{"origin":"original synthetic Kokoro reference"}',
        "assets/audio/KENNEY-LICENSE.txt": b"CC0",
        "assets/fonts/Montserrat-OFL.txt": b"SIL OFL",
        "script.txt": b"Read before deciding.",
        "README.md": (repository / "videos/biznex-second-question/README.md").read_bytes(),
        "REVIEW.md": (repository / "videos/biznex-second-question/REVIEW.md").read_bytes(),
        "BRIEF.md": b"Original fictional film",
        "SPEC.md": b"Technical specification",
        "STORYLINES.md": b"Selected story",
        "PROMPTS.md": b"Original prompts",
        "create_edit.py": b"# Original authoring source\n",
        "UPLOAD_COPY.md": b"Hiraeth by Scott Buckley, CC BY 4.0. Fictional AI story.",
        "renders/final.mp4": b"final delivery fixture; media decoder independently tested",
        "assets/audio/hiraeth-download.mp3": b"unneeded duplicate",
        "assets/audio/narration-baseline.wav": b"unselected baseline",
        "client_secret-private.json": b'{"client_secret":"do-not-package"}',
        ".env": b"PASSWORD=do-not-package",
    }
    for name in module.PROVENANCE:
        files[name] = b"{}"
    files["VISUAL_PROVENANCE.json"] = b'{"assets":[]}'
    files["assets/audio/narration.asr-evidence.json"] = json.dumps({"source_report": "C:/Users/PrivateOwner/run/report.json", "asr_matches": True}).encode()
    for name, data in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (project / "AUDIO_MIX.json").write_text(json.dumps({"sources": [{"role": "voice", "asset": "assets/audio/narration.wav",
                                                                   "sha256": module.runner._hash(project / "assets/audio/narration.wav")}]}))
    snapshot_names = {"index.html", "EDIT_PLAN.json", "timing.json", "assets/audio/narration.wav",
                      "assets/audio/master.wav", "AUDIO_MIX.json"}

    def verify_sources(path):
        return plan, {name: module.runner._hash(project / name) for name in sorted(snapshot_names)}

    def media(path, unused_plan):
        return {"sha256": module.runner._hash(path), "bytes": path.stat().st_size,
                "duration_seconds": 20, "full_video_audio_decode_passed": True}

    monkeypatch.setattr(module.runner, "verify_project_sources", verify_sources)
    monkeypatch.setattr(module.runner, "verify_rendered_media", media)
    report = {"schema_version": 1, "project_id": module.PROJECT_ID, "status": "verified_delivery",
              "rendered": True, "delivery_verified": True, "source_files": verify_sources(project)[1],
              "stages": [{"name": name, "status": "passed"} for name in
                         ("render-with-check", "media-verification", "final-source-verification")],
              "output": {"file": "renders/final.mp4", **media(project / "renders/final.mp4", plan)}}
    (project / "renders/final.report.json").write_text(json.dumps(report))
    for name in module.SUPPORT:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repository / name, target)
    for source in (repository / "config/expressive-voice").glob("*"):
        if source.is_file() and source.suffix in {".json", ".txt"} and source.name != "af-heart-audition.json":
            target = tmp_path / source.relative_to(repository)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    audition = tmp_path / "output/expressive-voice/af-heart-audition"
    audition.mkdir(parents=True)
    (audition / "ab-comparison.wav").write_bytes(b"audition sample")
    for name in ("ab-comparison-order.json", "audition-report.json", "audition-independent-evidence.json"):
        (audition / name).write_text('{"source":"C:/Users/PrivateOwner/audition.wav"}')
    return SimpleNamespace(module=module, root=tmp_path, project=project, report=report,
                           snapshot_names=snapshot_names)


def test_package_includes_complete_delivery_portable_rebuild_and_no_unselected_files(delivery):
    d = delivery
    result = d.module.package_delivery(d.project, root=d.root, include_source=True)
    assert result["status"] == "packaged" and result["published"] is False
    with zipfile.ZipFile(result["archive"]) as bundle:
        names = bundle.namelist()
        assert "final.mp4" in names and "captions.srt" in names
        assert "voice-comparison/ab-comparison.wav" in names
        assert "sources/videos/biznex-second-question/assets/audio/voice-reference.wav" in names
        assert "sources/scripts/run_cinematic_project.py" in names
        assert "sources/requirements-rebuild.txt" in names and "sources/REBUILD.md" in names
        assert "sources/docs/assets/readme/second-question-poster.jpg" in names
        assert "sources/config/editing/edit-plan.schema.json" in names
        assert not any("baseline" in name or "download" in name or "secret" in name or ".env" in name for name in names)
        assert bundle.read("sources/videos/biznex-second-question/index.html") == (d.project / "index.html").read_bytes()
        manifest = json.loads(bundle.read("DELIVERY_MANIFEST.json"))
        assert manifest["visual_review_verified"] is False
        assert any(row["private_paths_redacted"] for row in manifest["files"])
        for name in names:
            if Path(name).suffix in d.module.TEXT_SUFFIXES:
                assert b"PrivateOwner" not in bundle.read(name)
        checksums = bundle.read("SHA256SUMS.txt").decode().splitlines()
        assert len(checksums) == len(names) - 1
    with pytest.raises(d.module.PackageError, match="exists"):
        d.module.package_delivery(d.project, root=d.root)


def test_bundled_readme_and_core_documentation_links_resolve(delivery):
    d = delivery
    result = d.module.package_delivery(d.project, root=d.root, include_source=True)
    with zipfile.ZipFile(result["archive"]) as bundle:
        names = set(bundle.namelist())
        for name in sorted(names):
            if not name.startswith("sources/") or not name.endswith(".md"):
                continue
            for target in re.findall(r"\]\(([^)]+)\)", bundle.read(name).decode("utf-8-sig")):
                link = urlsplit(target.strip("<>"))
                if link.scheme or link.netloc or not link.path:
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(link.path)))
                assert resolved in names or any(item.startswith(resolved + "/") for item in names), (name, target)
        readme = bundle.read("sources/videos/biznex-second-question/README.md").decode("utf-8")
        rebuild = bundle.read("sources/REBUILD.md").decode("utf-8")
        assert "sources/REBUILD.md" in readme and "full repository" in readme
        assert "$env:PYTHONPATH" in rebuild and "requirements-rebuild.txt" in rebuild


@pytest.mark.parametrize("problem", ["missing_report", "failed_report", "stale_source", "changed_video", "baseline_timing", "wrong_srt_timing", "missing_words"])
def test_not_ready_never_installs_an_export(delivery, problem):
    d = delivery
    if problem == "missing_report":
        (d.project / "renders/final.report.json").unlink()
    elif problem == "failed_report":
        d.report["status"] = "failed"
        (d.project / "renders/final.report.json").write_text(json.dumps(d.report))
    elif problem == "stale_source":
        (d.project / "index.html").write_text("changed after render")
    elif problem == "changed_video":
        (d.project / "renders/final.mp4").write_bytes(b"replacement")
    elif problem == "baseline_timing":
        timing = json.loads((d.project / "timing.json").read_text())
        timing["voice_variant"] = "baseline"
        (d.project / "timing.json").write_text(json.dumps(timing))
        d.report["source_files"] = d.module.runner.verify_project_sources(d.project)[1]
        (d.project / "renders/final.report.json").write_text(json.dumps(d.report))
    else:
        text = (d.project / "assets/audio/narration.srt").read_text()
        text = text.replace("00:00:00,100", "00:00:00,300") if problem == "wrong_srt_timing" else text.replace("before ", "")
        (d.project / "assets/audio/narration.srt").write_text(text)
    with pytest.raises((ValueError, OSError)):
        d.module.package_delivery(d.project, root=d.root)
    assert not (d.root / "output/deliveries/biznex-second-question.zip").exists()
    assert not (d.root / "output/deliveries/biznex-second-question").exists()


def test_check_is_read_only_about_exports(delivery):
    result = delivery.module.package_delivery(delivery.project, root=delivery.root, check_only=True)
    assert result["status"] == "ready" and result["packaged"] is False
    assert not (delivery.root / "output/deliveries").exists()


def test_private_runtime_path_is_rejected_and_metadata_original_is_preserved(delivery):
    d = delivery
    evidence = d.project / "assets/audio/narration.asr-evidence.json"
    before = evidence.read_bytes()
    (d.project / "index.html").write_text('private = "C:/Users/PrivateOwner/asset.png"')
    d.report["source_files"] = d.module.runner.verify_project_sources(d.project)[1]
    (d.project / "renders/final.report.json").write_text(json.dumps(d.report))
    with pytest.raises(d.module.PackageError, match="private absolute path"):
        d.module.package_delivery(d.project, root=d.root, include_source=True)
    assert evidence.read_bytes() == before


def test_edit_during_copy_aborts_without_installing_partial_zip(delivery, monkeypatch):
    d = delivery
    original = d.module.export_text
    count = 0

    def change_during_copy(source, *, exact):
        nonlocal count
        result = original(source, exact=exact)
        if source.name == "index.html":
            count += 1
            if count == 2:
                source.write_text("changed during packaging")
        return result

    monkeypatch.setattr(d.module, "export_text", change_during_copy)
    with pytest.raises(ValueError, match="changed"):
        d.module.package_delivery(d.project, root=d.root, include_source=True)
    assert not (d.root / "output/deliveries/biznex-second-question.zip").exists()
    assert not (d.root / "output/deliveries/biznex-second-question").exists()
