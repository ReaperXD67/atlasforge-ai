from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from ..config import Settings
from ..models import Storyboard
from .ffmpeg import FFmpeg


def _write_wave(path: Path, samples: np.ndarray, sample_rate: int = 48000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype("<i2")
    with wave.open(str(path), "wb") as target:
        target.setnchannels(samples.shape[1] if samples.ndim == 2 else 1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(pcm.tobytes())
    return path


def generate_original_music(
    duration_seconds: float, output: Path, sample_rate: int = 48000
) -> Path:
    """Generate an original stereo documentary score with no third-party rights dependency."""
    total = max(1, math.ceil(duration_seconds * sample_rate))
    music = np.zeros((total, 2), dtype=np.float32)
    chord_roots = [110.0, 130.81, 98.0, 146.83]
    bar_seconds = 12.0
    for bar, root in enumerate(chord_roots * (math.ceil(duration_seconds / (bar_seconds * 4)) + 1)):
        start = round(bar * bar_seconds * sample_rate)
        if start >= total:
            break
        end = min(total, round((bar + 1) * bar_seconds * sample_rate))
        local_time = np.arange(end - start, dtype=np.float32) / sample_rate
        attack = np.minimum(1.0, local_time / 1.8)
        release = np.minimum(1.0, (bar_seconds - local_time) / 2.3)
        envelope = np.clip(attack * release, 0, 1)
        arc = 0.74 + 0.18 * np.sin(2 * np.pi * local_time / bar_seconds - np.pi / 2)
        sub = 0.055 * np.sin(2 * np.pi * root * 0.5 * local_time)
        left_pad = (
            0.12 * np.sin(2 * np.pi * root * 0.997 * local_time)
            + 0.075 * np.sin(2 * np.pi * root * 1.498 * local_time + 0.45)
            + 0.038 * np.sin(2 * np.pi * root * 2.002 * local_time + 1.2)
        )
        right_pad = (
            0.12 * np.sin(2 * np.pi * root * 1.003 * local_time + 0.12)
            + 0.075 * np.sin(2 * np.pi * root * 1.502 * local_time + 0.62)
            + 0.038 * np.sin(2 * np.pi * root * 1.998 * local_time + 1.05)
        )
        music[start:end, 0] += (left_pad + sub) * envelope * arc
        music[start:end, 1] += (right_pad + sub) * envelope * arc

        # Quiet 96 BPM pulse gives forward motion without fighting speech.
        beat_seconds = 60 / 96
        beat_count = math.ceil((end - start) / sample_rate / beat_seconds)
        for beat in range(beat_count):
            beat_start = round((beat * beat_seconds) * sample_rate)
            beat_length = min(round(0.42 * sample_rate), end - start - beat_start)
            if beat_length <= 0:
                continue
            beat_time = np.arange(beat_length, dtype=np.float32) / sample_rate
            pluck = (
                np.sin(2 * np.pi * root * 2 * beat_time)
                + 0.35 * np.sin(2 * np.pi * root * 3 * beat_time + 0.2)
            ) * np.exp(-7.5 * beat_time)
            pan = 0.62 if (beat + bar) % 2 else 0.38
            music[start + beat_start : start + beat_start + beat_length, 0] += (
                pluck * 0.035 * (1 - pan)
            )
            music[start + beat_start : start + beat_start + beat_length, 1] += pluck * 0.035 * pan

        # A sparse high bell marks the midpoint of each long harmonic phrase.
        bell_start = round(min(bar_seconds * 0.52, (end - start) / sample_rate) * sample_rate)
        bell_length = min(round(2.2 * sample_rate), end - start - bell_start)
        if bell_length > 0:
            bell_time = np.arange(bell_length, dtype=np.float32) / sample_rate
            bell = (
                np.sin(2 * np.pi * root * 4 * bell_time)
                + 0.25 * np.sin(2 * np.pi * root * 8.03 * bell_time)
            ) * np.exp(-2.2 * bell_time)
            music[start + bell_start : start + bell_start + bell_length, 0] += bell * 0.025
            music[start + bell_start : start + bell_start + bell_length, 1] += bell * 0.032
    fade = min(total // 2, sample_rate * 3)
    if fade:
        music[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
        music[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    return _write_wave(output, music * 0.72, sample_rate)


def generate_sfx_track(storyboard: Storyboard, duration_seconds: float, output: Path) -> Path:
    sample_rate = 48000
    total = max(1, math.ceil(duration_seconds * sample_rate))
    track = np.zeros(total, dtype=np.float32)
    rng = np.random.default_rng(20260807)
    intro_length = min(round(1.8 * sample_rate), total)
    if intro_length > 0:
        intro_time = np.arange(intro_length, dtype=np.float32) / sample_rate
        intro_noise = rng.standard_normal(intro_length).astype(np.float32)
        intro_smooth = np.convolve(intro_noise, np.ones(96, dtype=np.float32) / 96, mode="same")
        intro_envelope = np.sin(np.pi * np.minimum(1, intro_time / 1.8)) ** 2
        intro_tone = np.sin(2 * np.pi * (62 + 38 * intro_time) * intro_time)
        track[:intro_length] += (0.12 * intro_smooth + 0.035 * intro_tone) * intro_envelope
    cursor = 0.0
    for scene in storyboard.scenes:
        if scene.index > 1:
            start = round(max(0, cursor - 0.15) * sample_rate)
            length = min(round(0.55 * sample_rate), total - start)
            if length > 0:
                t = np.arange(length, dtype=np.float32) / sample_rate
                noise = rng.standard_normal(length).astype(np.float32)
                smooth = np.convolve(noise, np.ones(72, dtype=np.float32) / 72, mode="same")
                whoosh = smooth * np.sin(np.pi * np.minimum(1, t / 0.55)) * 0.28
                impact = np.sin(2 * np.pi * 72 * t) * np.exp(-9 * t) * 0.08
                if scene.visual_mode == "information_card":
                    accent = np.sin(2 * np.pi * 440 * t) * np.exp(-5.5 * t) * 0.035
                else:
                    accent = np.zeros_like(t)
                track[start : start + length] += whoosh + impact + accent
        cursor += scene.duration_seconds
    return _write_wave(output, track, sample_rate)


def mix_audio(
    narration: Path,
    music: Path,
    sfx: Path,
    duration_seconds: float,
    output: Path,
    settings: Settings,
    ffmpeg: FFmpeg,
) -> Path:
    cfg = settings.audio
    filter_graph = (
        f"[0:a]atrim=0:{duration_seconds:.3f},asetpts=PTS-STARTPTS,"
        "aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11,"
        "asplit=2[narr_mix][narr_sidechain];"
        f"[1:a]atrim=0:{duration_seconds:.3f},asetpts=PTS-STARTPTS,"
        f"aformat=channel_layouts=stereo,volume={cfg.music_volume_db}dB[music];"
        f"[music][narr_sidechain]sidechaincompress=threshold=0.025:ratio={cfg.sidechain_ratio}:"
        "attack=20:release=350[ducked];"
        f"[2:a]atrim=0:{duration_seconds:.3f},asetpts=PTS-STARTPTS,"
        f"aformat=channel_layouts=stereo,volume={cfg.sfx_volume_db}dB[fx];"
        "[narr_mix][ducked][fx]amix=inputs=3:duration=first:dropout_transition=2:normalize=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,"
        "alimiter=limit=0.95[out]"
    )
    ffmpeg.run(
        [
            "-i",
            str(narration),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            "-i",
            str(sfx),
            "-filter_complex",
            filter_graph,
            "-map",
            "[out]",
            "-ar",
            "48000",
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            str(output),
        ]
    )
    return output
