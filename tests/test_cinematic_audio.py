import numpy as np
import pytest

from daily_video_factory.cinematic_audio import gain_samples


def test_voice_ducking_applies_db_gain_without_changing_sample_timing():
    points = [{"frame": 0, "gain_db": 0}, {"frame": 3, "gain_db": -12},
              {"frame": 30, "gain_db": -12}, {"frame": 39, "gain_db": 0}]
    frame = np.arange(40, dtype=float)
    gain = gain_samples(points, frame)
    assert len(gain) == 40
    assert gain[0] == pytest.approx(1)
    assert gain[3] == pytest.approx(10 ** (-12 / 20))
    assert np.allclose(gain[3:31], gain[3])
    assert np.all(np.diff(gain[30:]) > 0)
    assert gain[39] == pytest.approx(1)


def test_mix_envelope_rejects_ambiguous_breakpoints():
    with pytest.raises(ValueError, match="strictly ordered"):
        gain_samples([{"frame": 2, "gain_db": 0}, {"frame": 2, "gain_db": -10}], np.array([2.]))


def test_mix_envelope_rejects_nonfinite_input():
    with pytest.raises(ValueError, match="finite"):
        gain_samples([{"frame": 0, "gain_db": float('nan')}, {"frame": 20, "gain_db": 0}], np.array([2.]))
