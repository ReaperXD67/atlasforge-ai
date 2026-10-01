from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image


class YouTubeDeliveryError(ValueError):
    """Raised when a long-form YouTube package is not ready to upload."""


def _rate(value: str) -> float:
    numerator, separator, denominator = value.partition("/")
    if not separator:
        return float(numerator)
    parsed_denominator = float(denominator)
    return float(numerator) / parsed_denominator if parsed_denominator else 0.0


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


def _section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group("body").strip() if match else ""


def _timestamp_seconds(value: str) -> int:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def validate_upload_package(markdown: str, *, duration_seconds: float) -> dict[str, Any]:
    title = _section(markdown, "Title").splitlines()[0].strip() if _section(markdown, "Title") else ""
    description = _section(markdown, "Description")
    if not title:
        raise YouTubeDeliveryError("upload package is missing a Title section")
    if len(title) > 100:
        raise YouTubeDeliveryError(f"YouTube title exceeds 100 characters: {len(title)}")
    if not description:
        raise YouTubeDeliveryError("upload package is missing a Description section")
    if len(description) > 5000:
        raise YouTubeDeliveryError(
            f"YouTube description exceeds 5000 characters: {len(description)}"
        )

    hashtags = list(dict.fromkeys(re.findall(r"(?<!\w)#[A-Za-z0-9_]+", markdown)))
    if len(hashtags) < 3:
        raise YouTubeDeliveryError("upload package needs at least three hashtags")

    chapters = [
        (_timestamp_seconds(match.group(1)), match.group(2).strip())
        for match in re.finditer(
            r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", description, flags=re.MULTILINE
        )
    ]
    if len(chapters) < 3:
        raise YouTubeDeliveryError("description needs at least three timestamped chapters")
    if chapters[0][0] != 0:
        raise YouTubeDeliveryError("the first YouTube chapter must start at 00:00")
    for (start, _), (next_start, _) in zip(chapters, chapters[1:], strict=False):
        if next_start - start < 10:
            raise YouTubeDeliveryError("each YouTube chapter must be at least 10 seconds long")
    if chapters[-1][0] >= duration_seconds:
        raise YouTubeDeliveryError("the final chapter starts after the video ends")

    return {
        "title": title,
        "title_characters": len(title),
        "description_characters": len(description),
        "hashtag_count": len(hashtags),
        "chapter_count": len(chapters),
        "chapters": [
            {"start_seconds": start, "title": chapter_title}
            for start, chapter_title in chapters
        ],
    }


def validate_longform_probe_data(
    payload: dict[str, Any], *, min_seconds: float = 300, max_seconds: float = 360
) -> dict[str, Any]:
    streams = payload.get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise YouTubeDeliveryError("delivery video has no video stream")
    if audio_stream is None:
        raise YouTubeDeliveryError("delivery video has no audio stream")

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    if (width, height) != (1920, 1080):
        raise YouTubeDeliveryError(f"expected 1920x1080 video, got {width}x{height}")

    fps = _rate(str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate", "0")))
    if abs(fps - 30) > 0.01:
        raise YouTubeDeliveryError(f"expected 30 fps video, got {fps:.3f}")

    video_codec = str(video_stream.get("codec_name", "")).lower()
    if video_codec != "h264":
        raise YouTubeDeliveryError(f"expected H.264 video, got {video_codec or 'unknown'}")
    if str(video_stream.get("pix_fmt", "")).lower() != "yuv420p":
        raise YouTubeDeliveryError(
            f"expected yuv420p pixel format, got {video_stream.get('pix_fmt') or 'unknown'}"
        )

    audio_codec = str(audio_stream.get("codec_name", "")).lower()
    if audio_codec != "aac":
        raise YouTubeDeliveryError(f"expected AAC audio, got {audio_codec or 'unknown'}")
    sample_rate = int(audio_stream.get("sample_rate", 0))
    if sample_rate != 48000:
        raise YouTubeDeliveryError(f"expected 48 kHz audio, got {sample_rate or 'unknown'}")
    channels = int(audio_stream.get("channels", 0))
    if channels != 2:
        raise YouTubeDeliveryError(f"expected stereo audio, got {channels or 'unknown'} channel(s)")

    duration = float(payload.get("format", {}).get("duration", 0))
    if not min_seconds <= duration <= max_seconds:
        raise YouTubeDeliveryError(
            f"expected duration between {min_seconds:g}s and {max_seconds:g}s, got {duration:.3f}s"
        )

    return {
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "duration_seconds": round(duration, 3),
        "video_codec": video_codec,
        "pixel_format": "yuv420p",
        "audio_codec": audio_codec,
        "audio_sample_rate": sample_rate,
        "audio_channels": channels,
    }


def validate_youtube_delivery(
    video: Path,
    thumbnail: Path,
    upload_package: Path,
    *,
    min_seconds: float = 300,
    max_seconds: float = 360,
) -> dict[str, Any]:
    for label, path in (
        ("video", video),
        ("thumbnail", thumbnail),
        ("upload package", upload_package),
    ):
        if not path.is_file() or path.stat().st_size == 0:
            raise YouTubeDeliveryError(f"{label} is missing or empty: {path}")

    report = validate_longform_probe_data(
        _probe(video), min_seconds=min_seconds, max_seconds=max_seconds
    )
    with Image.open(thumbnail) as image:
        if image.width < 1280 or image.width * 9 != image.height * 16:
            raise YouTubeDeliveryError(
                "expected a 16:9 thumbnail at least 1280 pixels wide, "
                f"got {image.width}x{image.height}"
            )
        if image.format not in {"JPEG", "PNG"}:
            raise YouTubeDeliveryError(
                f"expected a JPEG or PNG thumbnail, got {image.format or 'unknown'}"
            )
        report["thumbnail_width"] = image.width
        report["thumbnail_height"] = image.height
        report["thumbnail_format"] = image.format

    report["metadata"] = validate_upload_package(
        upload_package.read_text(encoding="utf-8"),
        duration_seconds=report["duration_seconds"],
    )
    report["video_bytes"] = video.stat().st_size
    report["thumbnail_bytes"] = thumbnail.stat().st_size
    return report
