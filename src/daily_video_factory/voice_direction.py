"""Explicit narration direction kept separate from the spoken/caption transcript."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VoiceBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=600)
    emotion: Literal["neutral", "curious", "serious", "reassuring", "excited"] = "neutral"
    energy: float = Field(default=0.5, ge=0, le=1)
    pace: float = Field(default=1.0, ge=0.85, le=1.15)
    pause_after_ms: int = Field(default=180, ge=0, le=1500)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A voice beat must contain spoken text")
        return value.strip()

    def instruction(self) -> str:
        return (
            f"Delivery: {self.emotion}, energy {self.energy:.2f} on a 0 to 1 scale. "
            f"Speak at approximately {self.pace:.2f} times your natural pace. "
            "Keep the same speaker identity. Speak only the supplied transcript, "
            "without reading these directions or adding words."
        )


class VoiceDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    beats: list[VoiceBeat] = Field(min_length=1, max_length=100)

    @property
    def narration(self) -> str:
        return " ".join(beat.text for beat in self.beats)

    def validate_transcript(self, text: str) -> None:
        # Punctuation/case are intentional; only whitespace can differ.
        if " ".join(text.split()) != " ".join(self.narration.split()):
            raise ValueError("Voice direction must preserve the exact approved transcript")

    @classmethod
    def load(cls, path: Path) -> VoiceDirection:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def bounded_speech_chunks(text: str, max_chars: int) -> list[str]:
    """Prefer sentence boundaries, then words; never silently truncate narration."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    normalized = " ".join(text.split())
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?。！？।])\s+", normalized)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        # A long sentence must be broken on word boundaries, too.
        pieces = [sentence] if len(sentence) <= max_chars else sentence.split()
        for piece in pieces:
            if len(piece) > max_chars:
                raise ValueError("A single narration token exceeds the provider character limit")
            if current and len(current) + len(piece) + 1 > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks


def chatterbox_controls(beat: VoiceBeat, base_exaggeration: float) -> dict[str, float]:
    """Numeric approximations, not a claim that Chatterbox understands emotion labels."""
    offset = {
        "neutral": 0.0,
        "curious": 0.06,
        "serious": -0.12,
        "reassuring": -0.08,
        "excited": 0.15,
    }[beat.emotion]
    return {
        "exaggeration": min(1.1, max(0.25, base_exaggeration + offset + (beat.energy - 0.5) * 0.2)),
    }


def directed_speech_chunks(direction: VoiceDirection, max_chars: int) -> list[VoiceBeat]:
    """Split provider-sized inputs without adding pauses inside an authored beat."""
    result: list[VoiceBeat] = []
    for beat in direction.beats:
        chunks = bounded_speech_chunks(beat.text, max_chars)
        result.extend(
            beat.model_copy(
                update={
                    "text": chunk,
                    "pause_after_ms": beat.pause_after_ms if index == len(chunks) - 1 else 0,
                }
            )
            for index, chunk in enumerate(chunks)
        )
    return result
