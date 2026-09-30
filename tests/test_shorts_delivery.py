from pathlib import Path

import pytest
from PIL import Image

from daily_video_factory.shorts_delivery import (
    ShortsDeliveryError,
    validate_probe_data,
    validate_short_delivery,
)


def _probe_payload(*, duration: float = 27.9, audio: bool = True) -> dict[str, object]:
    streams: list[dict[str, object]] = [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1080,
            "height": 1920,
            "r_frame_rate": "30/1",
        }
    ]
    if audio:
        streams.append({"codec_type": "audio", "codec_name": "aac"})
    return {"streams": streams, "format": {"duration": str(duration)}}


def test_probe_gate_accepts_a_delivery_ready_short() -> None:
    report = validate_probe_data(_probe_payload())
    assert report == {
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "duration_seconds": 27.9,
        "audio_codec": "aac",
    }


def test_probe_gate_rejects_missing_audio() -> None:
    with pytest.raises(ShortsDeliveryError, match="no audio stream"):
        validate_probe_data(_probe_payload(audio=False))


def test_probe_gate_rejects_too_short_video() -> None:
    with pytest.raises(ShortsDeliveryError, match="between 20s and 30s"):
        validate_probe_data(_probe_payload(duration=12.0))


def test_delivery_gate_rejects_wrong_thumbnail_dimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "short.mp4"
    video.write_bytes(b"not-empty")
    thumbnail = tmp_path / "thumbnail.png"
    Image.new("RGB", (1280, 720)).save(thumbnail)
    monkeypatch.setattr(
        "daily_video_factory.shorts_delivery._probe", lambda _: _probe_payload()
    )
    with pytest.raises(ShortsDeliveryError, match="1080x1920 thumbnail"):
        validate_short_delivery(video, thumbnail)
