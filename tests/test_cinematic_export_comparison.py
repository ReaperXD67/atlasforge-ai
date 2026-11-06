from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def comparison():
    source = Path(__file__).resolve().parents[1] / "scripts/compare_cinematic_exports.py"
    spec = importlib.util.spec_from_file_location("cinematic_export_comparison", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clips(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local ffmpeg and ffprobe are required.")
    static, cut = tmp_path / "static.mp4", tmp_path / "cut.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=90x160:r=10:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(static),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=90x160:r=10:d=1",
        "-f", "lavfi", "-i", "color=white:s=90x160:r=10:d=1",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cut),
    ], check=True)
    return static, cut


@pytest.mark.integration
def test_actual_decode_distinguishes_static_from_cut_without_quality_verdict(comparison, clips):
    report = comparison.compare(*clips)
    static, cut = report["baseline"], report["candidate"]
    assert static["scene_change_event_count"] == 0
    assert static["luma_change"]["maximum"] == 0
    assert static["luma_change"]["fraction_at_or_below_low_change_threshold"] == 1
    assert cut["scene_change_events_seconds"] == pytest.approx([1.0], abs=0.01)
    assert cut["luma_change"]["maximum"] > 200
    assert 0 < cut["luma_change"]["fraction_at_or_below_low_change_threshold"] < 1
    assert "winner" not in report and "score" not in report and "passed" not in report
    assert static["sha256"] != cut["sha256"]


@pytest.mark.integration
def test_duration_guard_prevents_analysis_past_limit(comparison, clips):
    with pytest.raises(ValueError, match="duration"):
        comparison.measure(clips[0], max_seconds=1)


@pytest.mark.integration
def test_no_adjacent_frames_reports_unknown_not_zero_motion(comparison, clips, monkeypatch):
    monkeypatch.setattr(comparison, "_motion_changes", lambda path: [])
    result = comparison.measure(clips[0])
    assert result["luma_change"]["adjacent_sample_pairs"] == 0
    assert result["luma_change"]["median"] is None
    assert result["luma_change"]["fraction_at_or_below_low_change_threshold"] is None
