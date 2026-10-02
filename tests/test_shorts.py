import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_video_factory.shorts import (
    ShortExperimentSpec,
    build_short_experiment_manifest,
    extract_hyperframes_narration,
    write_short_experiment_manifest,
)


def test_extract_hyperframes_narration_keeps_only_spoken_blocks() -> None:
    script = """# SCRIPT

**Voice:** Nexa

    First spoken line.

## Line 2

    Second spoken line,
    continued naturally.
"""
    assert extract_hyperframes_narration(script) == (
        "First spoken line.\n\nSecond spoken line, continued naturally."
    )


def test_short_experiment_rejects_landscape() -> None:
    with pytest.raises(ValidationError):
        ShortExperimentSpec(
            episode="video-003",
            title="A sufficiently useful title",
            aspect="1920x1080",
            target_duration_seconds=50,
            hook_delivery_seconds=1.2,
            pattern_interrupt_seconds=5,
            hypothesis="A strong curiosity gap should increase completed views.",
            primary_metric="average_percentage_viewed",
            secondary_metrics=["engaged_views"],
            packaging={"hook": "Half the packs"},
            success_thresholds={"average_percentage_viewed": 80},
            sources=["https://example.com/source"],
        )


def test_short_experiment_rejects_non_9x16_thumbnail() -> None:
    with pytest.raises(ValidationError, match="exact 9:16"):
        ShortExperimentSpec(
            episode="video-003",
            title="A sufficiently useful title",
            thumbnail_aspect="1000x1600",
            target_duration_seconds=50,
            hook_delivery_seconds=1.2,
            pattern_interrupt_seconds=5,
            hypothesis="A strong curiosity gap should increase completed views.",
            primary_metric="average_percentage_viewed",
            secondary_metrics=["engaged_views"],
            packaging={"hook": "Half the packs"},
            success_thresholds={"average_percentage_viewed": 80},
            sources=["https://example.com/source"],
        )


def test_short_manifest_is_deterministic_and_written(tmp_path: Path) -> None:
    payload = {
        "episode": "video-003",
        "title": "Half the packets but more PV",
        "target_duration_seconds": 52,
        "hook_delivery_seconds": 1.2,
        "pattern_interrupt_seconds": 5,
        "hypothesis": "A source-backed contradiction should improve retention.",
        "primary_metric": "average_percentage_viewed",
        "secondary_metrics": ["engaged_views", "viewed_vs_swiped_away"],
        "packaging": {"hook": "HALF THE PACKS. MORE PV?"},
        "success_thresholds": {"average_percentage_viewed": 80},
        "sources": ["https://example.com/source"],
        "voice": {"provider": "kokoro", "id": "af_heart", "speed": 1.06},
    }
    spec_path = tmp_path / "spec.json"
    output_path = tmp_path / "manifest.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")
    write_short_experiment_manifest(spec_path, output_path)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    direct = build_short_experiment_manifest(ShortExperimentSpec.model_validate(payload))
    assert written == direct
    assert written["youtube_short_eligible"] is True
    assert written["delivery"]["thumbnail_aspect"] == "1080x1920"
    assert written["measurement"]["checkpoints_hours"] == [24, 72]
    assert written["voice_lock"] == {
        "provider": "kokoro",
        "id": "af_heart",
        "speed": 1.06,
    }
