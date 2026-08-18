from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from datetime import date

import httpx

from .config import Settings
from .media.ffmpeg import FFmpeg


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _ollama_available() -> bool:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def run_doctor(settings: Settings) -> list[Check]:
    ffmpeg = FFmpeg()
    preferred_encoder_ok = ffmpeg.can_encode(settings.video.codec)
    fallback_encoder_ok = ffmpeg.can_encode(settings.video.fallback_codec)
    selected_encoder = (
        settings.video.codec if preferred_encoder_ok else settings.video.fallback_codec
    )
    source_ages = [
        (date.today() - source.checked_on).days for source in settings.research.official_sources
    ]
    sources_fresh = (
        bool(source_ages) and max(source_ages) <= settings.research.max_official_source_age_days
    )
    checks = [
        Check("Python", (3, 11) <= sys.version_info[:2] < (3, 14), platform.python_version()),
        Check("FFmpeg", ffmpeg.available, ffmpeg.executable or "not found"),
        Check(
            "Video encoder",
            preferred_encoder_ok or fallback_encoder_ok,
            f"selected={selected_encoder}; preferred_runtime={'ok' if preferred_encoder_ok else 'unavailable'}; "
            f"fallback_runtime={'ok' if fallback_encoder_ok else 'unavailable'}",
        ),
        Check(
            "Text provider",
            bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("GOOGLE_API_KEY"))
            or _ollama_available(),
            "OpenRouter, Google API, or local Ollama required",
        ),
        Check(
            "Narration provider",
            bool(os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
            or importlib.util.find_spec("kokoro") is not None
            or bool(os.getenv("PIPER_EXECUTABLE")),
            "OpenAI, Google, Kokoro, or Piper required",
        ),
        Check(
            "Editorial sources",
            sources_fresh,
            (
                f"{len(source_ages)} pinned sources; oldest={max(source_ages)} days; "
                f"limit={settings.research.max_official_source_age_days} days"
                if source_ages
                else "no official source summaries configured"
            ),
            required=bool(settings.research.editorial_topics),
        ),
        Check(
            "Google SDK",
            importlib.util.find_spec("google.genai") is not None,
            "only required for Veo",
            required=False,
        ),
        Check(
            "YouTube OAuth file",
            os.path.exists(
                os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "secrets/youtube_client_secret.json")
            ),
            "only required when publishing.enabled=true",
            required=settings.publishing.enabled,
        ),
        Check(
            "Disk space",
            shutil.disk_usage(settings.output_directory.resolve().anchor).free >= 20 * 1024**3,
            f"{shutil.disk_usage(settings.output_directory.resolve().anchor).free / 1024**3:.1f} GiB free",
        ),
    ]
    return checks
