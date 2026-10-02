from pathlib import Path

import pytest
from PIL import Image

from daily_video_factory.shorts_delivery import (
    ShortsDeliveryError,
    validate_probe_data,
    validate_short_delivery,
)


def _probe_payload(
    *, duration: float = 27.9, audio: bool = True, video_codec: str = "h264"
) -> dict[str, object]:
    streams: list[dict[str, object]] = [
        {
            "codec_type": "video",
            "codec_name": video_codec,
            "pix_fmt": "yuv420p",
            "width": 1080,
            "height": 1920,
            "r_frame_rate": "30/1",
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


def test_probe_gate_accepts_a_delivery_ready_short() -> None:
    report = validate_probe_data(_probe_payload())
    assert report == {
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "duration_seconds": 27.9,
        "video_codec": "h264",
        "pixel_format": "yuv420p",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
    }


def test_probe_gate_rejects_missing_audio() -> None:
    with pytest.raises(ShortsDeliveryError, match="no audio stream"):
        validate_probe_data(_probe_payload(audio=False))


def test_probe_gate_rejects_too_short_video() -> None:
    with pytest.raises(ShortsDeliveryError, match="between 20s and 30s"):
        validate_probe_data(_probe_payload(duration=12.0))


def test_probe_gate_rejects_wrong_video_codec() -> None:
    with pytest.raises(ShortsDeliveryError, match="H.264"):
        validate_probe_data(_probe_payload(video_codec="vp9"))


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


def test_delivery_gate_checks_metadata_and_voice_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "short.mp4"
    video.write_bytes(b"not-empty")
    thumbnail = tmp_path / "thumbnail.png"
    Image.new("RGB", (1080, 1920)).save(thumbnail)
    package = tmp_path / "UPLOAD_PACKAGE.md"
    package.write_text(
        "# Upload\n\n## Title\nA valid YouTube Shorts title\n\n"
        "## Description\nA useful description.\n\n## Hashtags\n#One #Two #Three\n",
        encoding="utf-8",
    )
    voice = tmp_path / "voice.json"
    voice.write_text('{"provider":"kokoro","voice":"af_heart"}', encoding="utf-8")
    monkeypatch.setattr(
        "daily_video_factory.shorts_delivery._probe", lambda _: _probe_payload()
    )
    report = validate_short_delivery(
        video,
        thumbnail,
        upload_package=package,
        voice_manifest=voice,
        expected_voice="af_heart",
    )
    assert report["metadata"]["hashtag_count"] == 3
    assert report["voice"] == {"provider": "kokoro", "voice": "af_heart"}


def test_delivery_gate_rejects_voice_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "short.mp4"
    video.write_bytes(b"not-empty")
    thumbnail = tmp_path / "thumbnail.png"
    Image.new("RGB", (1080, 1920)).save(thumbnail)
    voice = tmp_path / "voice.json"
    voice.write_text('{"provider":"edge","voice":"new_voice"}', encoding="utf-8")
    monkeypatch.setattr(
        "daily_video_factory.shorts_delivery._probe", lambda _: _probe_payload()
    )
    with pytest.raises(ShortsDeliveryError, match="af_heart"):
        validate_short_delivery(
            video,
            thumbnail,
            voice_manifest=voice,
            expected_voice="af_heart",
        )
