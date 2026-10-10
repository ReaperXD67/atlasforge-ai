from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from daily_video_factory import production_audio_quality as quality
from daily_video_factory.production_audio_quality import (
    ProductionAudioQualityError,
    check_production_audio,
    measure_video_loudness,
    parse_loudness_analysis,
    validate_loudness,
)


def _analysis(integrated: Any = "-14.21", peak: Any = "-2.00") -> str:
    return "FFmpeg analysis log\n" + json.dumps({"input_i": integrated, "input_tp": peak}) + "\n"


@pytest.mark.parametrize(
    "integrated,peak", [(-14.21, -2.0), (-15.5, -1.0), (-12.5, -1.0)],
)
def test_loudness_gate_accepts_measured_target_and_inclusive_limits(integrated: float, peak: float) -> None:
    assert validate_loudness({"integrated_lufs": integrated, "true_peak_dbtp": peak}) == {
        "integrated_lufs": integrated, "true_peak_dbtp": peak,
    }


@pytest.mark.parametrize(
    "integrated,peak,code",
    [(-15.51, -2.0, "loudness_out_of_range"), (-12.49, -2.0, "loudness_out_of_range"),
     (-14, -0.99, "true_peak_too_high"), (-70, -40, "loudness_out_of_range")],
)
def test_loudness_gate_rejects_out_of_range_loud_quiet_or_high_peak(
    integrated: float, peak: float, code: str,
) -> None:
    with pytest.raises(ProductionAudioQualityError) as exc:
        validate_loudness({"integrated_lufs": integrated, "true_peak_dbtp": peak})
    assert exc.value.code == code


@pytest.mark.parametrize(
    "value", [None, True, "", "unknown", "-inf", "inf", "nan", float("nan")],
)
def test_missing_nonfinite_and_silent_metrics_are_not_accepted(value: Any) -> None:
    with pytest.raises(ProductionAudioQualityError):
        parse_loudness_analysis(_analysis(integrated=value))
    with pytest.raises(ProductionAudioQualityError):
        parse_loudness_analysis(_analysis(peak=value))


def test_parser_ignores_unrelated_json_and_uses_last_analysis_block() -> None:
    stderr = '{"media_title":"private metadata"}\n' + _analysis("-18", "-3") + _analysis()
    assert parse_loudness_analysis(stderr) == {"integrated_lufs": -14.21, "true_peak_dbtp": -2.0}


@pytest.mark.parametrize("stderr", ["No audio analysis", '{"output_i":"-14"}', '{"input_i":"-14"}'])
def test_parser_requires_input_measurements_not_target_or_output_metrics(stderr: str) -> None:
    with pytest.raises(ProductionAudioQualityError):
        parse_loudness_analysis(stderr)


@pytest.fixture
def batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    episodes = []
    for number in range(1, 6):
        video = tmp_path / "private-workspace" / "videos" / f"clip-{number}" / "renders" / "final.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(b"final delivery bytes")
        episodes.append(SimpleNamespace(id=f"clip-{number}", output=video))
    manifest = SimpleNamespace(batch_id="audio-check", episodes=tuple(episodes))
    commands: list[tuple[list[str], dict[str, Any]]] = []
    responses: dict[str, str] = {}
    loads: list[tuple[Path, dict[str, Any]]] = []

    def load(path: Path, **kwargs: Any) -> Any:
        loads.append((path, kwargs))
        return manifest

    def run(command: list[str], **kwargs: Any) -> Any:
        commands.append((command, kwargs))
        video = command[command.index("-i") + 1]
        return SimpleNamespace(returncode=0, stderr=responses.get(video, _analysis()), stdout="")

    monkeypatch.setattr(quality, "load_production_batch_manifest", load)
    monkeypatch.setattr(quality.subprocess, "run", run)
    return SimpleNamespace(root=tmp_path, episodes=episodes, manifest=manifest,
                           commands=commands, responses=responses, loads=loads)


def test_read_only_analysis_uses_argument_list_null_output_and_preserves_final_video(batch: SimpleNamespace) -> None:
    video = batch.episodes[0].output
    before = video.read_bytes(), video.stat().st_mtime_ns
    assert measure_video_loudness(video) == {"integrated_lufs": -14.21, "true_peak_dbtp": -2.0}
    command, options = batch.commands[0]
    assert isinstance(command, list)
    assert command[0] == "ffmpeg"
    assert command[command.index("-i") + 1] == str(video)
    assert command[command.index("-map") + 1] == "0:a:0"
    assert command[-3:] == ["-f", "null", "-"]
    assert "-c:a" not in command and "-y" not in command
    assert options["shell"] is False
    assert options["capture_output"] is True
    assert before == (video.read_bytes(), video.stat().st_mtime_ns)


def test_batch_quality_report_contains_only_ids_finite_readings_and_public_limits(batch: SimpleNamespace) -> None:
    path = batch.root / "config" / "production.json"
    result = check_production_audio(path, repository_root=batch.root)
    assert batch.loads == [(path, {"repository_root": batch.root})]
    assert result["status"] == "verified"
    assert result["batch_id"] == "audio-check"
    assert len(result["episodes"]) == 5
    assert all(entry["status"] == "verified" for entry in result["episodes"])
    assert set(result["episodes"][0]) == {"id", "status", "integrated_lufs", "true_peak_dbtp"}
    public_json = json.dumps(result, allow_nan=False)
    assert str(batch.root) not in public_json
    assert "private-workspace" not in public_json
    assert "final.mp4" not in public_json


def test_one_bad_episode_does_not_hide_other_readings(batch: SimpleNamespace) -> None:
    batch.responses[str(batch.episodes[1].output)] = _analysis("-18", "-2")
    result = check_production_audio(batch.root / "production.json")
    assert result["status"] == "failed"
    assert [entry["status"] for entry in result["episodes"]] == ["verified", "failed", "verified", "verified", "verified"]
    assert result["episodes"][1]["integrated_lufs"] == -18
    assert result["episodes"][1]["error"]["code"] == "loudness_out_of_range"
    assert len(batch.commands) == 5


def test_silent_audio_is_failed_without_emitting_infinite_json(batch: SimpleNamespace) -> None:
    batch.responses[str(batch.episodes[0].output)] = _analysis("-inf", "-inf")
    result = check_production_audio(batch.root / "production.json")
    assert result["status"] == "failed"
    assert result["episodes"][0]["error"]["code"] == "nonfinite_metrics"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("failure", ["missing_tool", "nonzero", "timeout"])
def test_tool_failures_do_not_leak_private_diagnostics(
    batch: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    private = str(batch.episodes[0].output)

    def fail(*args: Any, **kwargs: Any) -> Any:
        if failure == "missing_tool":
            raise FileNotFoundError(private)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(private, 180, stderr="secret-token")
        return SimpleNamespace(returncode=1, stderr=f"Cannot decode {private} secret-token", stdout="")

    monkeypatch.setattr(quality.subprocess, "run", fail)
    result = check_production_audio(batch.root / "production.json")
    assert result["status"] == "failed"
    public = json.dumps(result)
    assert private not in public
    assert "secret-token" not in public


def test_missing_final_video_is_rejected_without_calling_ffmpeg(batch: SimpleNamespace) -> None:
    with pytest.raises(ProductionAudioQualityError, match="missing or empty"):
        measure_video_loudness(batch.root / "missing.mp4")
    assert batch.commands == []


def test_manifest_path_gate_runs_before_any_audio_analysis(
    batch: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("private-path outside authorized videos directory")

    monkeypatch.setattr(quality, "load_production_batch_manifest", invalid)
    with pytest.raises(ProductionAudioQualityError) as exc:
        check_production_audio(batch.root / "production.json")
    assert exc.value.code == "invalid_manifest"
    assert "private-path" not in str(exc.value)
    assert batch.commands == []


@pytest.mark.parametrize("status,exit_code", [("verified", 0), ("failed", 1)])
def test_standalone_checker_emits_small_json_and_failure_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    status: str, exit_code: int,
) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_production_audio.py"
    loader = importlib.util.spec_from_file_location("production_audio_checker_under_test", script)
    assert loader is not None and loader.loader is not None
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    monkeypatch.setattr(module, "check_production_audio", lambda _: {"status": status, "episodes": []})
    monkeypatch.setattr(sys, "argv", [str(script), "--manifest", str(tmp_path / "production.json")])
    assert module.main() == exit_code
    assert json.loads(capsys.readouterr().out)["status"] == status
