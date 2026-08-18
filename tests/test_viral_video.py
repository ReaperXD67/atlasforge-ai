import pytest

from daily_video_factory.exceptions import ConfigurationError
from daily_video_factory.viral_video import (
    compile_reference_prompt,
    compile_viral_prompt,
    fallback_prompt_direction,
)


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


def test_cinematic_insert_prompt_prioritizes_rigid_reference_led_motion() -> None:
    prompt = compile_viral_prompt(
        "cinematic_insert",
        "A silver GT car rolls slowly through a wet pit lane",
        seconds=5,
    )

    assert "one subject and one simple subject or environmental action" in prompt
    assert "primary rigid subject may remain stationary" in prompt
    assert "Preserve exact bodywork" in prompt
    assert "Avoid spectacle" in prompt
    assert "No cuts" in prompt


def test_local_reference_prompt_starts_before_physics_action() -> None:
    prompt = compile_reference_prompt(
        "physics_spectacle", "An empty brutalist parking structure fails inward"
    )
    assert "intact" in prompt
    assert "no people, damage, dust, smoke, or debris yet" in prompt
    assert "clean first frame" in prompt


def test_fallback_direction_reduces_physics_to_one_event() -> None:
    direction = fallback_prompt_direction(
        "physics_spectacle", "A fictional parking structure folds inward"
    )

    assert "one localized brittle fracture" in direction.motion_direction
    assert "Locked wide tripod" in direction.camera_direction
    assert "rubbery concrete" in direction.realism_risks


def test_fallback_direction_caps_long_reference_queries() -> None:
    direction = fallback_prompt_direction(
        "cinematic_insert",
        "An extraordinarily detailed rain-slick reinforced-concrete motorsport paddock tunnel "
        "with atmospheric fluorescent reflections and a perfectly stationary locked camera",
    )

    assert len(direction.reference_query) <= 100
