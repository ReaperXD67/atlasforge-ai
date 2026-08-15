from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .config import Settings
from .exceptions import QualityGateFailed
from .media.ffmpeg import FFmpeg
from .models import ScriptDocument, Storyboard, VideoMetadata

PROHIBITED_PATTERNS = {
    "guaranteed outcome": r"\b(guaranteed?|risk[- ]free|cannot lose|surefire)\b",
    "earnings promise": r"\b(earn|make|generate)\s+\$?\d[\d,]*(?:\s*(?:per|a)\s+(?:day|week|month))?\b",
    "income promise": r"\b(passive income|financial freedom)\s+(?:is|will be|becomes)\s+(?:easy|guaranteed|automatic)\b",
    "medical claim": r"\b(cures?|treats?|prevents?|heals?|diagnoses?)\s+(?:cancer|diabetes|disease|illness|acne)\b",
    "lifestyle income claim": r"\b(quit your job|replace your salary|six[- ]figure income|unlimited income)\b",
}


def validate_script(script: ScriptDocument, settings: Settings) -> list[str]:
    errors: list[str] = []
    cfg = settings.script
    if not cfg.min_words <= script.word_count <= cfg.max_words:
        errors.append(
            f"Script has {script.word_count} words; required range is {cfg.min_words}-{cfg.max_words}."
        )
    lower = script.full_text.lower()
    for label, pattern in PROHIBITED_PATTERNS.items():
        if re.search(pattern, lower, flags=re.IGNORECASE):
            errors.append(f"Potentially prohibited {label} detected.")
    brand = settings.channel.brand_name.strip()
    brand_index = lower.find(brand.lower()) if brand else -1
    if settings.channel.brand_required and brand and brand_index < 0:
        errors.append(
            f"{brand} is never discussed; the configured editorial brief requires a neutral case study."
        )
    elif (
        settings.channel.brand_required
        and brand
        and not script.brand_focused
        and brand_index / max(1, len(lower)) < cfg.brand_mention_min_fraction
    ):
        errors.append(f"{brand} appears before the education-first portion is complete.")
    if script.brand_focused:
        if not script.source_urls:
            errors.append("Brand-focused scripts require pinned official or regulatory sources.")
        stale_sources = [
            source.title
            for source in settings.research.official_sources
            if (date.today() - source.checked_on).days
            > settings.research.max_official_source_age_days
        ]
        if stale_sources:
            errors.append("Official source summaries are stale: " + ", ".join(stale_sources) + ".")
    disclosure_text = " ".join(script.disclosures).lower()
    if "ai" not in disclosure_text or "voice" not in disclosure_text:
        errors.append("The script package is missing an AI narration disclosure.")
    if not any(term in disclosure_text for term in {"financial", "income", "medical"}):
        errors.append("The script package is missing a financial or medical disclaimer.")
    if errors and settings.runtime.fail_on_quality_gate:
        raise QualityGateFailed(" ".join(errors))
    return errors


def validate_final(
    video: Path,
    thumbnail: Path,
    storyboard: Storyboard,
    metadata: VideoMetadata,
    settings: Settings,
    ffmpeg: FFmpeg,
) -> list[str]:
    errors: list[str] = []
    if not video.exists() or video.stat().st_size < 1_000_000:
        errors.append("Final MP4 is missing or implausibly small.")
    else:
        duration = ffmpeg.duration(video)
        target = settings.script.target_minutes
        minimum = max(0.5, target * 0.75)
        maximum = max(minimum + 0.25, target * 1.3)
        if not minimum * 60 <= duration <= maximum * 60:
            errors.append(
                f"Final duration is {duration / 60:.2f} minutes; expected approximately "
                f"{minimum:.1f}-{maximum:.1f}."
            )
    if not thumbnail.exists() or thumbnail.stat().st_size < 20_000:
        errors.append("Thumbnail is missing or implausibly small.")
    if not metadata.chapters or not metadata.chapters[0].startswith("0:00"):
        errors.append("YouTube chapters must begin at 0:00.")
    minimum_scenes = max(3, round(settings.script.target_minutes * 1.7))
    if len(storyboard.scenes) < minimum_scenes:
        errors.append("Storyboard has too little visual variation for long-form video.")
    if errors and settings.runtime.fail_on_quality_gate:
        raise QualityGateFailed(" ".join(errors))
    return errors
