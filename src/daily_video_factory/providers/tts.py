from __future__ import annotations

import asyncio
import base64
import json
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
from ..media.subtitles import (
    scale_exact_caption_sidecars,
    write_exact_caption_sidecars,
    write_forced_aligned_caption_sidecars,
)
from ..voice_direction import (
    VoiceDirection,
    bounded_speech_chunks,
    chatterbox_controls,
    directed_speech_chunks,
)
from .base import Provider, ProviderChain, ProviderResult


def split_for_tts(text: str, max_chars: int = 4500) -> list[str]:
    return bounded_speech_chunks(text, max_chars)


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
        chunks = bounded_speech_chunks(paragraph, max_chars)
        beats.extend((chunk, index == len(chunks) - 1) for index, chunk in enumerate(chunks))
    return beats


class TTSProvider(Provider[Path]):
    direction_mode = "plain_transcript_fallback"
    semantic_emotion_supported = False

    def synthesize_directed(self, direction: VoiceDirection, output_dir: Path) -> Path:
        return self.synthesize(direction.narration, output_dir)

    @abstractmethod
    def synthesize(self, text: str, output_dir: Path) -> Path:
        pass


class OpenAITTSProvider(TTSProvider):
    name = "openai"
    direction_mode = "per_beat_instructions"
    semantic_emotion_supported = True

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
    def _one(self, text: str, path: Path, *, instructions: str | None = None) -> None:
        response = httpx.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={
                "model": self.cfg.openai_model,
                "voice": self.cfg.openai_voice,
                "input": text,
                "instructions": instructions if instructions is not None else self.cfg.openai_instructions,
                "response_format": "wav",
            },
            timeout=180,
        )
        if response.status_code >= 400:
            raise ProviderFailed(
                f"OpenAI TTS returned HTTP {response.status_code}: {response.text[:300]}"
            )
        path.write_bytes(response.content)

    def synthesize_directed(self, direction: VoiceDirection, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        pauses: list[int] = []
        for index, beat in enumerate(direction.beats):
            part = output_dir / f"openai_directed_{index:03d}.wav"
            self._one(
                apply_pronunciations(beat.text, self.cfg.pronunciations),
                part,
                instructions=f"{self.cfg.openai_instructions}\n{beat.instruction()}",
            )
            parts.append(part)
            pauses.append(beat.pause_after_ms if index < len(direction.beats) - 1 else 0)
        return concatenate_and_normalize(
            parts, output_dir / "narration.wav", self.cfg.target_lufs, self.ffmpeg,
            pauses_ms=pauses,
        )

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
    direction_mode = "pace_and_pauses_only"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg
        self._pipeline = None

    def _get_pipeline(self):
        from kokoro import KPipeline

        if self._pipeline is None:
            self._pipeline = KPipeline(lang_code=self.cfg.kokoro_language)
        return self._pipeline

    def available(self) -> bool:
        try:
            import kokoro  # noqa: F401
            import soundfile  # noqa: F401

            return self.ffmpeg.available
        except ImportError:
            return False

    def synthesize_directed(self, direction: VoiceDirection, output_dir: Path) -> Path:
        try:
            import kokoro  # noqa: F401
            import soundfile as sf
        except ImportError as exc:
            raise ProviderFailed("Install the local-tts extra to use Kokoro") from exc
        output_dir.mkdir(parents=True, exist_ok=True)
        pipeline = self._get_pipeline()
        sample_rate = 24000
        clips: list[np.ndarray] = []
        performance: list[dict[str, object]] = []
        cursor = 0
        for index, beat in enumerate(direction.beats):
            speed = self.cfg.kokoro_speed * beat.pace
            generated = [
                np.asarray(audio, dtype=np.float32)
                for _graphemes, _phonemes, audio in pipeline(
                    apply_pronunciations(beat.text, self.cfg.pronunciations),
                    voice=self.cfg.kokoro_voice,
                    speed=speed,
                )
            ]
            if not generated or any(
                audio.ndim != 1 or not audio.size or not np.isfinite(audio).all()
                for audio in generated
            ):
                raise ProviderFailed("Kokoro returned empty or invalid directed audio")
            audio = np.concatenate(generated)
            pause_samples = (
                round(sample_rate * beat.pause_after_ms / 1000)
                if index < len(direction.beats) - 1 else 0
            )
            performance.append({
                "beat_index": index,
                "text": beat.text,
                "speed": speed,
                "start_sample": cursor,
                "speech_samples": audio.size,
                "appended_pause_samples": pause_samples,
            })
            clips.append(audio)
            if pause_samples:
                clips.append(np.zeros(pause_samples, dtype=np.float32))
            cursor += audio.size + pause_samples
        raw = output_dir / "kokoro_raw.wav"
        sf.write(raw, np.concatenate(clips), sample_rate)
        result = concatenate_and_normalize(
            [raw], output_dir / "narration.wav", self.cfg.target_lufs, self.ffmpeg
        )
        (output_dir / "narration.performance.json").write_text(
            json.dumps({
                "provider": self.name,
                "voice": self.cfg.kokoro_voice,
                "direction_mode": self.direction_mode,
                "semantic_emotion_supported": False,
                "ignored_controls": ["emotion", "energy"],
                "sample_rate": sample_rate,
                "beats": performance,
            }, indent=2) + "\n", encoding="utf-8",
        )
        return result

    def synthesize(self, text: str, output_dir: Path) -> Path:
        try:
            import kokoro  # noqa: F401
            import soundfile as sf
        except ImportError as exc:
            raise ProviderFailed("Install the local-tts extra to use Kokoro") from exc
        output_dir.mkdir(parents=True, exist_ok=True)
        pipeline = self._get_pipeline()
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


class EdgeTTSProvider(TTSProvider):
    """Natural no-key neural narration with an explicit offline-provider fallback."""

    name = "edge"

    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.cfg = settings.voice
        self.ffmpeg = ffmpeg

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401

            return self.ffmpeg.available
        except ImportError:
            return False

    async def _save(
        self, text: str, path: Path, *, rate: str, pitch: str
    ) -> list[tuple[str, float, float]]:
        from edge_tts import Communicate

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                communication = Communicate(
                    text,
                    self.cfg.edge_voice,
                    rate=rate,
                    pitch=pitch,
                    volume=self.cfg.edge_volume,
                    boundary="WordBoundary",
                )
                audio = bytearray()
                words: list[tuple[str, float, float]] = []
                async for event in communication.stream():
                    if event["type"] == "audio":
                        audio.extend(event["data"])
                    elif event["type"] == "WordBoundary":
                        start = float(event["offset"]) / 10_000_000
                        end = start + float(event["duration"]) / 10_000_000
                        words.append((str(event["text"]), start, end))
                if not audio or not words:
                    raise RuntimeError("no usable audio or word boundaries")
                path.write_bytes(audio)
                return words
            except Exception as exc:  # Edge transport errors vary across aiohttp releases.
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(1.5 * (2**attempt))
        raise ProviderFailed(f"Edge TTS failed after three attempts: {last_error}")

    @staticmethod
    def _adjust_signed(value: str, delta: int, suffix: str) -> str:
        match = re.fullmatch(r"([+-]?)(\d+)(?:%|Hz)", value.strip())
        if not match:
            raise ProviderFailed(f"Invalid Edge prosody value: {value}")
        number = int(match.group(2)) * (-1 if match.group(1) == "-" else 1)
        return f"{number + delta:+d}{suffix}"

    def synthesize(self, text: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        if self.cfg.edge_expressive:
            beats = split_for_expressive_tts(text, max_chars=self.cfg.edge_beat_max_chars)
        else:
            chunks = split_for_tts(text, max_chars=3800)
            beats = [(chunk, index == len(chunks) - 1) for index, chunk in enumerate(chunks)]
        parts: list[Path] = []
        pauses_ms: list[int] = []
        timed_words: list[tuple[str, float, float]] = []
        cursor = 0.0
        rate_pattern = (-1, 0, 1, 0, -1, 1)
        pitch_pattern = (1, 0, -1, 0, 1, -1)
        for index, (beat, paragraph_end) in enumerate(beats, start=1):
            spoken_beat = apply_pronunciations(beat, self.cfg.pronunciations)
            rate_delta = (
                rate_pattern[(index - 1) % len(rate_pattern)]
                * self.cfg.edge_rate_variation_pct
            )
            pitch_delta = (
                pitch_pattern[(index - 1) % len(pitch_pattern)]
                * self.cfg.edge_pitch_variation_hz
            )
            if index == 1:
                rate_delta -= self.cfg.edge_hook_slowdown_pct
                pitch_delta += self.cfg.edge_hook_pitch_lift_hz
            if index == len(beats):
                rate_delta -= self.cfg.edge_closing_slowdown_pct
            if "?" in beat:
                rate_delta -= self.cfg.edge_rate_variation_pct
                pitch_delta += self.cfg.edge_pitch_variation_hz
            rate = self._adjust_signed(self.cfg.edge_rate, rate_delta, "%")
            pitch = self._adjust_signed(self.cfg.edge_pitch, pitch_delta, "Hz")
            part = output_dir / f"edge_part_{index:03d}.mp3"
            boundaries = asyncio.run(
                self._save(spoken_beat, part, rate=rate, pitch=pitch)
            )
            parts.append(part)
            timed_words.extend(
                (word, cursor + start, cursor + end) for word, start, end in boundaries
            )
            pause_ms = 0
            if index < len(beats):
                pause_ms = (
                    self.cfg.edge_paragraph_pause_ms
                    if paragraph_end
                    else self.cfg.edge_sentence_pause_ms
                )
            pauses_ms.append(pause_ms)
            cursor += self.ffmpeg.duration(part) + pause_ms / 1000
        narration = concatenate_and_normalize(
            parts,
            output_dir / "narration.wav",
            self.cfg.target_lufs,
            self.ffmpeg,
            pauses_ms=pauses_ms,
        )
        write_exact_caption_sidecars(
            text,
            timed_words,
            output_dir,
            max_words=self.cfg.edge_caption_max_words,
            minimum_seconds=self.cfg.edge_caption_min_seconds,
        )
        (output_dir / "narration.performance.json").write_text(
            json.dumps(
                {
                    "voice": self.cfg.edge_voice,
                    "expressive": self.cfg.edge_expressive,
                    "beats": len(beats),
                    "base_rate": self.cfg.edge_rate,
                    "rate_variation_pct": self.cfg.edge_rate_variation_pct,
                    "pitch_variation_hz": self.cfg.edge_pitch_variation_hz,
                    "hook_slowdown_pct": self.cfg.edge_hook_slowdown_pct,
                    "hook_pitch_lift_hz": self.cfg.edge_hook_pitch_lift_hz,
                    "closing_slowdown_pct": self.cfg.edge_closing_slowdown_pct,
                    "sentence_pause_ms": self.cfg.edge_sentence_pause_ms,
                    "paragraph_pause_ms": self.cfg.edge_paragraph_pause_ms,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return narration


class ChatterboxTTSProvider(TTSProvider):
    """Expressive local narration with stable identity and optional consented voice reference."""

    name = "chatterbox"
    direction_mode = "numeric_prosody_approximation"

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
        return self._synthesize(text, output_dir)

    def synthesize_directed(self, direction: VoiceDirection, output_dir: Path) -> Path:
        return self._synthesize(direction.narration, output_dir, direction=direction)

    def _synthesize(
        self, text: str, output_dir: Path, *, direction: VoiceDirection | None = None
    ) -> Path:
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
            directed_beats = directed_speech_chunks(direction, 280) if direction else []
            beats = (
                [(apply_pronunciations(beat.text, self.cfg.pronunciations), False)
                 for beat in directed_beats]
                if direction else split_for_expressive_tts(spoken_text)
            )
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
                if direction:
                    exaggeration = chatterbox_controls(
                        directed_beats[index], self.cfg.chatterbox_exaggeration
                    )["exaggeration"]
                generated = model.generate(
                    beat,
                    exaggeration=exaggeration,
                    cfg_weight=self.cfg.chatterbox_cfg_weight,
                    temperature=self.cfg.chatterbox_temperature,
                )
                audio = generated.squeeze().detach().cpu().numpy().astype(np.float32)
                if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
                    raise ProviderFailed("Chatterbox returned empty or invalid audio")
                if direction and abs(directed_beats[index].pace - 1.0) > 0.005:
                    raw_beat = output_dir / f"chatterbox_beat_{index:03d}.wav"
                    paced_beat = output_dir / f"chatterbox_beat_{index:03d}_paced.wav"
                    sf.write(raw_beat, audio, sample_rate)
                    self.ffmpeg.run([
                        "-i", str(raw_beat), "-filter:a",
                        _atempo_chain(directed_beats[index].pace),
                        "-ar", str(sample_rate), str(paced_beat),
                    ])
                    audio, _ = sf.read(paced_beat, dtype="float32")
                clips.append(audio)
                if index < len(beats) - 1:
                    clips.append(
                        np.zeros(round(sample_rate * directed_beats[index].pause_after_ms / 1000), dtype=np.float32)
                        if direction else paragraph_pause if paragraph_end else sentence_pause
                    )
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
            if direction is None and abs(tempo - 1.0) > 0.005:
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
    parts: list[Path],
    output: Path,
    target_lufs: int,
    ffmpeg: FFmpeg,
    *,
    pauses_ms: list[int] | None = None,
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
    if pauses_ms is not None and len(pauses_ms) != len(parts):
        raise ValueError("One pause value is required for each narration part")
    if len(parts) == 1 and not pauses_ms:
        audio_filter = f"[0:a]{mastering}[out]"
    else:
        prepared: list[str] = []
        labels = ""
        for index in range(len(parts)):
            pause_seconds = (pauses_ms or [0] * len(parts))[index] / 1000
            prepared.append(f"[{index}:a]apad=pad_dur={pause_seconds:.3f}[part{index}]")
            labels += f"[part{index}]"
        audio_filter = (
            ";".join(prepared)
            + f";{labels}concat=n={len(parts)}:v=0:a=1[joined];"
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
    scale_exact_caption_sidecars(narration.parent, maximum_seconds / actual_seconds)
    return narration


def fit_narration_to_seconds(narration: Path, target_seconds: float, ffmpeg: FFmpeg) -> Path:
    """Fit narration and its exact timing sidecars to a known edit duration."""
    if target_seconds <= 0:
        raise ValueError("Target narration duration must be positive")
    actual_seconds = ffmpeg.duration(narration)
    if abs(actual_seconds - target_seconds) <= 0.02:
        return narration
    speed = actual_seconds / target_seconds
    fitted = narration.with_name(f"{narration.stem}.exact-fit{narration.suffix}")
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
    scale_exact_caption_sidecars(narration.parent, target_seconds / actual_seconds)
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
            "edge": EdgeTTSProvider(settings, ffmpeg),
            "chatterbox": ChatterboxTTSProvider(settings, ffmpeg),
            "piper": PiperTTSProvider(settings, ffmpeg),
        }
        self.chain: ProviderChain[Path] = ProviderChain(
            providers[name] for name in settings.voice.providers if name in providers
        )

    def run(
        self, text: str, output_dir: Path, *, target_seconds: float | None = None,
        direction: VoiceDirection | None = None,
    ) -> ProviderResult[Path]:
        if direction is not None:
            direction.validate_transcript(text)
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "narration.words.json",
            "narration.captions.json",
            "narration.exact.srt",
            "narration.caption-verification.json",
            "narration.performance.json",
            "narration.direction-report.json",
        ):
            with suppress(FileNotFoundError):
                (output_dir / name).unlink()
        attempts: list[dict[str, str]] = []

        def invoke(provider: Provider[Path]) -> Path:
            narrator = cast(TTSProvider, provider)
            # A failed earlier provider must not leave timing from a different voice.
            for sidecar in ("narration.words.json", "narration.captions.json",
                            "narration.exact.srt", "narration.caption-verification.json",
                            "narration.performance.json"):
                with suppress(FileNotFoundError):
                    (output_dir / sidecar).unlink()
            attempt = {"provider": provider.name, "status": "failed"}
            attempts.append(attempt)
            value = (narrator.synthesize_directed(direction, output_dir) if direction
                     else narrator.synthesize(text, output_dir))
            attempt["status"] = "succeeded"
            return value

        result = self.chain.run("narration", invoke)
        if not (output_dir / "narration.words.json").is_file():
            write_forced_aligned_caption_sidecars(
                text,
                result.value,
                output_dir,
                self.settings,
            )
        result.value = fit_narration_duration(
            result.value,
            self.settings.script.target_minutes,
            self.settings.voice.max_duration_ratio,
            self.ffmpeg,
        )
        if target_seconds is not None:
            result.value = fit_narration_to_seconds(result.value, target_seconds, self.ffmpeg)
        selected = next(provider for provider in self.chain.providers if provider.name == result.provider)
        mode = cast(TTSProvider, selected).direction_mode
        (output_dir / "narration.direction-report.json").write_text(
            json.dumps({
                "schema_version": 1,
                "requested_provider_order": self.settings.voice.providers,
                "selected_provider": result.provider,
                "fallback_used": result.provider != self.settings.voice.providers[0],
                "attempts": attempts,
                "direction_requested": direction is not None,
                "direction_mode": mode if direction else "provider_default",
                "direction_applied": direction is not None and mode != "plain_transcript_fallback",
                "semantic_emotion_supported": cast(TTSProvider, selected).semantic_emotion_supported,
                "emotion_fidelity_verified": False,
                "duration_seconds": self.ffmpeg.duration(result.value),
                "direction": direction.model_dump() if direction else None,
            }, indent=2) + "\n", encoding="utf-8",
        )
        return result
