import pytest

from daily_video_factory.exceptions import ConfigurationError
from daily_video_factory.viral_video import compile_viral_prompt


def test_beat_creature_prompt_locks_identity_and_bpm() -> None:
    prompt = compile_viral_prompt(
        "beat_creature",
        "A ginger cat dances on a glossy pit-lane floor",
        seconds=8,
        bpm=128,
    )
    assert "128.0 BPM" in prompt
    assert "Preserve the exact identity" in prompt
    assert "No cuts" in prompt


def test_talking_duo_requires_both_exact_lines() -> None:
    with pytest.raises(ConfigurationError, match="one short line for each speaker"):
        compile_viral_prompt(
            "talking_duo",
            "Two fictional babies exchange a playful joke",
            seconds=6,
            dialogue_a="Did you bring the snacks?",
        )


def test_physics_prompt_forbids_real_disaster_framing() -> None:
    prompt = compile_viral_prompt(
        "physics_spectacle",
        "A futuristic empty parking structure folds inward",
        seconds=7,
    )
    assert "No people" in prompt
    assert "real landmarks" in prompt
    assert "real disaster" in prompt
