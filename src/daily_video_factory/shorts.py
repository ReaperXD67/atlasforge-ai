from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .exceptions import ConfigurationError


def extract_hyperframes_narration(script_markdown: str) -> str:
    """Extract only the indented spoken blocks from a HyperFrames SCRIPT.md file."""
    blocks: list[str] = []
    current: list[str] = []
    for line in script_markdown.splitlines():
        if line.startswith("    ") and line.strip():
            current.append(line.strip())
            continue
        if current:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    narration = "\n\n".join(blocks).strip()
    if not narration:
        raise ConfigurationError("SCRIPT.md contains no indented spoken blocks")
    return narration


class ShortExperimentSpec(BaseModel):
    episode: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=10, max_length=100)
    aspect: str = "1080x1920"
    target_duration_seconds: float = Field(gt=0, le=180)
    hook_delivery_seconds: float = Field(gt=0, le=3)
    pattern_interrupt_seconds: float = Field(gt=0, le=8)
    loop_ending: bool = True
    hypothesis: str = Field(min_length=20, max_length=500)
    primary_metric: Literal[
        "engaged_views", "viewed_vs_swiped_away", "average_percentage_viewed"
    ]
    secondary_metrics: list[str] = Field(min_length=1, max_length=8)
    packaging: dict[str, str]
    success_thresholds: dict[str, float] = Field(min_length=1)
    sources: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_vertical_delivery(self) -> ShortExperimentSpec:
        match = re.fullmatch(r"(\d+)x(\d+)", self.aspect)
        if not match:
            raise ValueError("aspect must use WIDTHxHEIGHT")
        width, height = (int(value) for value in match.groups())
        if width >= height:
            raise ValueError("Shorts experiments must use a vertical canvas")
        return self


def build_short_experiment_manifest(spec: ShortExperimentSpec) -> dict[str, object]:
    """Create a deterministic measurement contract for a daily Shorts experiment."""
    return {
        "schema_version": 1,
        "episode": spec.episode,
        "youtube_short_eligible": spec.target_duration_seconds <= 180,
        "delivery": {
            "aspect": spec.aspect,
            "target_duration_seconds": spec.target_duration_seconds,
            "hook_delivery_seconds": spec.hook_delivery_seconds,
            "pattern_interrupt_seconds": spec.pattern_interrupt_seconds,
            "loop_ending": spec.loop_ending,
        },
        "hypothesis": spec.hypothesis,
        "packaging": spec.packaging,
        "measurement": {
            "primary_metric": spec.primary_metric,
            "secondary_metrics": spec.secondary_metrics,
            "success_thresholds": spec.success_thresholds,
            "checkpoints_hours": [24, 72],
            "comparison_basis": "previous BizNex upload of the same format",
        },
        "sources": spec.sources,
    }


def write_short_experiment_manifest(spec_path: Path, output_path: Path) -> Path:
    spec = ShortExperimentSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_short_experiment_manifest(spec), indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
