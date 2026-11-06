from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from daily_video_factory.voice_direction import VoiceBeat, VoiceDirection


@pytest.fixture
def pilot(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """No optional audio packages or models are needed for preparation regressions."""
    stored: dict = {}
    soundfile = ModuleType("soundfile")
    soundfile.write = lambda path, samples, rate, **kwargs: stored.update(
        {Path(path): (np.asarray(samples).copy(), rate)}
    )
    soundfile.read = lambda path, **kwargs: stored[Path(path)]
    monkeypatch.setitem(sys.modules, "soundfile", soundfile)
    path = Path(__file__).resolve().parents[1] / "scripts/prepare_pilot_batch.py"
    spec = importlib.util.spec_from_file_location("pilot_preparation_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "generate_original_music", lambda *args, **kwargs: None)
    return SimpleNamespace(module=module, stored=stored)


def test_missed_name_cannot_occupy_preceding_silent_pause(pilot: SimpleNamespace) -> None:
    plan = VoiceDirection(beats=[VoiceBeat(text="Hello."), VoiceBeat(text="Mira speaks.")])
    words = [
        {"text": "Hello.", "start": .1, "end": .8},
        {"text": "Mira", "start": .8, "end": 1.4},
        {"text": "speaks.", "start": 1.4, "end": 1.9},
    ]
    performance = {"sample_rate": 100, "beats": [
        {"start_sample": 0, "speech_samples": 100},
        {"start_sample": 120, "speech_samples": 100},
    ]}
    corrected, count = pilot.module.constrain_word_anchors(words, plan, performance)
    assert count == 1
    assert corrected[1] == {"text": "Mira", "start": 1.2, "end": 1.4}
    assert words[1]["start"] == .8  # The raw evidence remains available to callers.
    assert corrected[2] == words[2]


def test_impossible_timing_fails_instead_of_inventing_even_spacing(pilot: SimpleNamespace) -> None:
    plan = VoiceDirection(beats=[VoiceBeat(text="Hello.")])
    with pytest.raises(ValueError, match="entirely outside"):
        pilot.module.constrain_word_anchors(
            [{"text": "Hello.", "start": 2, "end": 3}], plan,
            {"sample_rate": 100, "beats": [{"start_sample": 0, "speech_samples": 100}]},
        )
    with pytest.raises(ValueError, match="word counts"):
        pilot.module.constrain_word_anchors([], plan, {"sample_rate": 100, "beats": []})


def test_mix_pads_filter_drain_without_changing_existing_audio(
    pilot: SimpleNamespace, tmp_path: Path
) -> None:
    original = np.full((46400, 2), .125, dtype=np.float32)

    def fake_ffmpeg(args: list[str]) -> None:
        pilot.stored[Path(args[-1])] = (original, 48000)

    pilot.module.make_mix(tmp_path, [], 1.0, SimpleNamespace(run=fake_ffmpeg))
    mixed, rate = pilot.stored[tmp_path / "final_mix.wav"]
    assert rate == 48000 and mixed.shape == (48000, 2)
    assert np.array_equal(mixed[:46400], original)
    assert np.count_nonzero(mixed[46400:]) == 0


def test_mix_refuses_to_truncate_overlong_output(pilot: SimpleNamespace, tmp_path: Path) -> None:
    def fake_ffmpeg(args: list[str]) -> None:
        pilot.stored[Path(args[-1])] = (np.zeros((48200, 2), dtype=np.float32), 48000)

    with pytest.raises(ValueError, match="duration differs"):
        pilot.module.make_mix(tmp_path, [], 1.0, SimpleNamespace(run=fake_ffmpeg))


def test_shot_anchor_missing_from_transcript_is_an_error(pilot: SimpleNamespace) -> None:
    with pytest.raises(ValueError, match="No measured speech anchor"):
        pilot.module.phrase_time([{"text": "Existing.", "start": 1}], "Invented")
