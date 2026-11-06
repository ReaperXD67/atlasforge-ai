"""Render compiled editorial audio cues, including measured speech ducking.

This is an offline mixer, not a music or voice generator. Source audio is decoded
without tempo or pitch changes; cue envelopes and one measured master gain are applied.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from daily_video_factory.edit_plan import validate_edit_plan_bundle

SAMPLE_RATE = 48_000


def gain_samples(points: list[dict[str, Any]], frames: np.ndarray) -> np.ndarray:
    positions = np.array([p["frame"] for p in points], dtype=np.float64)
    values = np.array([p["gain_db"] for p in points], dtype=np.float64)
    if len(points) < 2 or not np.all(np.diff(positions) > 0):
        raise ValueError("Audio envelope points must be strictly ordered")
    if not np.isfinite(values).all() or not np.isfinite(frames).all():
        raise ValueError("Audio envelope must be finite")
    return np.power(10, np.interp(frames, positions, values) / 20).astype(np.float32)


def _ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run([_ffmpeg(), "-hide_banner", "-nostdin", *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-3000:])
    return result


def _measurement(stderr: bytes) -> dict[str, Any]:
    text = stderr.decode("utf-8", errors="replace")
    start, end = text.rfind("{"), text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("FFmpeg returned no loudness measurement")
    value = json.loads(text[start:end + 1])
    if value.get("input_i") in {"-inf", "inf"}:
        raise ValueError("The master is silent or invalid")
    return value


def mix_project_audio(project: Path) -> dict[str, Any]:
    project = project.resolve()
    audit = validate_edit_plan_bundle(project / "EDIT_PLAN.json")
    if not audit.passed:
        raise ValueError("The edit plan did not pass its declared editorial checks")
    plan = json.loads((project / "EDIT_PLAN.compiled.json").read_text(encoding="utf-8"))
    fps = plan["fps"]
    count = round(plan["duration_frames"] / fps * SAMPLE_RATE)
    master = np.zeros((count, 2), dtype=np.float32)
    sources = []
    for cue in plan["audio"]:
        source = (project / cue["asset"]).resolve()
        source.relative_to(project)
        start = round(cue["start_frame"] / fps * SAMPLE_RATE)
        end = round(cue["end_frame"] / fps * SAMPLE_RATE)
        length = end - start
        decoded = _run([
            "-ss", str(cue["source_start_frame"] / fps), "-i", str(source),
            "-t", str(length / SAMPLE_RATE), "-vn", "-ar", str(SAMPLE_RATE),
            "-ac", "2", "-f", "f32le", "pipe:1",
        ]).stdout
        audio = np.frombuffer(decoded, dtype="<f4").reshape(-1, 2)
        if len(audio) < length - SAMPLE_RATE / fps - 1:
            raise ValueError(f"Source {cue['id']} is shorter than its edit cue; no silent looping")
        if not np.isfinite(audio).all():
            raise ValueError(f"Nonfinite samples in {cue['id']}")
        available = min(length, len(audio))
        frames = cue["start_frame"] + np.arange(available, dtype=np.float64) * fps / SAMPLE_RATE
        master[start:start + available] += audio[:available] * gain_samples(cue["gain_envelope"], frames)[:, None]
        sources.append({"id": cue["id"], "role": cue["role"], "asset": cue["asset"],
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "start_frame": cue["start_frame"], "end_frame": cue["end_frame"]})
    destination = project / "assets/audio"
    destination.mkdir(parents=True, exist_ok=True)
    import wave
    # Floating-point intermediates preserve headroom instead of clipping the mix.
    raw = destination / "master-unlimited.f32"
    raw.write_bytes(master.astype("<f4").tobytes())
    args = ["-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "2", "-i", str(raw)]
    measured = _measurement(_run([*args, "-af", "loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"]).stderr)
    filt = ("loudnorm=I=-16:TP=-1.5:LRA=9:linear=true:print_format=json:"
            f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
            f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
            f"offset={measured['target_offset']}")
    output = destination / "master.wav"
    normalized = _measurement(_run(["-y", *args, "-af", filt, "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(output)]).stderr)
    # Delete only this exact temporary file inside this project's audio directory.
    raw.unlink()
    with wave.open(str(output), "rb") as wav:
        actual_frames, channels, rate = wav.getnframes(), wav.getnchannels(), wav.getframerate()
    if abs(actual_frames - count) > 2 or channels != 2 or rate != SAMPLE_RATE:
        raise ValueError("Final mix duration or format disagrees with the compiled edit")
    receipt = {"schema_version": 1, "sample_rate": rate, "channels": channels,
               "compiled_plan_sha256": hashlib.sha256((project / "EDIT_PLAN.compiled.json").read_bytes()).hexdigest(),
               "samples": actual_frames, "duration_seconds": actual_frames / rate,
               "sources": sources, "before_normalization": measured,
               "normalization": normalized, "master_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
               "subjective_listening_verified": False, "voice_emotion_verified": False}
    (project / "AUDIO_MIX.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt
