from __future__ import annotations

import base64
import os
import re
import subprocess
import wave
from abc import abstractmethod
from pathlib import Path
from typing import cast

import httpx
import numpy as np
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from ..config import Settings
from ..exceptions import ProviderFailed
from ..media.ffmpeg import FFmpeg
from .base import Provider, ProviderChain, ProviderResult


def split_for_tts(text: str, max_chars: int = 4500) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


class TTSProvider(Provider[Path]):
    @abstractmethod
    def synthesize(self, text: str, output_dir: Path) -> Path:
        pass


class OpenAITTSProvider(TTSProvider):
    name = "openai"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg

    def available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY")) and self.ffmpeg.available

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, ProviderFailed)),
        reraise=True,
    )
    def _one(self, text: str, path: Path) -> None:
        response = httpx.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={
                "model": self.cfg.openai_model,
                "voice": self.cfg.openai_voice,
                "input": text,
                "instructions": self.cfg.openai_instructions,
                "response_format": "wav",
            },
            timeout=180,
        )
        if response.status_code >= 400:
            raise ProviderFailed(
                f"OpenAI TTS returned HTTP {response.status_code}: {response.text[:300]}"
            )
        path.write_bytes(response.content)

    def synthesize(self, text: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        for index, chunk in enumerate(split_for_tts(text), start=1):
            part = output_dir / f"openai_part_{index:03d}.wav"
            self._one(chunk, part)
            parts.append(part)
        return concatenate_and_normalize(
            parts, output_dir / "narration.wav", self.cfg.target_lufs, self.ffmpeg
        )


class GeminiTTSProvider(TTSProvider):
    name = "gemini"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg

    def available(self) -> bool:
        return bool(os.getenv("GOOGLE_API_KEY")) and self.ffmpeg.available

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, ProviderFailed)),
        reraise=True,
    )
    def _one(self, text: str, path: Path) -> None:
        response = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": os.environ["GOOGLE_API_KEY"],
                "Content-Type": "application/json",
            },
            json={
                "model": self.cfg.gemini_model,
                "input": "Synthesize narration. Spoken transcript begins:\n" + text,
                "response_format": {"type": "audio"},
                "generation_config": {"speech_config": [{"voice": self.cfg.gemini_voice}]},
            },
            timeout=180,
        )
        if response.status_code >= 400:
            raise ProviderFailed(
                f"Gemini TTS returned HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            data = response.json()["output_audio"]["data"]
            pcm = base64.b64decode(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderFailed("Gemini TTS returned no usable audio") from exc
        with wave.open(str(path), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(self.cfg.sample_rate)
            target.writeframes(pcm)

    def synthesize(self, text: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        for index, chunk in enumerate(split_for_tts(text, max_chars=3500), start=1):
            part = output_dir / f"gemini_part_{index:03d}.wav"
            self._one(chunk, part)
            parts.append(part)
        return concatenate_and_normalize(
            parts, output_dir / "narration.wav", self.cfg.target_lufs, self.ffmpeg
        )


class KokoroTTSProvider(TTSProvider):
    name = "kokoro"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg

    def available(self) -> bool:
        try:
            import kokoro  # noqa: F401
            import soundfile  # noqa: F401

            return self.ffmpeg.available
        except ImportError:
            return False

    def synthesize(self, text: str, output_dir: Path) -> Path:
        try:
            import soundfile as sf
            from kokoro import KPipeline
        except ImportError as exc:
            raise ProviderFailed("Install the local-tts extra to use Kokoro") from exc
        output_dir.mkdir(parents=True, exist_ok=True)
        pipeline = KPipeline(lang_code="a")
        clips: list[np.ndarray] = []
        for _graphemes, _phonemes, audio in pipeline(text, voice=self.cfg.kokoro_voice):
            clips.append(np.asarray(audio, dtype=np.float32))
        if not clips:
            raise ProviderFailed("Kokoro produced no audio")
        raw = output_dir / "kokoro_raw.wav"
        sf.write(raw, np.concatenate(clips), 24000)
        return concatenate_and_normalize(
            [raw], output_dir / "narration.wav", self.cfg.target_lufs, self.ffmpeg
        )


class PiperTTSProvider(TTSProvider):
    name = "piper"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg
        self.executable = os.getenv("PIPER_EXECUTABLE", "")
        self.model = os.getenv("PIPER_MODEL_PATH", "")

    def available(self) -> bool:
        return (
            Path(self.executable).exists() and Path(self.model).exists() and self.ffmpeg.available
        )

    def synthesize(self, text: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        raw = output_dir / "piper_raw.wav"
        completed = subprocess.run(
            [self.executable, "--model", self.model, "--output_file", str(raw)],
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=900,
        )
        if completed.returncode or not raw.exists():
            raise ProviderFailed(f"Piper failed: {completed.stderr[-1000:]}")
        return concatenate_and_normalize(
            [raw], output_dir / "narration.wav", self.cfg.target_lufs, self.ffmpeg
        )


def concatenate_and_normalize(
    parts: list[Path], output: Path, target_lufs: int, ffmpeg: FFmpeg
) -> Path:
    if not parts:
        raise ProviderFailed("No audio parts to concatenate")
    inputs: list[str] = []
    for part in parts:
        inputs.extend(["-i", str(part)])
    if len(parts) == 1:
        audio_filter = f"[0:a]loudnorm=I={target_lufs}:TP=-1.5:LRA=11[out]"
    else:
        labels = "".join(f"[{index}:a]" for index in range(len(parts)))
        audio_filter = (
            f"{labels}concat=n={len(parts)}:v=0:a=1[joined];"
            f"[joined]loudnorm=I={target_lufs}:TP=-1.5:LRA=11[out]"
        )
    ffmpeg.run(
        [*inputs, "-filter_complex", audio_filter, "-map", "[out]", "-ar", "48000", str(output)]
    )
    return output


def _atempo_chain(speed: float) -> str:
    """Build a valid FFmpeg atempo chain for any positive speed multiplier."""
    if speed <= 0:
        raise ValueError("Audio speed must be positive")
    factors: list[float] = []
    remaining = speed
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def fit_narration_duration(
    narration: Path,
    target_minutes: float,
    max_duration_ratio: float,
    ffmpeg: FFmpeg,
) -> Path:
    """Cap unexpectedly slow narration while preserving pitch and the original path."""
    actual_seconds = ffmpeg.duration(narration)
    maximum_seconds = target_minutes * 60 * max_duration_ratio
    if actual_seconds <= maximum_seconds:
        return narration
    speed = actual_seconds / maximum_seconds
    fitted = narration.with_name(f"{narration.stem}.duration-fit{narration.suffix}")
    ffmpeg.run(
        [
            "-i",
            str(narration),
            "-filter:a",
            _atempo_chain(speed),
            "-ar",
            "48000",
            str(fitted),
        ]
    )
    fitted.replace(narration)
    return narration


class NarrationGenerator:
    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.settings = settings
        self.ffmpeg = ffmpeg
        providers = {
            "openai": OpenAITTSProvider(settings, ffmpeg),
            "gemini": GeminiTTSProvider(settings, ffmpeg),
            "kokoro": KokoroTTSProvider(settings, ffmpeg),
            "piper": PiperTTSProvider(settings, ffmpeg),
        }
        self.chain: ProviderChain[Path] = ProviderChain(
            providers[name] for name in settings.voice.providers if name in providers
        )

    def run(self, text: str, output_dir: Path) -> ProviderResult[Path]:
        result = self.chain.run(
            "narration",
            lambda provider: cast(TTSProvider, provider).synthesize(text, output_dir),
        )
        result.value = fit_narration_duration(
            result.value,
            self.settings.script.target_minutes,
            self.settings.voice.max_duration_ratio,
            self.ffmpeg,
        )
        return result
