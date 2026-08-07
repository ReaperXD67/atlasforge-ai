from __future__ import annotations

import re
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
    brand_index = lower.find("atomy")
    if brand_index < 0:
        errors.append("Atomy is never discussed; the configured editorial brief requires a neutral case study.")
    elif brand_index / max(1, len(lower)) < cfg.brand_mention_min_fraction:
        errors.append("Atomy appears before the education-first portion is complete.")
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
        if not 5.5 * 60 <= duration <= 8.5 * 60:
            errors.append(f"Final duration is {duration / 60:.2f} minutes; expected approximately 6-8.")
    if not thumbnail.exists() or thumbnail.stat().st_size < 20_000:
        errors.append("Thumbnail is missing or implausibly small.")
    if not metadata.chapters or not metadata.chapters[0].startswith("0:00"):
        errors.append("YouTube chapters must begin at 0:00.")
    if len(storyboard.scenes) < 12:
        errors.append("Storyboard has too little visual variation for long-form video.")
    if errors and settings.runtime.fail_on_quality_gate:
        raise QualityGateFailed(" ".join(errors))
    return errors

