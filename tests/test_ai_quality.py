from pathlib import Path

import numpy as np
from PIL import Image

from daily_video_factory.media.ai_quality import SyntheticClipInspector
from daily_video_factory.media.ffmpeg import FFmpeg


class FrameFixtureFFmpeg(FFmpeg):
    """Exercise the inspector without requiring an FFmpeg binary on CI runners."""

    def __init__(self, frames: list[Image.Image]) -> None:
        super().__init__(executable="fixture-ffmpeg", ffprobe="fixture-ffprobe")
        self.frames = frames

    def duration(self, path: Path) -> float:
        del path
        return 3.0

    def run(self, args: list[str], timeout_seconds: int = 3600):
        del timeout_seconds
        pattern = str(args[-1])
        for index, frame in enumerate(self.frames, start=1):
            frame.save(Path(pattern.replace("%02d", f"{index:02d}")), quality=95)


def _moving_frames(*, flash: bool = False) -> list[Image.Image]:
    frames: list[Image.Image] = []
    height, width = 640, 360
    for index in range(9):
        if flash and index in {4, 5}:
            array = np.full((height, width, 3), (18, 30, 235), dtype=np.uint8)
        else:
            x = np.arange(width, dtype=np.uint16)[None, :]
            y = np.arange(height, dtype=np.uint16)[:, None]
            checker = (((x + index * 5) // 24 + y // 24) % 2 * 92 + 74).astype(np.uint8)
            array = np.stack(
                [checker, np.roll(checker, index * 3, axis=1), 210 - checker // 2], axis=2
            )
        frames.append(Image.fromarray(array, mode="RGB"))
    return frames


def test_synthetic_gate_rejects_blank_frozen_clip(settings, monkeypatch, tmp_path: Path) -> None:
    ffmpeg = FrameFixtureFFmpeg([Image.new("RGB", (360, 640), "black") for _ in range(9)])
    inspector = SyntheticClipInspector(settings, ffmpeg)
    monkeypatch.setattr(inspector, "_clip_realism", lambda _frames: None)
    monkeypatch.setattr(inspector, "_semantic_judge", lambda _frames, prompt: None)
    frozen = tmp_path / "frozen.mp4"

    report = inspector.inspect(frozen)

    assert report.passed is False
    assert report.checks["exposure_safe"] is False
    assert report.checks["has_coherent_motion"] is False


def test_synthetic_gate_fails_closed_when_semantic_review_rejects(
    settings, monkeypatch, tmp_path: Path
) -> None:
    ffmpeg = FrameFixtureFFmpeg(_moving_frames())
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
    moving = tmp_path / "moving.mp4"

    report = inspector.inspect(moving, prompt="A rigid structure falls under gravity")

    assert report.passed is False
    assert report.checks["semantic_realism"] is False
    assert report.semantic_judge is not None
    assert report.metrics["clip_camera_realism"] == 1.0
    assert report.score < 0.8


def test_synthetic_gate_detects_short_full_frame_color_flash(
    settings, monkeypatch, tmp_path: Path
) -> None:
    ffmpeg = FrameFixtureFFmpeg(_moving_frames(flash=True))
    inspector = SyntheticClipInspector(settings, ffmpeg)
    monkeypatch.setattr(inspector, "_clip_realism", lambda _frames: None)
    monkeypatch.setattr(inspector, "_semantic_judge", lambda _frames, prompt: None)
    flashed = tmp_path / "flash.mp4"

    report = inspector.inspect(flashed)

    assert report.passed is False
    assert report.checks["no_color_flash"] is False
