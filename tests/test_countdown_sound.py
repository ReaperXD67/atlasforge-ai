"""Contract tests for the original countdown sound, without a model or paid media."""
from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path

import numpy as np
import pytest


def module():
    path = Path(__file__).parents[1] / "scripts" / "synthesize_countdown_sound.py"
    spec = importlib.util.spec_from_file_location("countdown_sound", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def source(project: Path):
    words = []
    for start, phrase in [(2, "Ten seconds"), (5, "My hand"), (7, "Then I stopped"),
                          (10, "Was I choosing"), (11, "or escaping"),
                          (13, "I let the numbers"), (16, "The clock"),
                          (18, "I still needed")]:
        for index, word in enumerate(phrase.split()):
            words.append({"text": word, "start": start + index * .1,
                          "end": start + index * .1 + .08})
    (project / "assets" / "audio").mkdir(parents=True)
    (project / "timing.json").write_text(json.dumps({"duration_seconds": 20, "words": words}))


def read_audio(path: Path):
    with wave.open(str(path)) as stream:
        assert (stream.getnchannels(), stream.getframerate(), stream.getsampwidth()) == (2, 48000, 2)
        return np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").reshape(-1, 2)


def test_sound_has_exact_duration_hush_audible_bookends_and_reproducible_bytes(tmp_path):
    source(tmp_path)
    synth = module()
    first = synth.synthesize(tmp_path)
    saved = [(tmp_path / row["asset"]).read_bytes() for row in first["files"]]
    for row in first["files"]:
        samples = read_audio(tmp_path / row["asset"])
        assert len(samples) == 20 * 48000
        assert np.any(samples[:6 * 48000]) and np.any(samples[12 * 48000:])
        assert not np.any(samples[round(7.05 * 48000):round(7.65 * 48000)])
        assert np.max(np.abs(samples.astype(np.int32))) < 32767
    second = synth.synthesize(tmp_path)
    assert first == second
    assert saved == [(tmp_path / row["asset"]).read_bytes() for row in second["files"]]


def test_ambiguous_or_missing_phrase_fails_instead_of_guessing_timing():
    synth = module()
    words = [{"text": "Ten", "start": 1}, {"text": "seconds", "start": 1.2}]
    assert synth.anchor(words, "Ten seconds") == 1
    with pytest.raises(ValueError, match="occur once"):
        synth.anchor(words * 2, "Ten seconds")
    with pytest.raises(ValueError, match="occur once"):
        synth.anchor(words, "The clock")
