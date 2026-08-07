from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from dataclasses import dataclass

from .config import Settings
from .media.ffmpeg import FFmpeg


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def run_doctor(settings: Settings) -> list[Check]:
    ffmpeg = FFmpeg()
    checks = [
        Check("Python", (3, 11) <= sys.version_info[:2] < (3, 14), platform.python_version()),
        Check("FFmpeg", ffmpeg.available, ffmpeg.executable or "not found"),
        Check(
            "Video encoder",
            ffmpeg.has_encoder(settings.video.codec) or ffmpeg.has_encoder(settings.video.fallback_codec),
            f"preferred={settings.video.codec}, fallback={settings.video.fallback_codec}",
        ),
        Check(
            "Text provider",
            bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("GOOGLE_API_KEY"))
            or shutil.which("ollama") is not None,
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
            "Google SDK",
            importlib.util.find_spec("google.genai") is not None,
            "only required for Veo",
            required=False,
        ),
        Check(
            "YouTube OAuth file",
            os.path.exists(os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "secrets/youtube_client_secret.json")),
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

