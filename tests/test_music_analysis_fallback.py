import json
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

from daily_video_factory.music_analysis_fallback import (
    analyze_music_fallback,
    analyze_waveform_fallback,
)


def pulse_train(sample_rate: int = 8_000, duration: float = 12) -> np.ndarray:
    samples = np.zeros(int(sample_rate * duration))
    pulse = np.hanning(160) * np.sin(2 * np.pi * 160 * np.arange(160) / sample_rate)
    for start in np.arange(0.25, duration - 0.1, 0.5):
        index = int(start * sample_rate)
        samples[index : index + len(pulse)] += pulse
    return samples


def test_repeated_pulses_have_deterministic_estimated_tempo_and_measured_energy() -> None:
    samples = pulse_train()
    first = analyze_waveform_fallback(samples, 8_000)
    second = analyze_waveform_fallback(samples, 8_000)

    assert json.dumps(first, allow_nan=False) == json.dumps(second, allow_nan=False)
    # A metrical half-time reading is also valid; no downbeat confidence is invented.
    assert min(abs(first["bpm"] - 120), abs(first["bpm"] - 60)) < 2
    assert first["beat_grid_estimated"] is True
    assert first["is_rhythmic"] is True
    assert first["downbeats_seconds"] == []
    assert first["downbeat_confidence"] == 0
    assert "not_probability" in first["confidence_kind"]
    assert len(first["onsets_seconds"]) >= 20
    assert max(point["energy"] for point in first["energy_curve"]) > 0.8


def test_silence_does_not_invent_beats_or_tempo() -> None:
    report = analyze_waveform_fallback(np.zeros((80_000, 2)), 8_000)

    assert report["duration_seconds"] == 10
    assert report["bpm"] is None
    assert report["beats_seconds"] == report["onsets_seconds"] == []
    assert report["rhythm_confidence"] == 0
    assert report["is_rhythmic"] is False
    assert all(point["energy"] == 0 for point in report["energy_curve"])
    json.dumps(report, allow_nan=False)


def test_sustained_tone_does_not_imply_a_musical_beat_grid() -> None:
    sample_rate = 8_000
    tone = np.sin(2 * np.pi * 440 * np.arange(sample_rate * 10) / sample_rate)

    report = analyze_waveform_fallback(tone, sample_rate)

    assert report["bpm"] is None
    assert report["beats_seconds"] == []
    assert report["is_rhythmic"] is False


@pytest.mark.parametrize(
    "samples",
    [
        np.ones(1),
        np.ones(73),
        pulse_train(duration=4),
        pulse_train(duration=4) * 1e300,
    ],
)
def test_valid_inputs_produce_finite_bounded_values_and_times(samples: np.ndarray) -> None:
    report = analyze_waveform_fallback(samples, 8_000)
    duration = len(samples) / 8_000

    json.dumps(report, allow_nan=False)
    assert report["duration_seconds"] == duration
    assert 0 <= report["rhythm_confidence"] <= 1
    for field in ["beats_seconds", "onsets_seconds"]:
        assert report[field] == sorted(set(report[field]))
        assert all(0 <= t <= duration for t in report[field])
    for point in report["energy_curve"]:
        assert 0 <= point["time_seconds"] <= duration
        assert all(0 <= point[key] <= 1 for key in ["energy", "onset_strength", "bass_energy"])
    assert all(0 <= point["time_seconds"] <= duration for point in report["key_moments"])


@pytest.mark.parametrize("samples", [np.array([]), np.array([np.nan]), np.array([np.inf])])
def test_invalid_audio_is_rejected(samples: np.ndarray) -> None:
    with pytest.raises(ValueError):
        analyze_waveform_fallback(samples, 8_000)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is not installed")
def test_file_decode_preserves_timing_origin_and_duration(tmp_path: Path) -> None:
    sample_rate = 8_000
    samples = pulse_train(duration=5)
    samples[:sample_rate] = 0
    track = tmp_path / "leading-silence.wav"
    with wave.open(str(track), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes((samples * 30_000).astype("<i2").tobytes())

    report = analyze_music_fallback(track, sample_rate=sample_rate)

    assert report["duration_seconds"] == 5
    assert report["onsets_seconds"][0] > 1
    assert report["energy_curve"][0]["energy"] == 0
