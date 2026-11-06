"""Real FFmpeg mixer tests using original, procedural test tones only.

These temporary signals are test fixtures under the repository license; they are
not music, cloned voices, third-party recordings or delivered creative assets.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import wave
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_edit_plan import fixture_data

from daily_video_factory import cinematic_audio
from daily_video_factory.edit_plan import EditPlanError, compile_project_edit_plan


def _write_tone(path: Path, seconds: float, frequency: float, amplitude: float,
                *, sample_rate: int = 44100) -> None:
    time = np.arange(round(seconds * sample_rate), dtype=np.float64) / sample_rate
    # Slow envelope adds measurable level variation while retaining silence-free
    # integration windows. Generated purely for tests, with no copied material.
    envelope = 0.65 + 0.25 * np.cos(2 * np.pi * 0.7 * time)
    values = amplitude * envelope * np.sin(2 * np.pi * frequency * time)
    pcm = np.rint(values * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        wav.writeframes(pcm.tobytes())


@pytest.fixture
def real_audio_project(tmp_path: Path) -> Path:
    if not shutil.which("ffmpeg"):
        pytest.skip("Local FFmpeg unavailable")
    raw, timing = fixture_data()
    timing["duration_seconds"] = 7.2
    for word in timing["words"]:
        word["start"] /= 5
        word["end"] /= 5
    assets = tmp_path / "assets"
    assets.mkdir()
    for i in range(4):
        (assets / f"plate-{i}.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    for role, frequency, amplitude in [("voice", 310, 0.24), ("music", 701, 0.08), ("ambience", 997, 0.04)]:
        _write_tone(assets / f"{role}.wav", 7.2, frequency, amplitude)
    (tmp_path / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    (tmp_path / "EDIT_PLAN.json").write_text(json.dumps(raw), encoding="utf-8")
    compile_project_edit_plan(tmp_path / "EDIT_PLAN.json")
    return tmp_path


@pytest.mark.integration
def test_real_two_pass_mix_preserves_clock_and_binds_receipt(real_audio_project: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    original_run = cinematic_audio._run

    def observed_run(args: list[str]) -> Any:
        calls.append(args.copy())
        return original_run(args)

    # Observe commands while still running every decode/measurement/normalization.
    monkeypatch.setattr(cinematic_audio, "_run", observed_run)
    receipt = cinematic_audio.mix_project_audio(real_audio_project)
    filters = [args[args.index("-af") + 1] for args in calls if "-af" in args]
    assert len(filters) == 2
    assert "measured_I=" not in filters[0]
    assert "measured_I=" in filters[1] and "linear=true" in filters[1]
    assert "measured_TP=" in filters[1] and "offset=" in filters[1]
    assert len([args for args in calls if "pipe:1" in args]) == 3
    master = real_audio_project / "assets/audio/master.wav"
    with wave.open(str(master), "rb") as wav:
        assert (wav.getnchannels(), wav.getframerate(), wav.getsampwidth()) == (2, 48000, 2)
        assert wav.getnframes() == 345600
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    assert np.max(np.abs(samples.astype(np.int32))) < 32767
    assert np.sqrt(np.mean((samples.astype(np.float64) / 32768) ** 2)) > 0.01
    assert abs(float(receipt["normalization"]["output_i"]) + 16) <= 0.5
    assert float(receipt["normalization"]["output_tp"]) <= -1.4
    assert receipt["duration_seconds"] == 7.2
    assert receipt["samples"] == 345600
    assert receipt["master_sha256"] == hashlib.sha256(master.read_bytes()).hexdigest()
    assert receipt["compiled_plan_sha256"] == hashlib.sha256((real_audio_project / "EDIT_PLAN.compiled.json").read_bytes()).hexdigest()
    assert {s["role"] for s in receipt["sources"]} == {"voice", "music", "ambience"}
    for source in receipt["sources"]:
        assert source["sha256"] == hashlib.sha256((real_audio_project / source["asset"]).read_bytes()).hexdigest()
    assert json.loads((real_audio_project / "AUDIO_MIX.json").read_text()) == receipt
    assert not receipt["subjective_listening_verified"] and not receipt["voice_emotion_verified"]
    assert not (real_audio_project / "assets/audio/master-unlimited.f32").exists()


@pytest.mark.integration
def test_real_mixer_rejects_source_shorter_than_its_cue(real_audio_project: Path) -> None:
    _write_tone(real_audio_project / "assets/music.wav", 0.2, 701, 0.08)
    # Recompile honestly binds the shortened media; length enforcement is the
    # mixer's job rather than a failure caused only by a stale asset hash.
    compile_project_edit_plan(real_audio_project / "EDIT_PLAN.json")
    with pytest.raises(ValueError, match="shorter than its edit cue"):
        cinematic_audio.mix_project_audio(real_audio_project)
    assert not (real_audio_project / "AUDIO_MIX.json").exists()
    assert not (real_audio_project / "assets/audio/master.wav").exists()


def test_stale_source_fails_before_any_decode(real_audio_project: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    _write_tone(real_audio_project / "assets/voice.wav", 7.2, 320, 0.24)
    calls = []
    monkeypatch.setattr(cinematic_audio, "_run", lambda args: calls.append(args))
    with pytest.raises(EditPlanError, match="Stale"):
        cinematic_audio.mix_project_audio(real_audio_project)
    assert calls == []
