from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

import pytest
from test_edit_plan import make_project

from daily_video_factory.edit_plan import compile_project_edit_plan
from scripts import run_cinematic_project as workflow


def hashed(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def build_fixture(project: Path) -> None:
    """A valid source/receipt fixture, not a rendered video or an audio mix test."""
    plan_path = make_project(project)
    compiled, _ = compile_project_edit_plan(plan_path)
    (project / "assets/vendor").mkdir()
    (project / "assets/fonts").mkdir()
    (project / "assets/audio").mkdir()
    for name in ("cinematic_primitives.js", "gsap.min.js"):
        (project / "assets/vendor" / name).write_text("/* test vendor */", encoding="utf-8")
    (project / "assets/fonts/example.ttf").write_bytes(b"fixture-font")
    (project / "index.html").write_text('<html><head><link rel="stylesheet" href="cinematic.css"></head>'
                                       '<body><img src="assets/plate-0.svg"><script src="cinematic.js"></script></body></html>', encoding="utf-8")
    (project / "cinematic.css").write_text("@font-face{src:url('assets/fonts/example.ttf')} .a{filter:url(#n)}", encoding="utf-8")
    (project / "cinematic.js").write_text("/* generated fixture */", encoding="utf-8")
    (project / "package.json").write_text('{"scripts":{"check":"npx hyperframes@0.9.19 check"}}', encoding="utf-8")
    (project / "hyperframes.json").write_text("{}", encoding="utf-8")
    write_json(project / "DIRECTION.json", {"audio_master": "assets/audio/master.wav", "review_state": "test fixture"})
    with wave.open(str(project / "assets/audio/master.wav"), "wb") as wav:
        wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x00" * (36 * 48000 * 2 * 2))
    write_json(project / "AUDIO_MIX.json", {
        "compiled_plan_sha256": hashed(project / "EDIT_PLAN.compiled.json"),
        "master_sha256": hashed(project / "assets/audio/master.wav"),
        "duration_seconds": 36, "samples": 36 * 48000, "sample_rate": 48000, "channels": 2,
    })
    files = workflow.REQUIRED_BUILD_FILES | {"assets/audio/master.wav"}
    write_json(project / "CINEMATIC_BUILD.json", {
        "schema_version": 1, "project_id": compiled.project_id,
        "duration_frames": compiled.duration_frames, "fps": compiled.fps,
        "files": {name: hashed(project / name) for name in files}, "rendered": False,
    })


def test_check_only_verifies_current_sources_without_render_claim_or_rebuild(tmp_path: Path) -> None:
    build_fixture(tmp_path)
    before = {name: hashed(tmp_path / name) for name in ("EDIT_PLAN.json", "index.html", "assets/audio/master.wav")}
    result = workflow.run_project(tmp_path, check_only=True)
    assert result["status"] == "sources_verified"
    assert result["rendered"] is False and result["delivery_verified"] is False
    assert result["output"] is None and result["published"] is False
    assert result["visual_review_verified"] is False
    assert "assets/fonts/example.ttf" in result["source_files"]
    assert before == {name: hashed(tmp_path / name) for name in before}


@pytest.mark.parametrize("name", ["assets/plate-0.svg", "assets/voice.wav", "index.html", "assets/audio/master.wav"])
def test_stale_sources_are_rejected(tmp_path: Path, name: str) -> None:
    build_fixture(tmp_path)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Stale|changed"):
        workflow.run_project(tmp_path, check_only=True)
    report = json.loads((tmp_path / "CINEMATIC_RUN.json").read_text())
    assert report["status"] == "failed" and not report["delivery_verified"]


def test_new_gain_plan_cannot_reuse_an_old_mix(tmp_path: Path) -> None:
    build_fixture(tmp_path)
    path = tmp_path / "EDIT_PLAN.json"
    raw = json.loads(path.read_text())
    raw["audio"][1]["gain_db"] = -25
    write_json(path, raw)
    compile_project_edit_plan(path)
    with pytest.raises(workflow.CinematicRunError, match="different edit"):
        workflow.verify_project_sources(tmp_path)


def test_build_receipt_cannot_omit_a_required_source(tmp_path: Path) -> None:
    build_fixture(tmp_path)
    path = tmp_path / "CINEMATIC_BUILD.json"
    build = json.loads(path.read_text())
    del build["files"]["cinematic.js"]
    write_json(path, build)
    with pytest.raises(workflow.CinematicRunError, match="omits"):
        workflow.verify_project_sources(tmp_path)


def test_font_change_during_render_is_detected_without_builder_listing_font(tmp_path: Path) -> None:
    build_fixture(tmp_path)
    _, before = workflow.verify_project_sources(tmp_path)
    (tmp_path / "assets/fonts/example.ttf").write_bytes(b"changed font")
    with pytest.raises(workflow.CinematicRunError, match="Sources changed"):
        workflow.assert_sources_unchanged(tmp_path, before)


def test_remote_runtime_media_is_not_allowed(tmp_path: Path) -> None:
    build_fixture(tmp_path)
    (tmp_path / "cinematic.css").write_text("@font-face{src:url('https://example.com/font.ttf')}", encoding="utf-8")
    build_path = tmp_path / "CINEMATIC_BUILD.json"
    build = json.loads(build_path.read_text())
    build["files"]["cinematic.css"] = hashed(tmp_path / "cinematic.css")
    write_json(build_path, build)
    with pytest.raises(workflow.CinematicRunError, match="must be local"):
        workflow.verify_project_sources(tmp_path)


@pytest.mark.parametrize("failing_stage", ["compile", "mix", "build"])
def test_stage_failure_stops_later_steps_and_invalidates_prior_report(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch,
                                                                    failing_stage: str) -> None:
    build_fixture(tmp_path)
    calls = []
    write_json(tmp_path / "CINEMATIC_RUN.json", {"status": "verified_delivery", "delivery_verified": True})

    def step(name: str) -> None:
        calls.append(name)
        if name == failing_stage:
            raise RuntimeError(f"simulated {name} failure")

    monkeypatch.setattr(workflow, "compile_project_edit_plan", lambda *_: step("compile"))
    monkeypatch.setattr(workflow, "mix_project_audio", lambda *_: step("mix"))
    monkeypatch.setattr(workflow, "run_command", lambda *_, **__: step("build"))
    with pytest.raises(RuntimeError, match="simulated"):
        workflow.run_project(tmp_path)
    assert calls == ["compile", "mix", "build"][:["compile", "mix", "build"].index(failing_stage) + 1]
    report = json.loads((tmp_path / "CINEMATIC_RUN.json").read_text())
    assert report["failed_stage"] == failing_stage
    assert not report["rendered"] and not report["delivery_verified"]


def test_interruption_records_failure_without_touching_existing_export(tmp_path: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    build_fixture(tmp_path)
    (tmp_path / "renders").mkdir()
    (tmp_path / "renders/final.mp4").write_bytes(b"previous delivery")
    monkeypatch.setattr(workflow, "compile_project_edit_plan", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        workflow.run_project(tmp_path, render=True)
    assert (tmp_path / "renders/final.mp4").read_bytes() == b"previous delivery"
    report = json.loads((tmp_path / "CINEMATIC_RUN.json").read_text())
    assert report["error_type"] == "KeyboardInterrupt" and not report["delivery_verified"]


def test_failed_render_cannot_adopt_an_existing_mp4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build_fixture(tmp_path)
    (tmp_path / "renders").mkdir()
    (tmp_path / "renders/final.mp4").write_bytes(b"old mp4")
    monkeypatch.setattr(workflow, "compile_project_edit_plan", lambda *_: None)
    monkeypatch.setattr(workflow, "mix_project_audio", lambda *_: None)
    monkeypatch.setattr(workflow, "render_command", lambda *_: ["fixture-renderer"])

    def command(args: list[str], **_: Any) -> None:
        if args == ["fixture-renderer"]:
            raise workflow.CinematicRunError("renderer failed")

    monkeypatch.setattr(workflow, "run_command", command)
    with pytest.raises(workflow.CinematicRunError, match="renderer failed"):
        workflow.run_project(tmp_path, render=True)
    assert (tmp_path / "renders/final.mp4").read_bytes() == b"old mp4"
    report = json.loads((tmp_path / "CINEMATIC_RUN.json").read_text())
    assert report["output"] is None and report["failed_stage"] == "render-with-check"


def test_source_changes_during_render_stop_before_media_verification(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    build_fixture(tmp_path)
    monkeypatch.setattr(workflow, "compile_project_edit_plan", lambda *_: None)
    monkeypatch.setattr(workflow, "mix_project_audio", lambda *_: None)
    monkeypatch.setattr(workflow, "render_command", lambda *_: ["fixture-renderer"])
    verified = []
    monkeypatch.setattr(workflow, "verify_rendered_media", lambda *_: verified.append(True))

    def command(args: list[str], **_: Any) -> None:
        if args == ["fixture-renderer"]:
            (tmp_path / "assets/fonts/example.ttf").write_bytes(b"modified during render")

    monkeypatch.setattr(workflow, "run_command", command)
    with pytest.raises(workflow.CinematicRunError, match="Sources changed"):
        workflow.run_project(tmp_path, render=True)
    assert verified == []


@pytest.mark.parametrize("output", ["../export.mp4", "C:/export.mp4", "index.mp4", "renders/wrong.txt"])
def test_export_path_is_contained_and_cannot_overwrite_inputs(tmp_path: Path, output: str) -> None:
    build_fixture(tmp_path)
    with pytest.raises(workflow.CinematicRunError):
        workflow.run_project(tmp_path, output=output)


def test_render_and_read_only_mode_cannot_be_combined(tmp_path: Path) -> None:
    with pytest.raises(workflow.CinematicRunError, match="cannot be combined"):
        workflow.run_project(tmp_path, render=True, check_only=True)


@pytest.fixture
def actual_small_video(tmp_path: Path) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg/ffprobe unavailable")
    path = tmp_path / "test.mp4"
    subprocess.run([str(shutil.which("ffmpeg")), "-v", "error", "-f", "lavfi", "-i",
                    "color=c=navy:s=320x568:r=30:d=1", "-f", "lavfi", "-i",
                    "sine=frequency=400:sample_rate=48000:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ac", "2", "-t", "1", "-y", str(path)], check=True, timeout=30)
    return path


def small_plan() -> dict[str, Any]:
    return {"width": 320, "height": 568, "fps": 30, "duration_frames": 30, "duration_seconds": 1.0}


@pytest.mark.integration
def test_real_media_probe_counts_frames_and_decodes_both_streams(actual_small_video: Path) -> None:
    # This is a real 1-second FFmpeg fixture, not a mocked or claimed HyperFrames render.
    result = workflow.verify_rendered_media(actual_small_video, small_plan(), min_seconds=0.5, max_seconds=2)
    assert result["decoded_video_frames"] == 30
    assert result["full_video_audio_decode_passed"]
    assert result["sha256"] == hashed(actual_small_video)
    assert result["bytes"] > 0 and result["sample_rate"] == 48000


@pytest.mark.integration
def test_real_media_wrong_expected_frame_count_is_rejected(actual_small_video: Path) -> None:
    plan = small_plan()
    plan["duration_frames"] = 31
    with pytest.raises(workflow.CinematicRunError, match="frame count"):
        workflow.verify_rendered_media(actual_small_video, plan, min_seconds=0.5, max_seconds=2)


@pytest.mark.integration
def test_truncated_real_mp4_is_rejected(actual_small_video: Path) -> None:
    data = actual_small_video.read_bytes()
    actual_small_video.write_bytes(data[:len(data) // 2])
    with pytest.raises(workflow.CinematicRunError):
        workflow.verify_rendered_media(actual_small_video, small_plan(), min_seconds=0.5, max_seconds=2)
