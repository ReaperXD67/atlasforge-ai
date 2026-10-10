"""Read-only loudness checks for final mixed-batch deliveries; no encoding."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from .production_batch import load_production_batch_manifest

MIN_INTEGRATED_LUFS = -15.5
MAX_INTEGRATED_LUFS = -12.5
MAX_TRUE_PEAK_DBTP = -1.0


class ProductionAudioQualityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _finite_metric(value: Any, label: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ProductionAudioQualityError("invalid_metrics", f"Missing or invalid {label}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProductionAudioQualityError("invalid_metrics", f"Missing or invalid {label}") from exc
    if not math.isfinite(number):
        raise ProductionAudioQualityError("nonfinite_metrics", f"Nonfinite or silent {label}")
    return number


def parse_loudness_analysis(stderr: str) -> dict[str, float]:
    """Extract FFmpeg's last loudnorm metrics block, not media metadata/log text."""
    decoder = json.JSONDecoder()
    metrics: dict[str, Any] | None = None
    for position, character in enumerate(stderr):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(stderr[position:])
        except ValueError:
            continue
        if isinstance(parsed, dict) and ("input_i" in parsed or "input_tp" in parsed):
            metrics = parsed
    if metrics is None:
        raise ProductionAudioQualityError("missing_metrics", "FFmpeg returned no loudness metrics")
    return {
        "integrated_lufs": _finite_metric(metrics.get("input_i"), "integrated LUFS"),
        "true_peak_dbtp": _finite_metric(metrics.get("input_tp"), "true peak"),
    }


def validate_loudness(readings: dict[str, Any]) -> dict[str, float]:
    integrated = _finite_metric(readings.get("integrated_lufs"), "integrated LUFS")
    peak = _finite_metric(readings.get("true_peak_dbtp"), "true peak")
    if not MIN_INTEGRATED_LUFS <= integrated <= MAX_INTEGRATED_LUFS:
        raise ProductionAudioQualityError(
            "loudness_out_of_range",
            f"Integrated loudness must be between {MIN_INTEGRATED_LUFS:g} and {MAX_INTEGRATED_LUFS:g} LUFS",
        )
    if peak > MAX_TRUE_PEAK_DBTP:
        raise ProductionAudioQualityError(
            "true_peak_too_high", f"True peak must not exceed {MAX_TRUE_PEAK_DBTP:g} dBTP"
        )
    return {"integrated_lufs": integrated, "true_peak_dbtp": peak}


def measure_video_loudness(video: Path) -> dict[str, float]:
    try:
        available = video.is_file() and video.stat().st_size > 0
    except OSError:
        available = False
    if not available:
        raise ProductionAudioQualityError("missing_video", "Final delivery video is missing or empty")
    command = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-map", "0:a:0",
        "-vn", "-sn", "-dn", "-af", "loudnorm=I=-14:TP=-2:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            command, shell=False, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
    except FileNotFoundError as exc:
        raise ProductionAudioQualityError("ffmpeg_unavailable", "FFmpeg is required for audio analysis") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProductionAudioQualityError("analysis_failed", "FFmpeg audio analysis did not complete") from exc
    if result.returncode:
        # FFmpeg's diagnostic text can contain absolute paths or media metadata;
        # never place that raw text in the public quality report.
        raise ProductionAudioQualityError("analysis_failed", "FFmpeg could not measure final audio")
    return parse_loudness_analysis(result.stderr)


def check_production_audio(
    manifest_path: Path, *, repository_root: Path | None = None
) -> dict[str, Any]:
    """Return publishable readings for every episode; keep private paths out."""
    try:
        manifest = load_production_batch_manifest(manifest_path, repository_root=repository_root)
    except (OSError, ValueError) as exc:
        raise ProductionAudioQualityError("invalid_manifest", "Production manifest failed path/schema validation") from exc
    episodes: list[dict[str, Any]] = []
    for episode in manifest.episodes:
        reading: dict[str, Any] = {"id": episode.id}
        try:
            readings = measure_video_loudness(episode.output)
            reading.update(readings)
            validate_loudness(readings)
            reading["status"] = "verified"
        except ProductionAudioQualityError as exc:
            reading.update(status="failed", error={"code": exc.code, "message": str(exc)})
        episodes.append(reading)
    return {
        "schema_version": 1,
        "batch_id": manifest.batch_id,
        "status": "verified" if all(item["status"] == "verified" for item in episodes) else "failed",
        "limits": {
            "min_integrated_lufs": MIN_INTEGRATED_LUFS,
            "max_integrated_lufs": MAX_INTEGRATED_LUFS,
            "max_true_peak_dbtp": MAX_TRUE_PEAK_DBTP,
        },
        "episodes": episodes,
    }
