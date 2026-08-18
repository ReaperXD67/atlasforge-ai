from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OWNED_VISUAL_MODES = frozenset(
    {"information_card", "kinetic_statement", "step_card", "proof_card", "comparison_card"}
)


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    failed = "failed"
    ready = "ready"
    published = "published"


class StageStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    skipped = "skipped"
    failed = "failed"


class ResearchItem(BaseModel):
    title: str
    source: str
    url: str | None = None
    score: float = 0
    rationale: str = ""
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceSource(BaseModel):
    title: str
    url: str
    checked_on: date
    summary: str


class ResearchReport(BaseModel):
    query_date: date
    candidates: list[ResearchItem]
    selected_title: str
    selected_angle: str
    brand_focused: bool = False
    evidence: list[EvidenceSource] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)


class ScriptDocument(BaseModel):
    title: str
    hook: str
    body: list[str]
    cta: str
    full_text: str
    word_count: int
    estimated_minutes: float
    facts_to_verify: list[str] = Field(default_factory=list)
    disclosures: list[str] = Field(default_factory=list)
    brand_focused: bool = False
    source_urls: list[str] = Field(default_factory=list)
    provider: str

    @field_validator("word_count")
    @classmethod
    def positive_word_count(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("word_count must be positive")
        return value


class Scene(BaseModel):
    index: int
    duration_seconds: float = Field(ge=2, le=60)
    narration: str
    camera_angle: str = "medium shot"
    environment: str = "editorial studio"
    character_description: str = "diverse adult professional"
    emotion: str = "thoughtful"
    lighting: str = "soft cinematic daylight"
    sound_effects: list[str] = Field(default_factory=list)
    transition: str = "crossfade"
    video_prompt: str
    visual_search_query: str
    visual_exclusion_terms: list[str] = Field(default_factory=list)
    onscreen_title: str = ""
    visual_mode: str = "documentary_broll"
    premium_score: float = Field(default=0, ge=0, le=1)
    selected_video_provider: str = "local_motion"
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    reference_image: Path | None = None
    generation_seed: int | None = Field(default=None, ge=0, le=18446744073709551615)
    generation_task: Literal["text_to_video", "image_to_video", "reference_to_video"] = (
        "text_to_video"
    )
    ai_generation_required: bool = False
    ai_generation_reason: str = ""


class Storyboard(BaseModel):
    title: str
    total_duration_seconds: float
    scenes: list[Scene]
    provider: str


class SubtitleCue(BaseModel):
    index: int
    start_seconds: float
    end_seconds: float
    text: str


class VideoMetadata(BaseModel):
    title: str = Field(max_length=100)
    description: str = Field(max_length=5000)
    tags: list[str] = Field(max_length=30)
    hashtags: list[str] = Field(max_length=15)
    chapters: list[str]
    thumbnail_text: str = Field(max_length=70)
    category_id: str = "27"


class CostEntry(BaseModel):
    stage: str
    provider: str
    estimated_usd: float = Field(ge=0)
    actual_usd: float | None = Field(default=None, ge=0)
    note: str = ""


class RunManifest(BaseModel):
    run_id: str
    publication_date: date
    status: RunStatus
    pipeline_kind: Literal["narrated", "music_film", "viral_short"] = "narrated"
    topic: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    current_stage: str = "created"
    output_root: Path
    final_video: Path | None = None
    thumbnail: Path | None = None
    youtube_video_id: str | None = None
    costs: list[CostEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
