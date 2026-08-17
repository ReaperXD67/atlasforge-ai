from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from .exceptions import ConfigurationError


class ChannelConfig(BaseModel):
    name: str
    language: str = "en"
    region: str = "US"
    timezone: str = "UTC"
    brand_name: str = "Atomy"
    brand_required: bool = True
    content_goal: str = "Educational, evidence-aware long-form explainers"
    audience: list[str]
    disclosure: str


class ScheduleConfig(BaseModel):
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    upload_privacy: str = "private"
    publish_hour: int = Field(default=18, ge=0, le=23)
    catch_up_if_missed: bool = True


class OfficialSourceConfig(BaseModel):
    title: str
    url: str
    checked_on: date
    summary: str


class ResearchConfig(BaseModel):
    seed_topics: list[str]
    editorial_topics: list[str] = Field(default_factory=list)
    rotate_editorial_topics: bool = True
    official_sources: list[OfficialSourceConfig] = Field(default_factory=list)
    max_official_source_age_days: int = Field(default=90, ge=1)
    reddit_subreddits: list[str] = Field(default_factory=list)
    max_candidates: int = 40
    request_timeout_seconds: int = 15


class ScriptConfig(BaseModel):
    target_minutes: float = 7
    words_per_minute: int = 145
    min_words: int = 900
    max_words: int = 1150
    brand_mention_min_fraction: float = 0.55
    brand_mention_max_fraction: float = 0.85
    text_providers: list[str]
    openrouter_model: str
    gemini_model: str
    ollama_model: str


class StoryboardConfig(BaseModel):
    target_scene_seconds: int = 16
    min_scene_seconds: int = 8
    max_scene_seconds: int = 24
    max_scenes: int = 32


class VoiceConfig(BaseModel):
    providers: list[str]
    openai_model: str
    openai_voice: str
    openai_instructions: str
    gemini_model: str
    gemini_voice: str
    kokoro_voice: str
    kokoro_speed: float = Field(default=0.98, ge=0.75, le=1.25)
    kokoro_language: str = "a"
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_stability: float = Field(default=0.42, ge=0, le=1)
    elevenlabs_similarity_boost: float = Field(default=0.78, ge=0, le=1)
    elevenlabs_style: float = Field(default=0.22, ge=0, le=1)
    sample_rate: int = 24000
    target_lufs: int = -16
    max_duration_ratio: float = Field(default=1.18, ge=1.0, le=1.5)


class ImagesConfig(BaseModel):
    providers: list[str]
    width: int = 1920
    height: int = 1080
    pexels_orientation: str = "landscape"


class VideoConfig(BaseModel):
    width: int = 1920
    height: int = 1080
    fps: int = 30
    codec: str = "h264_nvenc"
    fallback_codec: str = "libx264"
    crf: int = 19
    preset: str = "p5"
    fallback_preset: str = "fast"
    premium_providers: list[str]
    enable_premium_scenes: bool = False
    premium_max_scenes_per_video: int = 1
    premium_daily_budget_usd: float = 0.50
    veo_model: str
    veo_estimated_usd_per_second: float = 0.05
    gemini_omni_model: str = "gemini-omni-flash-preview"
    gemini_omni_estimated_usd_per_second: float = 0.10
    minimax_model: str
    minimax_resolution: str = "768P"
    minimax_estimated_usd_per_clip: float = 0.30
    cloud_clip_seconds: int = 8
    transition_seconds: float = 0.35
    stock_video_enabled: bool = True
    stock_video_providers: list[str] = Field(default_factory=lambda: ["pexels_video"])
    stock_video_max_scenes_per_video: int = Field(default=48, ge=0, le=100)
    stock_video_candidates_per_scene: int = Field(default=15, ge=1, le=80)
    stock_video_min_width: int = Field(default=1280, ge=320)
    stock_video_min_duration_seconds: float = Field(default=4.0, ge=1, le=60)
    stock_video_download_timeout_seconds: int = Field(default=180, ge=15, le=900)
    stock_video_semantic_ranking: bool = True
    stock_video_semantic_model: str = "openai/clip-vit-base-patch32"
    stock_video_semantic_candidates: int = Field(default=12, ge=2, le=40)
    stock_video_min_visual_relevance: float = Field(default=0.32, ge=0, le=1)
    local_generation_enabled: bool = False
    local_generation_providers: list[str] = Field(default_factory=lambda: ["comfyui_wan22"])
    local_generation_max_scenes_per_video: int = Field(default=1, ge=0, le=8)
    local_generation_min_score: float = Field(default=0.7, ge=0, le=1)
    local_generation_quality_gate: bool = True
    local_generation_min_quality_score: float = Field(default=0.62, ge=0, le=1)
    local_generation_min_sharpness: float = Field(default=0.25, ge=0, le=1)
    local_generation_min_reference_similarity: float = Field(default=0.52, ge=0, le=1)
    local_generation_vlm_gate: bool = True
    local_generation_vlm_model: str = "google/gemini-3-flash-preview"
    local_generation_vlm_min_score: float = Field(default=0.72, ge=0, le=1)
    local_generation_reference_policy: Literal["real_first", "synthetic_only"] = "real_first"
    local_generation_candidates: int = Field(default=2, ge=1, le=3)
    comfyui_width: int = Field(default=832, ge=256, le=1920)
    comfyui_height: int = Field(default=480, ge=256, le=1080)
    comfyui_frames: int = Field(default=121, ge=17, le=241)
    comfyui_fps: int = Field(default=24, ge=8, le=60)
    comfyui_steps: int = Field(default=20, ge=1, le=60)
    comfyui_cfg: float = Field(default=5.0, ge=1, le=15)
    comfyui_timeout_minutes: int = Field(default=60, ge=5, le=240)
    comfyui_reference_checkpoint: str = "sd_xl_base_1.0.safetensors"
    comfyui_reference_width: int = Field(default=768, ge=512, le=1536)
    comfyui_reference_height: int = Field(default=1344, ge=512, le=2048)
    comfyui_reference_steps: int = Field(default=28, ge=1, le=60)
    comfyui_reference_cfg: float = Field(default=5.5, ge=1, le=15)
    comfyui_rife_enabled: bool = True
    comfyui_rife_model: str = "rife_v4.26.safetensors"
    comfyui_rife_multiplier: int = Field(default=2, ge=2, le=4)
    # Legacy FFmpeg optical flow is deliberately off. It softened the low-resolution
    # Wan source and created rubbery edge artifacts; RIFE now runs on decoded frames.
    interpolate_low_fps_clips: bool = False
    clip_color_grade: bool = True


class AudioConfig(BaseModel):
    music_volume_db: float = -27
    sfx_volume_db: float = -19
    generate_original_music: bool = True
    sidechain_ratio: float = 8


class SubtitleConfig(BaseModel):
    burn_in: bool = True
    max_words_per_caption: int = 7
    font_name: str = "Segoe UI Semibold"
    font_size: int = 56
    highlight_color: str = "&H0037E6FF"
    alignment: Literal["auto", "estimated", "whisper"] = "auto"
    whisper_model: str = "small.en"
    whisper_device: str = "auto"
    whisper_compute_type: str = "default"
    glossary: list[str] = Field(
        default_factory=lambda: [
            "Atomy",
            "Atomy USA",
            "Personal PV",
            "PV",
            "Federal Trade Commission",
            "FTC",
        ]
    )


class PublishingConfig(BaseModel):
    enabled: bool = False
    category_id: str = "27"
    made_for_kids: bool = False
    contains_synthetic_media: bool = True
    upload_thumbnail: bool = True
    upload_caption_track: bool = False


class RuntimeConfig(BaseModel):
    output_directory: Path = Path("output")
    model_directory: Path = Path("models")
    retries: int = 3
    retry_min_seconds: int = 2
    retry_max_seconds: int = 30
    stage_timeout_minutes: int = 45
    keep_intermediates: bool = True
    fail_on_quality_gate: bool = True


class Settings(BaseModel):
    channel: ChannelConfig
    schedule: ScheduleConfig
    research: ResearchConfig
    script: ScriptConfig
    storyboard: StoryboardConfig
    voice: VoiceConfig
    images: ImagesConfig
    video: VideoConfig
    audio: AudioConfig
    subtitles: SubtitleConfig
    publishing: PublishingConfig
    runtime: RuntimeConfig

    @property
    def output_directory(self) -> Path:
        return self.runtime.output_directory

    @property
    def model_directory(self) -> Path:
        return self.runtime.model_directory


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_config(path: Path, seen: set[Path] | None = None) -> dict[str, Any]:
    resolved = path.resolve()
    ancestry = set() if seen is None else set(seen)
    if resolved in ancestry:
        chain = " -> ".join(str(item) for item in [*ancestry, resolved])
        raise ConfigurationError(f"Circular configuration inheritance: {chain}")
    ancestry.add(resolved)
    if not resolved.exists():
        raise ConfigurationError(f"Configuration file not found: {resolved}")
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot read configuration {resolved}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Configuration root must be an object: {resolved}")
    parent = raw.pop("extends", None)
    if parent is None:
        return raw
    if not isinstance(parent, str) or not parent.strip():
        raise ConfigurationError(f"'extends' must be a non-empty path in {resolved}")
    parent_path = Path(parent)
    if not parent_path.is_absolute():
        parent_path = resolved.parent / parent_path
    return _deep_merge(_read_config(parent_path, ancestry), raw)


def load_settings(
    config_file: Path | str | None = None, overrides: dict[str, Any] | None = None
) -> Settings:
    load_dotenv()
    path_value = (
        config_file
        if config_file is not None
        else (os.getenv("CONFIG_FILE") or "config/default.yaml")
    )
    path = Path(path_value)
    try:
        raw = _read_config(path)
        runtime_from_environment = {
            key: value
            for key, value in {
                "output_directory": os.getenv("OUTPUT_DIRECTORY"),
                "model_directory": os.getenv("MODEL_DIRECTORY"),
            }.items()
            if value
        }
        if runtime_from_environment:
            raw = _deep_merge(raw, {"runtime": runtime_from_environment})
        if overrides:
            raw = _deep_merge(raw, overrides)
        return Settings.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid configuration in {path}: {exc}") from exc
