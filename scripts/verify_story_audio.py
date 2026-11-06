"""Measure the actual encoded mix and transcribe its measured spoken windows locally."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import correlate, correlation_lags, resample_poly

from daily_video_factory.cinematic_audio import _measurement
from daily_video_factory.story_delivery import verify_current_render
from daily_video_factory.story_pipeline import ROOT, PipelineError, local, read, sha, write


def alignment(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    a = resample_poly(a.mean(axis=1), 1, 12).astype("float64")
    b = resample_poly(b.mean(axis=1), 1, 12).astype("float64")
    if not len(a) or not len(b) or np.dot(a, a) <= 0 or np.dot(b, b) <= 0:
        raise PipelineError("Cannot align empty or silent verification audio")
    correlation = correlate(a, b, method="fft")
    lags = correlation_lags(len(a), len(b))
    allowed = np.abs(lags) <= 400
    lag = int(lags[allowed][np.argmax(correlation[allowed])])
    if lag >= 0:
        a = a[lag:]
    else:
        b = b[-lag:]
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    return {"lag_seconds": lag / 4000, "correlation": float(np.corrcoef(a, b)[0, 1])}


def portable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, str):
        for prefix in (str(ROOT), ROOT.as_posix()):
            if value.startswith(prefix):
                return value[len(prefix):].lstrip("/\\").replace("\\", "/")
        if re.search(r"[A-Za-z]:[/\\]|/(?:Users|home)/", value):
            raise PipelineError("ASR evidence contains an unexpected private path")
    return value


def verify(project: Path) -> dict[str, Any]:
    project = project.resolve()
    verified = verify_current_render(project)
    out = project / "qa/audio"
    out.mkdir(parents=True, exist_ok=True)
    video, digest = verified["video"], verified["video_sha256"]
    encoded = out / "encoded-final.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(video),
                    "-map", "0:a:0", "-vn", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(encoded)],
                   check=True, timeout=300)
    measurement = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-map", "0:a:0",
                                  "-af", "loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"],
                                 capture_output=True, check=True, timeout=300)
    loudness = _measurement(measurement.stderr)
    x, sr = sf.read(encoded, dtype="float32", always_2d=True)
    master_path = local(project, "assets/audio/master.wav")
    voice_path = local(project, "assets/audio/narration.wav")
    performance_path = local(project, "assets/audio/narration.performance.json")
    original_hashes = {str(p.relative_to(project).as_posix()): sha(p) for p in (master_path, voice_path, performance_path)}
    master, msr = sf.read(master_path, dtype="float32", always_2d=True)
    voice, vsr = sf.read(voice_path, dtype="float32", always_2d=True)
    if sr != 48000 or msr != sr or vsr != sr:
        raise PipelineError("Verification audio requires 48kHz sources")
    encoded_alignment, voice_alignment = alignment(x, master), alignment(master, voice)
    receipt, performance = read(local(project, "AUDIO_MIX.json")), read(performance_path)
    def normalize(text: str) -> list[str]:
        return re.findall(r"\w+(?:['’]\w+)*", text.lower().replace("’", "'"))

    if normalize(" ".join(t.get("caption_text", t["text"]) for t in performance["takes"])) != normalize(
            local(project, "script.txt").read_text(encoding="utf-8")):
        raise PipelineError("Measured performance windows must cover the complete approved transcript")
    voice_sources = [row for row in receipt["sources"] if row["role"] == "voice"]
    crops = []
    for index, take in enumerate(performance["takes"]):
        start = round((take["start_sample"] / performance["sample_rate"] + encoded_alignment["lag_seconds"]) * sr)
        end = start + round(take["speech_samples"] / performance["sample_rate"] * sr)
        if not 0 <= start < end <= len(x):
            raise PipelineError("Measured speech window escapes the encoded audio")
        path = out / f"take-{index:03d}.wav"
        sf.write(path, x[start:end], sr, subtype="PCM_16")
        crops.append({"id": take["id"], "mode": "final_mix", "text": take.get("caption_text", take["text"]),
                      "path": path.relative_to(ROOT).as_posix()})
    if not crops:
        raise PipelineError("Encoded speech QA requires measured take windows")
    write(out / "audition-report.json", {"schema_version": 1, "video_sha256": digest, "takes": crops})
    subprocess.run([sys.executable, str(ROOT / "scripts/inspect_voice_audition.py"), "--report",
                    str(out / "audition-report.json")], cwd=ROOT, check=True, timeout=1800)
    asr_path = out / "audition-independent-evidence.json"
    asr = portable(read(asr_path))
    write(asr_path, asr)
    result = {"schema_version": 1, "video_sha256": digest, "source_sha256": original_hashes,
        "encoded_audio_duration": len(x) / sr, "sample_rate": sr, "channels": x.shape[1],
        "integrated_lufs": float(loudness["input_i"]), "true_peak_dbtp": float(loudness["input_tp"]),
        "all_samples_finite": bool(np.isfinite(x).all()), "sample_peak": float(np.max(np.abs(x))),
        "clipped_sample_fraction": float(np.mean(np.abs(x) >= 0.9999)),
        "encoded_vs_master": encoded_alignment, "master_vs_voice": voice_alignment,
        "master_sha_matches_receipt": sha(master_path) == receipt["master_sha256"],
        "voice_sha_matches_receipt": len(voice_sources) == 1 and sha(voice_path) == voice_sources[0]["sha256"],
        "asr_pass_count": sum(t["normalized_asr_matches"] for t in asr["takes"]),
        "asr_total": len(asr["takes"]), "subjective_listening_verified": False, "voice_emotion_verified": False,
        "asr_mismatches": [{"id": t["id"], "expected": t["expected_text"], "actual": t["asr_transcript"]}
                           for t in asr["takes"] if not t["normalized_asr_matches"]]}
    result["technical_passed"] = all([result["master_sha_matches_receipt"], result["voice_sha_matches_receipt"],
        result["all_samples_finite"], result["clipped_sample_fraction"] == 0,
        -17 <= result["integrated_lufs"] <= -15, result["true_peak_dbtp"] <= -1,
        abs(encoded_alignment["lag_seconds"]) <= 0.02, encoded_alignment["correlation"] >= 0.98,
        abs(voice_alignment["lag_seconds"]) <= 0.02])
    result["asr_all_passed"] = result["asr_pass_count"] == result["asr_total"] == len(crops)
    if sha(video) != digest or any(sha(local(project, name)) != value for name, value in original_hashes.items()):
        raise PipelineError("Media changed during encoded audio QA")
    write(out / "encoded-audio-verification.json", result)
    if not result["technical_passed"] or not result["asr_all_passed"]:
        raise PipelineError("The actual encoded mix failed speech or technical checks")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.project)
    except Exception:
        print("Encoded audio QA failed. Check the local report and measured speech; no approval is claimed.")
        return 1
    print(f"[audio-qa] {result['asr_pass_count']}/{result['asr_total']} exact ASR windows; {result['integrated_lufs']:.2f}LUFS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
