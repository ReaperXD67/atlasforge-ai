from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image


class ShortsDeliveryError(ValueError):
    """Raised when a rendered Short is not safe to hand off."""


def _rate(value: str) -> float:
    numerator, separator, denominator = value.partition("/")
    if not separator:
        return float(numerator)
    return float(numerator) / float(denominator)


def _probe(video: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def validate_probe_data(
    payload: dict[str, Any], *, min_seconds: float = 20, max_seconds: float = 30
) -> dict[str, Any]:
    streams = payload.get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise ShortsDeliveryError("delivery video has no video stream")
    if audio_stream is None:
        raise ShortsDeliveryError("delivery video has no audio stream")

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    if (width, height) != (1080, 1920):
        raise ShortsDeliveryError(f"expected 1080x1920 video, got {width}x{height}")

    fps = _rate(str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate", "0")))
    if abs(fps - 30) > 0.01:
        raise ShortsDeliveryError(f"expected 30 fps video, got {fps:.3f}")

    video_codec = str(video_stream.get("codec_name", "")).lower()
    if video_codec != "h264":
        raise ShortsDeliveryError(f"expected H.264 video, got {video_codec or 'unknown'}")
    pixel_format = str(video_stream.get("pix_fmt", "")).lower()
    if pixel_format != "yuv420p":
        raise ShortsDeliveryError(
            f"expected yuv420p pixel format, got {pixel_format or 'unknown'}"
        )

    audio_codec = str(audio_stream.get("codec_name", "")).lower()
    if audio_codec != "aac":
        raise ShortsDeliveryError(f"expected AAC audio, got {audio_codec or 'unknown'}")
    sample_rate = int(audio_stream.get("sample_rate", 0))
    if sample_rate != 48000:
        raise ShortsDeliveryError(f"expected 48 kHz audio, got {sample_rate or 'unknown'}")
    channels = int(audio_stream.get("channels", 0))
    if channels != 2:
        raise ShortsDeliveryError(f"expected stereo audio, got {channels or 'unknown'} channel(s)")

    duration = float(payload.get("format", {}).get("duration", 0))
    if not min_seconds <= duration <= max_seconds:
        raise ShortsDeliveryError(
            f"expected duration between {min_seconds:g}s and {max_seconds:g}s, got {duration:.3f}s"
        )

    return {
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "duration_seconds": round(duration, 3),
        "video_codec": video_codec,
        "pixel_format": pixel_format,
        "audio_codec": audio_codec,
        "audio_sample_rate": sample_rate,
        "audio_channels": channels,
    }


def _section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group("body").strip() if match else ""


def validate_shorts_upload_package(markdown: str) -> dict[str, Any]:
    title_section = _section(markdown, "Title")
    title = title_section.splitlines()[0].strip() if title_section else ""
    description = _section(markdown, "Description")
    if not title:
        raise ShortsDeliveryError("upload package is missing a Title section")
    if len(title) > 100:
        raise ShortsDeliveryError(f"YouTube title exceeds 100 characters: {len(title)}")
    if not description:
        raise ShortsDeliveryError("upload package is missing a Description section")
    if len(description) > 5000:
        raise ShortsDeliveryError(
            f"YouTube description exceeds 5000 characters: {len(description)}"
        )
    hashtags = list(dict.fromkeys(re.findall(r"(?<!\w)#[A-Za-z0-9_]+", markdown)))
    if len(hashtags) < 3:
        raise ShortsDeliveryError("upload package needs at least three hashtags")
    return {
        "title": title,
        "title_characters": len(title),
        "description_characters": len(description),
        "hashtag_count": len(hashtags),
    }


def validate_voice_manifest(manifest: dict[str, Any], *, expected_voice: str) -> dict[str, str]:
    provider = str(manifest.get("provider", "")).strip()
    voice = str(manifest.get("voice") or manifest.get("id") or "").strip()
    if not provider:
        raise ShortsDeliveryError("voice manifest is missing provider")
    if not voice:
        raise ShortsDeliveryError("voice manifest is missing voice")
    if voice.casefold() != expected_voice.casefold():
        raise ShortsDeliveryError(
            f"expected voice {expected_voice!r}, got {voice!r}"
        )
    return {"provider": provider, "voice": voice}


def validate_short_delivery(
    video: Path,
    thumbnail: Path,
    *,
    upload_package: Path | None = None,
    voice_manifest: Path | None = None,
    expected_voice: str | None = None,
    min_seconds: float = 20,
    max_seconds: float = 30,
) -> dict[str, Any]:
    for label, path in (("video", video), ("thumbnail", thumbnail)):
        if not path.is_file() or path.stat().st_size == 0:
            raise ShortsDeliveryError(f"{label} is missing or empty: {path}")

    report = validate_probe_data(
        _probe(video), min_seconds=min_seconds, max_seconds=max_seconds
    )
    with Image.open(thumbnail) as image:
        if image.size != (1080, 1920):
            raise ShortsDeliveryError(
                f"expected 1080x1920 thumbnail, got {image.width}x{image.height}"
            )
        report["thumbnail_width"] = image.width
        report["thumbnail_height"] = image.height
        report["thumbnail_format"] = image.format
    report["video_bytes"] = video.stat().st_size
    report["thumbnail_bytes"] = thumbnail.stat().st_size
    if upload_package is not None:
        if not upload_package.is_file() or upload_package.stat().st_size == 0:
            raise ShortsDeliveryError(f"upload package is missing or empty: {upload_package}")
        report["metadata"] = validate_shorts_upload_package(
            upload_package.read_text(encoding="utf-8")
        )
    if expected_voice and voice_manifest is None:
        raise ShortsDeliveryError("expected voice requires a voice manifest")
    if voice_manifest is not None:
        if not voice_manifest.is_file() or voice_manifest.stat().st_size == 0:
            raise ShortsDeliveryError(f"voice manifest is missing or empty: {voice_manifest}")
        if not expected_voice:
            raise ShortsDeliveryError("voice manifest requires an expected voice")
        report["voice"] = validate_voice_manifest(
            json.loads(voice_manifest.read_text(encoding="utf-8")),
            expected_voice=expected_voice,
        )
    return report
