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
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(pcm.tobytes())
    return path


def generate_original_music(
    duration_seconds: float, output: Path, sample_rate: int = 48000
) -> Path:
    """Generate an original restrained ambient bed with no third-party rights dependency."""
    total = max(1, math.ceil(duration_seconds * sample_rate))
    music = np.zeros(total, dtype=np.float32)
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
        chord = (
            0.18 * np.sin(2 * np.pi * root * local_time)
            + 0.10 * np.sin(2 * np.pi * root * 1.5 * local_time + 0.5)
            + 0.07 * np.sin(2 * np.pi * root * 2.0 * local_time + 1.1)
        )
        pulse = 0.5 + 0.5 * np.sin(2 * np.pi * 0.125 * local_time)
        music[start:end] += chord * envelope * (0.65 + 0.2 * pulse)
    fade = min(total // 2, sample_rate * 3)
    if fade:
        music[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        music[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return _write_wave(output, music * 0.65, sample_rate)


def generate_sfx_track(storyboard: Storyboard, duration_seconds: float, output: Path) -> Path:
    sample_rate = 48000
    total = max(1, math.ceil(duration_seconds * sample_rate))
    track = np.zeros(total, dtype=np.float32)
    rng = np.random.default_rng(20260807)
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
                track[start : start + length] += whoosh
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
        "loudnorm=I=-16:TP=-1.5:LRA=11[narr];"
        f"[1:a]atrim=0:{duration_seconds:.3f},asetpts=PTS-STARTPTS,volume={cfg.music_volume_db}dB[music];"
        f"[music][narr]sidechaincompress=threshold=0.025:ratio={cfg.sidechain_ratio}:"
        "attack=20:release=350[ducked];"
        f"[2:a]atrim=0:{duration_seconds:.3f},asetpts=PTS-STARTPTS,volume={cfg.sfx_volume_db}dB[fx];"
        "[narr][ducked][fx]amix=inputs=3:duration=first:dropout_transition=2,"
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
