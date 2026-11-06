"""Measure two real local video exports without assigning creative or retention scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

SCENE_THRESHOLD = 0.30
SCENE_SIZE = (270, 480)
MOTION_SIZE = (90, 160)
SAMPLE_FPS = 8
LOW_CHANGE_LUMA = 1.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _motion_changes(path: Path) -> list[float]:
    """Return mean absolute luma changes between adjacent sampled frames, in 0..255 units."""
    width, height = MOTION_SIZE
    frame_bytes = width * height
    command = [
        "ffmpeg", "-v", "error", "-nostdin", "-threads", "2", "-i", str(path),
        "-map", "0:v:0", "-filter_threads", "1", "-vf",
        f"fps={SAMPLE_FPS},scale={width}:{height},format=gray", "-an", "-f", "rawvideo", "-",
    ]
    changes: list[float] = []
    previous: Any = None
    with tempfile.TemporaryFile() as errors, subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=errors,
    ) as process:
        assert process.stdout is not None
        try:
            while True:
                frame = process.stdout.read(frame_bytes)
                if not frame:
                    break
                if len(frame) != frame_bytes:
                    raise ValueError("Decoder returned an incomplete frame.")
                current = np.frombuffer(frame, dtype=np.uint8).astype(np.int16)
                if previous is not None:
                    changes.append(float(np.abs(current - previous).mean()))
                previous = current
            if process.wait() != 0:
                raise ValueError("Video frame decoding failed.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return changes


def measure(path: Path, *, max_seconds: float = 600) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("An input video does not exist.")
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True,
    ).stdout)
    video = next((stream for stream in probe.get("streams", [])
                  if stream.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("An input contains no video stream.")
    duration = float(probe.get("format", {}).get("duration", video.get("duration", 0)))
    if not math.isfinite(duration) or not 0 < duration <= max_seconds:
        raise ValueError("Input duration is unknown or outside the configured analysis limit.")
    fingerprint = sha256(path)
    width, height = SCENE_SIZE
    selection = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-threads", "2", "-i", str(path),
         "-map", "0:v:0", "-filter_threads", "1", "-vf",
         f"scale={width}:{height},select=gt(scene\\,{SCENE_THRESHOLD:.2f}),showinfo",
         "-an", "-f", "null", "-"], capture_output=True, text=True, check=True,
    )
    events = [float(value) for value in re.findall(r"pts_time:\s*([0-9.eE+\-]+)", selection.stderr)]
    changes = _motion_changes(path)
    if sha256(path) != fingerprint:
        raise ValueError("An input changed during analysis; no comparison can be recorded.")
    return {
        "filename": path.name, "sha256": fingerprint, "container_seconds": duration,
        "video_stream": video,
        "scene_change_events_seconds": events, "scene_change_event_count": len(events),
        "scene_change_events_per_minute": round(len(events) / duration * 60, 4),
        "luma_change": {
            "adjacent_sample_pairs": len(changes),
            "median": float(np.median(changes)) if changes else None,
            "p90": float(np.percentile(changes, 90)) if changes else None,
            "maximum": max(changes) if changes else None,
            "fraction_at_or_below_low_change_threshold": (
                sum(change <= LOW_CHANGE_LUMA for change in changes) / len(changes)
                if changes else None
            ),
        },
    }


def compare(baseline: Path, candidate: Path, *, max_seconds: float = 600) -> dict[str, Any]:
    return {
        "schema_version": 1, "status": "measured_comparison",
        "checked_at": datetime.now(UTC).isoformat(),
        "ffmpeg_version": subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=True,
        ).stdout.splitlines()[0],
        "method": {
            "scene_threshold": SCENE_THRESHOLD, "scene_size": list(SCENE_SIZE),
            "motion_size": list(MOTION_SIZE), "sample_fps": SAMPLE_FPS,
            "low_change_luma_threshold": LOW_CHANGE_LUMA,
            "luma_units": "mean absolute difference on an unsigned 8-bit grayscale scale (0..255)",
            "region": "full frame, including captions and overlays",
            "limitations": (
                "Scene events are pixel changes, not human-labeled cuts. Luma change includes "
                "camera motion, subject movement, edits and text. Small motion can be missed. "
                "Neither metric measures storytelling, naturalness, retention or audience reach. "
                "No pass/fail, winner or creative quality score is assigned."
            ),
        },
        "baseline": measure(baseline, max_seconds=max_seconds),
        "candidate": measure(candidate, max_seconds=max_seconds),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=600)
    args = parser.parse_args()
    if not math.isfinite(args.max_seconds) or args.max_seconds <= 0:
        parser.error("--max-seconds must be a positive finite duration.")
    if args.output.resolve() in {args.baseline.resolve(), args.candidate.resolve()}:
        parser.error("Output must not replace an input video.")
    try:
        report = compare(args.baseline, args.candidate, max_seconds=args.max_seconds)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, subprocess.SubprocessError):
        raise SystemExit("Comparison failed. Check local inputs, ffmpeg/ffprobe and duration limit; no valid comparison was produced.") from None
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "quality_verdict": "not_assessed"}))


if __name__ == "__main__":
    main()
