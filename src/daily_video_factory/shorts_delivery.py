from __future__ import annotations

import json
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

    fps = _rate(str(video_stream.get("r_frame_rate", "0")))
    if abs(fps - 30) > 0.01:
        raise ShortsDeliveryError(f"expected 30 fps video, got {fps:.3f}")

    codec = str(audio_stream.get("codec_name", "")).lower()
    if codec != "aac":
        raise ShortsDeliveryError(f"expected AAC audio, got {codec or 'unknown'}")

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
        "audio_codec": codec,
    }


def validate_short_delivery(
    video: Path,
    thumbnail: Path,
    *,
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
    return report
