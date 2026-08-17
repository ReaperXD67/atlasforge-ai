from pathlib import Path

from daily_video_factory.media.ai_quality import SyntheticClipInspector
from daily_video_factory.media.ffmpeg import FFmpeg


def _clip(ffmpeg: FFmpeg, output: Path, source: str) -> Path:
    ffmpeg.run(
        [
            "-f",
            "lavfi",
            "-i",
            source,
            "-t",
            "3",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
    )
    return output


def test_synthetic_gate_rejects_blank_frozen_clip(settings, monkeypatch, tmp_path: Path) -> None:
    ffmpeg = FFmpeg()
    inspector = SyntheticClipInspector(settings, ffmpeg)
    monkeypatch.setattr(inspector, "_clip_realism", lambda _frames: None)
    monkeypatch.setattr(inspector, "_semantic_judge", lambda _frames, prompt: None)
    frozen = _clip(ffmpeg, tmp_path / "frozen.mp4", "color=c=black:s=360x640:r=24")

    report = inspector.inspect(frozen)

    assert report.passed is False
    assert report.checks["exposure_safe"] is False
    assert report.checks["has_coherent_motion"] is False


def test_synthetic_gate_fails_closed_when_semantic_review_rejects(
    settings, monkeypatch, tmp_path: Path
) -> None:
    ffmpeg = FFmpeg()
    inspector = SyntheticClipInspector(settings, ffmpeg)
    # A misleadingly perfect CLIP camera guess is diagnostic only and cannot overrule the
    # semantic supervisor.
    monkeypatch.setattr(inspector, "_clip_realism", lambda _frames: 1.0)
    monkeypatch.setattr(
        inspector,
        "_semantic_judge",
        lambda _frames, prompt: {
            "verdict": "reject",
            "critical_failure": True,
            "minimum_score": 0.2,
            "anomalies": ["rubbery rigid geometry"],
        },
    )
    moving = _clip(ffmpeg, tmp_path / "moving.mp4", "testsrc2=s=360x640:r=24")

    report = inspector.inspect(moving, prompt="A rigid structure falls under gravity")

    assert report.passed is False
    assert report.checks["semantic_realism"] is False
    assert report.semantic_judge is not None
    assert report.metrics["clip_camera_realism"] == 1.0
    assert report.score < 0.8


def test_synthetic_gate_detects_short_full_frame_color_flash(
    settings, monkeypatch, tmp_path: Path
) -> None:
    ffmpeg = FFmpeg()
    inspector = SyntheticClipInspector(settings, ffmpeg)
    monkeypatch.setattr(inspector, "_clip_realism", lambda _frames: None)
    monkeypatch.setattr(inspector, "_semantic_judge", lambda _frames, prompt: None)
    flashed = _clip(
        ffmpeg,
        tmp_path / "flash.mp4",
        "testsrc2=s=360x640:r=24,drawbox=color=blue:t=fill:enable='between(t,1,1.6)'",
    )

    report = inspector.inspect(flashed)

    assert report.passed is False
    assert report.checks["no_color_flash"] is False
