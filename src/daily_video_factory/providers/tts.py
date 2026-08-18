from __future__ import annotations

import base64
import os
import re
import subprocess
import wave
from abc import abstractmethod
from contextlib import suppress
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


def apply_pronunciations(text: str, pronunciations: dict[str, str]) -> str:
    """Apply speech-only pronunciation hints without changing script or caption truth."""
    spoken = text
    for written, replacement in sorted(pronunciations.items(), key=lambda item: len(item[0]), reverse=True):
        if not written.strip() or not replacement.strip():
            continue
        spoken = re.sub(
            rf"(?<!\w){re.escape(written.strip())}(?!\w)",
            replacement.strip(),
            spoken,
            flags=re.IGNORECASE,
        )
    return spoken


def split_for_expressive_tts(text: str, max_chars: int = 280) -> list[tuple[str, bool]]:
    """Create short, paragraph-aware performance beats instead of one flat TTS pass."""
    beats: list[tuple[str, bool]] = []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", re.sub(r"\s+", " ", paragraph))
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > max_chars:
                beats.append((current, False))
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            beats.append((current, True))
    return beats


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


class ElevenLabsTTSProvider(TTSProvider):
    name = "elevenlabs"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg

    def available(self) -> bool:
        return bool(os.getenv("ELEVENLABS_API_KEY")) and self.ffmpeg.available

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, ProviderFailed)),
        reraise=True,
    )
    def _one(self, text: str, path: Path) -> None:
        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}",
            params={"output_format": "mp3_44100_192"},
            headers={
                "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": self.cfg.elevenlabs_model,
                "voice_settings": {
                    "stability": self.cfg.elevenlabs_stability,
                    "similarity_boost": self.cfg.elevenlabs_similarity_boost,
                    "style": self.cfg.elevenlabs_style,
                    "use_speaker_boost": True,
                },
            },
            timeout=240,
        )
        if response.status_code >= 400:
            raise ProviderFailed(
                f"ElevenLabs TTS returned HTTP {response.status_code}: {response.text[:300]}"
            )
        path.write_bytes(response.content)

    def synthesize(self, text: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        for index, chunk in enumerate(split_for_tts(text, max_chars=4500), start=1):
            part = output_dir / f"elevenlabs_part_{index:03d}.mp3"
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
        pipeline = KPipeline(lang_code=self.cfg.kokoro_language)
        spoken_text = apply_pronunciations(text, self.cfg.pronunciations)
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", spoken_text) if part.strip()]
        clips: list[np.ndarray] = []
        sample_rate = 24000
        sentence_pause = np.zeros(
            round(sample_rate * self.cfg.kokoro_sentence_pause_ms / 1000), dtype=np.float32
        )
        paragraph_pause = np.zeros(
            round(sample_rate * self.cfg.kokoro_paragraph_pause_ms / 1000), dtype=np.float32
        )
        for paragraph_index, paragraph in enumerate(paragraphs):
            generated = [
                np.asarray(audio, dtype=np.float32)
                for _graphemes, _phonemes, audio in pipeline(
                    paragraph,
                    voice=self.cfg.kokoro_voice,
                    speed=self.cfg.kokoro_speed,
                )
            ]
            for clip_index, audio in enumerate(generated):
                clips.append(audio)
                if clip_index < len(generated) - 1 and sentence_pause.size:
                    clips.append(sentence_pause)
            if paragraph_index < len(paragraphs) - 1 and paragraph_pause.size:
                clips.append(paragraph_pause)
        if not clips:
            raise ProviderFailed("Kokoro produced no audio")
        raw = output_dir / "kokoro_raw.wav"
        sf.write(raw, np.concatenate(clips), sample_rate)
        return concatenate_and_normalize(
            [raw], output_dir / "narration.wav", self.cfg.target_lufs, self.ffmpeg
        )


class ChatterboxTTSProvider(TTSProvider):
    """Expressive local narration with stable identity and optional consented voice reference."""

    name = "chatterbox"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg

    def available(self) -> bool:
        try:
            import chatterbox.tts  # noqa: F401
            import soundfile  # noqa: F401
            import torch  # noqa: F401

            return self.ffmpeg.available
        except ImportError:
            return False

    def synthesize(self, text: str, output_dir: Path) -> Path:
        try:
            import soundfile as sf
            import torch
            from chatterbox.tts import ChatterboxTTS
        except ImportError as exc:
            raise ProviderFailed("Install Chatterbox TTS to use expressive local narration") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        reference = self.cfg.chatterbox_reference_audio
        if reference is not None and not reference.is_file():
            raise ProviderFailed(f"Chatterbox voice reference is missing: {reference}")

        try:
            model = ChatterboxTTS.from_pretrained(device=device)
            if reference is not None:
                model.prepare_conditionals(
                    str(reference), exaggeration=self.cfg.chatterbox_exaggeration
                )
            spoken_text = apply_pronunciations(text, self.cfg.pronunciations)
            beats = split_for_expressive_tts(spoken_text)
            clips: list[np.ndarray] = []
            sample_rate = int(model.sr)
            sentence_pause = np.zeros(
                round(sample_rate * self.cfg.chatterbox_sentence_pause_ms / 1000),
                dtype=np.float32,
            )
            paragraph_pause = np.zeros(
                round(sample_rate * self.cfg.chatterbox_paragraph_pause_ms / 1000),
                dtype=np.float32,
            )
            for index, (beat, paragraph_end) in enumerate(beats):
                # Give the cold open, periodic re-hooks, and final invitation a little more
                # intention while keeping ordinary explanation restrained and credible.
                lift = 0.08 if index == 0 or index == len(beats) - 1 else 0.04 if index % 4 == 0 else -0.03
                exaggeration = min(1.1, max(0.25, self.cfg.chatterbox_exaggeration + lift))
                generated = model.generate(
                    beat,
                    exaggeration=exaggeration,
                    cfg_weight=self.cfg.chatterbox_cfg_weight,
                    temperature=self.cfg.chatterbox_temperature,
                )
                audio = generated.squeeze().detach().cpu().numpy().astype(np.float32)
                clips.append(audio)
                if index < len(beats) - 1:
                    clips.append(paragraph_pause if paragraph_end else sentence_pause)
            if not clips:
                raise ProviderFailed("Chatterbox produced no audio")
            raw = output_dir / "chatterbox_raw.wav"
            sf.write(raw, np.concatenate(clips), sample_rate)
            mastered_source = raw
            word_count = len(re.findall(r"\b[\w'-]+\b", spoken_text))
            raw_duration = self.ffmpeg.duration(raw)
            target_wpm = self.cfg.chatterbox_target_wpm * self.cfg.chatterbox_speed
            target_duration = max(1.0, word_count / target_wpm * 60)
            tempo = min(1.2, max(0.7, raw_duration / target_duration))
            if abs(tempo - 1.0) > 0.005:
                mastered_source = output_dir / "chatterbox_paced.wav"
                self.ffmpeg.run(
                    [
                        "-i",
                        str(raw),
                        "-filter:a",
                        _atempo_chain(tempo),
                        "-ar",
                        str(sample_rate),
                        str(mastered_source),
                    ]
                )
            return concatenate_and_normalize(
                [mastered_source],
                output_dir / "narration.wav",
                self.cfg.target_lufs,
                self.ffmpeg,
            )
        except ProviderFailed:
            raise
        except (RuntimeError, OSError, ValueError, AssertionError) as exc:
            if device == "cuda" and "out of memory" in str(exc).casefold():
                with suppress(RuntimeError):
                    torch.cuda.empty_cache()
            raise ProviderFailed(f"Chatterbox narration failed on {device}: {exc}") from exc


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
    mastering = (
        "highpass=f=70,"
        "equalizer=f=220:t=q:w=1:g=-1.2,"
        "equalizer=f=3000:t=q:w=1:g=1.0,"
        "acompressor=threshold=0.125:ratio=2:attack=20:release=180:makeup=1.15:knee=2.828,"
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=7"
    )
    if len(parts) == 1:
        audio_filter = f"[0:a]{mastering}[out]"
    else:
        labels = "".join(f"[{index}:a]" for index in range(len(parts)))
        audio_filter = (
            f"{labels}concat=n={len(parts)}:v=0:a=1[joined];"
            f"[joined]{mastering}[out]"
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
            "elevenlabs": ElevenLabsTTSProvider(settings, ffmpeg),
            "gemini": GeminiTTSProvider(settings, ffmpeg),
            "kokoro": KokoroTTSProvider(settings, ffmpeg),
            "chatterbox": ChatterboxTTSProvider(settings, ffmpeg),
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
