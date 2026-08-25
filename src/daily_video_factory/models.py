from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OWNED_VISUAL_MODES = frozenset(
    {"information_card", "kinetic_statement", "step_card", "proof_card", "comparison_card"}
)
MUSIC_EDIT_STYLES = frozenset(
    {
        "clean",
        "neon_strobe",
        "smoke_velocity",
        "luxury_noir",
        "flash_editorial",
        "pragon_neon",
    }
)
MusicEditStyle = Literal[
    "clean",
    "neon_strobe",
    "smoke_velocity",
    "luxury_noir",
    "flash_editorial",
    "pragon_neon",
]
MusicTreatment = Literal[
    "clean_hold",
    "neon_flash",
    "shutter_trail",
    "film_texture",
    "ember_resolve",
]
PerformerRole = Literal["none", "male_lead", "female_lead", "duet", "ensemble"]
PerformanceAction = Literal[
    "none",
    "lip_sync",
    "guitar",
    "dance",
    "smoking_closeup",
    "duet_performance",
    "friend_gathering",
    "car_action",
]


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
    title_variants: list[str] = Field(default_factory=list, max_length=3)
    thumbnail_text_options: list[str] = Field(default_factory=list, max_length=3)
    packaging_hypothesis: str = ""
    description_summary: str = Field(default="", max_length=600)
    chapter_titles: list[str] = Field(default_factory=list, max_length=6)
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


class MotionTextCue(BaseModel):
    """A short piece of export-safe typography tied to the scene-local edit clock."""

    time_seconds: float = Field(ge=0)
    duration_seconds: float = Field(default=0.55, ge=0.2, le=8)
    text: str = Field(min_length=1, max_length=96)
    style: Literal[
        "impact",
        "split",
        "outline",
        "stamp",
        "brand_neon",
        "brand_outro",
        "lyric_line",
        "lyric_whisper",
    ] = "impact"


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
    # Music-film edit metadata. Defaults keep narrated/viral storyboards backwards compatible.
    start_seconds: float = Field(default=0, ge=0)
    music_section: str = ""
    music_energy: float = Field(default=0.5, ge=0, le=1)
    music_pacing: Literal["beat_cut", "phrase_flow"] = "phrase_flow"
    edit_intent: str = ""
    source_inpoint_seconds: float | None = Field(default=None, ge=0)
    source_reframe_zoom: float = Field(default=1.0, ge=1.0, le=2.0)
    source_reframe_x: float = Field(default=0.5, ge=0, le=1)
    source_reframe_y: float = Field(default=0.5, ge=0, le=1)
    visual_direction: str = Field(default="", max_length=1200)
    music_edit_style: MusicEditStyle = "clean"
    music_treatment: MusicTreatment = "clean_hold"
    beat_accents_seconds: list[float] = Field(default_factory=list)
    motion_text_cues: list[MotionTextCue] = Field(default_factory=list)
    # Optional recurring-performer contract used by music films. Performer scenes are generated
    # from locked identity references and are never eligible for silent stock-person fallback.
    performer_role: PerformerRole = "none"
    performance_action: PerformanceAction = "none"
    performer_generation_required: bool = False
    performance_audio: Path | None = None
    performer_reference: Path | None = None
    performer_reference_secondary: Path | None = None
    lyric_section: str = ""
    lyric_singer: Literal["", "male", "female", "ensemble", "instrumental"] = ""
    lyric_text: str = Field(default="", max_length=300)


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
    title_variants: list[str] = Field(default_factory=list, max_length=3)
    description: str = Field(max_length=5000)
    tags: list[str] = Field(max_length=30)
    hashtags: list[str] = Field(max_length=15)
    chapters: list[str]
    thumbnail_text: str = Field(max_length=70)
    thumbnail_variants: list[str] = Field(default_factory=list, max_length=3)
    packaging_hypothesis: str = ""
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
