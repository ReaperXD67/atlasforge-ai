from pathlib import Path

import pytest
from PIL import Image

from daily_video_factory.youtube_delivery import (
    YouTubeDeliveryError,
    validate_longform_probe_data,
    validate_upload_package,
    validate_youtube_delivery,
)


def _probe_payload(*, duration: float = 325.04, audio: bool = True) -> dict[str, object]:
    streams: list[dict[str, object]] = [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "avg_frame_rate": "30/1",
            "pix_fmt": "yuv420p",
        }
    ]
    if audio:
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
            }
        )
    return {"streams": streams, "format": {"duration": str(duration)}}


def _upload_package() -> str:
    return """# Upload package

## Title

Atomy Compensation Plan Explained

## Description

An evidence-aware guide to the plan.

00:00 Start here
00:32 Two legs
01:04 PV explained

## Hashtags

#Atomy #AtomyUSA #BusinessGuide
"""


def test_probe_gate_accepts_a_longform_youtube_video() -> None:
    report = validate_longform_probe_data(_probe_payload())
    assert report["width"] == 1920
    assert report["height"] == 1080
    assert report["video_codec"] == "h264"
    assert report["audio_sample_rate"] == 48000


def test_probe_gate_rejects_missing_audio() -> None:
    with pytest.raises(YouTubeDeliveryError, match="no audio stream"):
        validate_longform_probe_data(_probe_payload(audio=False))


def test_upload_package_requires_youtube_chapters() -> None:
    broken = _upload_package().replace("00:00 Start here\n00:32 Two legs\n01:04 PV explained", "")
    with pytest.raises(YouTubeDeliveryError, match="timestamped chapters"):
        validate_upload_package(broken, duration_seconds=325)


def test_delivery_gate_accepts_complete_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not-empty")
    thumbnail = tmp_path / "thumbnail.png"
    Image.new("RGB", (1920, 1080)).save(thumbnail)
    package = tmp_path / "UPLOAD_PACKAGE.md"
    package.write_text(_upload_package(), encoding="utf-8")
    monkeypatch.setattr(
        "daily_video_factory.youtube_delivery._probe", lambda _: _probe_payload()
    )
    report = validate_youtube_delivery(video, thumbnail, package)
    assert report["metadata"]["chapter_count"] == 3
    assert report["thumbnail_width"] == 1920


def test_delivery_gate_rejects_vertical_thumbnail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not-empty")
    thumbnail = tmp_path / "thumbnail.png"
    Image.new("RGB", (1080, 1920)).save(thumbnail)
    package = tmp_path / "UPLOAD_PACKAGE.md"
    package.write_text(_upload_package(), encoding="utf-8")
    monkeypatch.setattr(
        "daily_video_factory.youtube_delivery._probe", lambda _: _probe_payload()
    )
    with pytest.raises(YouTubeDeliveryError, match="16:9 thumbnail"):
        validate_youtube_delivery(video, thumbnail, package)
