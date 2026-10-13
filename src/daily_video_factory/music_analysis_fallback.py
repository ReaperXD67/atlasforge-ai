"""Explicit, deterministic music analysis when the optional beat tracker cannot run.

Usage::

    report = analyze_music_fallback(Path("song.wav"))
    Path("audiomap.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

FFmpeg decodes the original track without trimming or changing its timing origin.
NumPy/SciPy then measure relative energy and spectral-flux onsets. Tempo and beat
times are estimates, not forced-alignment results; half/double-time ambiguity is
expected. ``rhythm_confidence`` is an autocorrelation score, not a probability.
No meter or downbeats are inferred. Call this helper explicitly: it does not
silently replace the main music analyzer or alter its dependency/security setup.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage, signal


def analyze_music_fallback(
    track: Path,
    *,
    ffmpeg_executable: str | None = None,
    sample_rate: int = 22_050,
) -> dict[str, Any]:
    """Decode an audio file and return a JSON-safe, explicitly estimated music map."""
    if sample_rate < 1_000:
        raise ValueError("sample_rate must be at least 1000 Hz")
    executable = ffmpeg_executable or os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")
    if not executable:
        raise FileNotFoundError("FFmpeg is required for fallback music analysis")
    result = subprocess.run(
        [
            executable,
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(track),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
        timeout=300,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace")[-1000:]
        raise RuntimeError(f"FFmpeg audio decode failed: {detail}")
    waveform = np.frombuffer(result.stdout, dtype="<f4")
    return analyze_waveform_fallback(waveform, sample_rate)


def analyze_waveform_fallback(
    waveform: np.ndarray,
    sample_rate: int,
    *,
    hop_length: int = 256,
) -> dict[str, Any]:
    """Analyze mono or frames-by-channels samples without a model download.

    Empty/non-finite inputs are rejected. Silence has no tempo or fabricated beat
    grid. The returned energy is relative to this recording, not an LUFS reading.
    Times are seconds from the first supplied sample and stay within its duration.
    """
    if sample_rate < 1_000:
        raise ValueError("sample_rate must be at least 1000 Hz")
    if not 1 <= hop_length <= 2048:
        raise ValueError("hop_length must be between 1 and 2048")
    samples = np.asarray(waveform, dtype=np.float64)
    if samples.ndim not in (1, 2) or not samples.size:
        raise ValueError("waveform must contain mono or frames-by-channels samples")
    if not np.isfinite(samples).all():
        raise ValueError("waveform must contain only finite samples")
    duration = len(samples) / sample_rate
    # Scale before channel mixing/FFT to avoid overflow on finite high-gain inputs.
    peak = float(np.max(np.abs(samples)))
    samples = (
        (samples / peak).astype(np.float32)
        if peak > 1e-8
        else np.zeros_like(samples, dtype=np.float32)
    )
    if samples.ndim == 2:
        samples = samples.mean(axis=1)

    def timestamp(value: float) -> float:
        return min(duration, max(0.0, round(float(value), 6)))

    energy_times = np.arange(0.0, duration, 0.25)
    report: dict[str, Any] = {
        "schema_version": 1,
        "analysis_backend": "scipy_spectral_flux_fallback",
        "duration_seconds": duration,
        "bpm": None,
        "beat_grid_estimated": True,
        "rhythm_confidence": 0.0,
        "confidence_kind": "normalized_onset_autocorrelation_not_probability",
        "downbeat_confidence": 0.0,
        "is_rhythmic": False,
        "beats_seconds": [],
        "downbeats_seconds": [],
        "energy_curve": [],
        "onsets_seconds": [],
        "onset_strengths": [],
        "key_moments": [],
        "warnings": [
            "Tempo and beat positions are estimates; half/double-time ambiguity remains.",
            "Meter and downbeats were not measured. Prefer phrase pacing for sparse audio.",
        ],
    }
    if not np.any(samples):
        report["energy_curve"] = [
            {"time_seconds": timestamp(t), "energy": 0.0, "onset_strength": 0.0, "bass_energy": 0.0}
            for t in energy_times
        ]
        report["warnings"].append("No measurable audio energy; no beat grid was generated.")
        return report

    # Pad only the analysis window; timestamps still refer to the original samples.
    window = 2048
    padded = np.pad(samples, (0, window - len(samples))) if len(samples) < window else samples
    frequencies, times, spectrum = signal.stft(
        padded,
        fs=sample_rate,
        nperseg=window,
        noverlap=window - hop_length,
        boundary="zeros",
    )
    valid = times < duration
    times = times[valid]
    magnitude = np.abs(spectrum[:, valid])
    power = magnitude**2

    def normalize(values: np.ndarray) -> np.ndarray:
        scale = float(np.percentile(values, 99))
        if scale <= 1e-12:
            scale = float(np.max(values))
        return values / scale if scale > 1e-12 else np.zeros_like(values)

    energy = normalize(np.sqrt(power.sum(axis=0)))
    bass = normalize(np.sqrt(power[frequencies < 160].sum(axis=0)))
    compressed = np.log1p(magnitude * 100)
    flux = np.maximum(0.0, np.diff(compressed, axis=1, prepend=compressed[:, :1])).mean(axis=0)
    flux = np.maximum(0.0, flux - ndimage.median_filter(flux, size=45))
    envelope = ndimage.gaussian_filter1d(normalize(flux), 0.8)
    for t in energy_times:
        report["energy_curve"].append(
            {
                "time_seconds": timestamp(t),
                "energy": round(float(np.clip(np.interp(t, times, energy), 0, 1)), 6),
                "onset_strength": round(float(np.clip(np.interp(t, times, envelope), 0, 1)), 6),
                "bass_energy": round(float(np.clip(np.interp(t, times, bass), 0, 1)), 6),
            }
        )

    dt = hop_length / sample_rate
    onsets, _ = signal.find_peaks(
        envelope,
        height=0.12,
        prominence=0.10,
        distance=max(1, int(0.13 / dt)),
    )
    report["onsets_seconds"] = [timestamp(times[i]) for i in onsets]
    report["onset_strengths"] = [round(float(np.clip(envelope[i], 0, 1)), 6) for i in onsets]

    # Require multiple measured transients and several seconds of evidence.
    centered = envelope - envelope.mean()
    if duration >= 4 and len(onsets) >= 4 and np.dot(centered, centered) > 1e-12:
        autocorrelation = signal.correlate(centered, centered, mode="full", method="fft")
        autocorrelation = autocorrelation[len(centered) - 1 :]
        first = max(1, int(60 / 180 / dt))
        last = min(len(autocorrelation) - 2, int(60 / 55 / dt))
        if first <= last:
            lag = first + int(np.argmax(autocorrelation[first : last + 1]))
            confidence = float(np.clip(autocorrelation[lag] / autocorrelation[0], 0, 1))
            report["rhythm_confidence"] = round(confidence, 6)
            if confidence >= 0.15:
                denominator = (
                    autocorrelation[lag - 1] - 2 * autocorrelation[lag] + autocorrelation[lag + 1]
                )
                delta = (
                    0.5 * (autocorrelation[lag - 1] - autocorrelation[lag + 1]) / denominator
                    if abs(denominator) > 1e-12
                    else 0.0
                )
                period = (lag + float(np.clip(delta, -0.5, 0.5))) * dt
                phases = np.linspace(0, period, 400, endpoint=False)
                scores = [
                    float(np.mean(np.interp(np.arange(p, duration, period), times, envelope)))
                    for p in phases
                ]
                phase = float(phases[int(np.argmax(scores))])
                beats = []
                for predicted in np.arange(phase, duration, period):
                    nearby = np.flatnonzero(np.abs(times - predicted) < period * 0.12)
                    if len(nearby):
                        local = nearby[int(np.argmax(envelope[nearby]))]
                        # Silent regions keep the estimated grid instead of snapping arbitrarily.
                        beat = times[local] if envelope[local] >= 0.12 else predicted
                    else:
                        beat = predicted
                    beats.append(timestamp(beat))
                report["bpm"] = round(60 / period, 6)
                report["beats_seconds"] = sorted(set(beats))
                report["is_rhythmic"] = True

    if len(energy_times) >= 8:
        curve = np.array([point["energy"] for point in report["energy_curve"]])
        change = np.diff(ndimage.gaussian_filter1d(curve, 4), prepend=curve[0])
        changes, _ = signal.find_peaks(np.abs(change), height=0.025, distance=28)
        report["key_moments"] = [
            {
                "time_seconds": timestamp(energy_times[i]),
                "kind": "surge" if change[i] > 0 else "drop",
                "strength": round(float(np.clip(abs(change[i]) * 16, 0, 1)), 6),
            }
            for i in changes
        ]
    return report
