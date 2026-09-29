from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field


class PresenterExpression(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    file: Path
    triggers: list[str] = Field(default_factory=list)
    description: str = ""


class PresenterExpressionManifest(BaseModel):
    version: int = 1
    character: str = "Nexa"
    default: str = "neutral"
    minimum_hold_seconds: float = Field(default=5.0, ge=1.0, le=30.0)
    expressions: list[PresenterExpression]


@dataclass(frozen=True)
class ExpressionCue:
    start_seconds: float
    end_seconds: float
    expression: str


class PresenterExpressionLibrary:
    """Load and deterministically select static presenter expressions.

    Selection intentionally uses a small keyword map instead of a model call. That keeps recurring
    presenter decisions fast, cheap, reproducible, and available offline.
    """

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path.resolve()
        raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.manifest = PresenterExpressionManifest.model_validate(raw)
        self._by_name = {item.name.casefold(): item for item in self.manifest.expressions}
        if self.manifest.default.casefold() not in self._by_name:
            raise ValueError(
                f"Default presenter expression {self.manifest.default!r} is missing from the manifest"
            )

    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.manifest.expressions)

    def resolve(self, name: str | None = None) -> Path:
        key = (name or self.manifest.default).strip().casefold()
        item = self._by_name.get(key) or self._by_name[self.manifest.default.casefold()]
        path = item.file
        if not path.is_absolute():
            path = self.manifest_path.parent / path
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Presenter expression asset is missing: {resolved}")
        return resolved

    def choose(self, *text_values: str, preferred: str | None = None) -> str:
        if preferred and preferred.strip().casefold() in self._by_name:
            return self._by_name[preferred.strip().casefold()].name
        text = " ".join(text_values).casefold()
        tokens = set(re.findall(r"[a-z0-9]+", text))
        best_name = self.manifest.default
        best_score = 0
        for item in self.manifest.expressions:
            score = 0
            for trigger in item.triggers:
                trigger_tokens = set(re.findall(r"[a-z0-9]+", trigger.casefold()))
                if trigger_tokens and trigger_tokens.issubset(tokens):
                    score += max(1, len(trigger_tokens))
            if score > best_score:
                best_name = item.name
                best_score = score
        return best_name

    def plan_cues(
        self,
        requested: list[tuple[float, str]],
        *,
        total_duration_seconds: float,
        minimum_hold_seconds: float | None = None,
    ) -> list[ExpressionCue]:
        """Coalesce expression requests so static images never flash unnaturally.

        Requests closer than the hold threshold are delayed to the threshold. The final cue always
        extends to the end of the scene/video.
        """

        if total_duration_seconds <= 0:
            return []
        hold = minimum_hold_seconds or self.manifest.minimum_hold_seconds
        normalized: list[tuple[float, str]] = []
        for start, name in sorted(requested, key=lambda item: item[0]):
            if start < 0 or start >= total_duration_seconds:
                continue
            resolved_name = self._by_name.get(name.casefold())
            canonical = resolved_name.name if resolved_name else self.manifest.default
            if normalized and canonical == normalized[-1][1]:
                continue
            if normalized and start - normalized[-1][0] < hold:
                start = normalized[-1][0] + hold
                if start >= total_duration_seconds:
                    continue
            normalized.append((start, canonical))
        if not normalized or normalized[0][0] > 0:
            normalized.insert(0, (0.0, self.manifest.default))
        return [
            ExpressionCue(
                start_seconds=start,
                end_seconds=(
                    normalized[index + 1][0]
                    if index + 1 < len(normalized)
                    else total_duration_seconds
                ),
                expression=name,
            )
            for index, (start, name) in enumerate(normalized)
        ]
