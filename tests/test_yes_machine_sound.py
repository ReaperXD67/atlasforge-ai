"""Small real PCM fixtures verify authored synthesis, not a mocked render."""
import importlib.util
import json
import wave
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location(
    "yes_machine_sound", Path(__file__).parents[1] / "scripts/synthesize_yes_machine_sound.py"
)
sound = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sound)


def test_anchor_rejects_missing_and_repeated_phrases():
    words = [{"text": "yes", "start": 0, "end": .2}, {"text": "yes", "start": 1, "end": 1.2}]
    with pytest.raises(ValueError, match="occur once"):
        sound.anchor(words, "yes")
    with pytest.raises(ValueError, match="occur once"):
        sound.anchor(words, "not now")


def test_synthesis_is_deterministic_stereo_and_obeys_the_authored_hush(tmp_path):
    text = ("Saying yes One little yes Then the money The time The stuff So I tried "
            "I paused What does it cost Will I use it Does it fit my life Turns out")
    words = [{"text": value, "start": i * .28, "end": i * .28 + .18}
             for i, value in enumerate(text.split())]
    timing = {"duration_seconds": 14, "words": words}
    (tmp_path / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    first = sound.synthesize(tmp_path)
    before = [(tmp_path / row["asset"]).read_bytes() for row in first["files"]]
    second = sound.synthesize(tmp_path)
    assert first == second
    assert before == [(tmp_path / row["asset"]).read_bytes() for row in second["files"]]
    start, end = first["hush_seconds"]
    assert end > start
    for row in first["files"]:
        with wave.open(str(tmp_path / row["asset"]), "rb") as source:
            assert source.getnchannels() == 2
            assert source.getframerate() == 48_000
            assert source.getnframes() == 14 * 48_000
            pcm = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").reshape(-1, 2)
        assert np.max(np.abs(pcm.astype(np.int32))) < 32_767
        assert np.max(np.abs(pcm[:int(start * 48_000)])) > 0
        assert not pcm[int(np.ceil(start * 48_000)):int(end * 48_000)].any()


@pytest.mark.parametrize("sample", [float("nan"), float("inf"), 1.0, -1.0])
def test_pcm_writer_rejects_nonfinite_or_clipped_sound(tmp_path, sample):
    with pytest.raises(ValueError, match="invalid/clipped"):
        sound.write_wav(tmp_path / "invalid.wav", np.full((4, 2), sample))
    assert not (tmp_path / "invalid.wav").exists()
