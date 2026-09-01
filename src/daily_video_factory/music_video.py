from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
import warnings
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from pydantic import BaseModel, Field

from .artifacts import RunPaths
from .config import Settings
from .lyrics import (
    LyricTimingReport,
    align_supplied_lyrics,
    lrc_text,
    remotion_captions,
)
from .media.ffmpeg import FFmpeg
from .media.render import VideoRenderer
from .models import (
    MUSIC_EDIT_STYLES,
    MotionTextCue,
    MusicEditStyle,
    MusicTreatment,
    PerformanceAction,
    PerformerRole,
    RunManifest,
    RunStatus,
    Scene,
    StageStatus,
    Storyboard,
)
from .providers.images import SceneImageGenerator
from .providers.performance import PerformanceSceneScheduler
from .providers.video import LocalSceneScheduler, PremiumSceneScheduler, StockVideoScheduler
from .state import RunStore


class EnergyPoint(BaseModel):
    time_seconds: float
    energy: float = Field(ge=0, le=1)
    onset_strength: float = Field(default=0, ge=0, le=1)
    bass_energy: float = Field(default=0, ge=0, le=1)


class MusicSection(BaseModel):
    start_seconds: float
    end_seconds: float
    label: Literal["intro", "build", "drive", "peak", "break", "outro"]
    energy: float = Field(ge=0, le=1)
    onset_rate: float = Field(default=0, ge=0)
    pacing: Literal["beat_cut", "phrase_flow"] = "phrase_flow"
    feel: Literal["sparse", "warm", "full", "heavy", "bright"] = "full"


class MusicMoment(BaseModel):
    time_seconds: float
    kind: Literal["surge", "drop", "hard_stop"]
    strength: float = Field(ge=0, le=1)


class MusicSpan(BaseModel):
    start_seconds: float
    end_seconds: float
    kind: Literal["roll", "silence", "phrase"]
    strength: float = Field(default=0, ge=0, le=1)


class BeatMap(BaseModel):
    duration_seconds: float
    bpm: float
    beats_seconds: list[float]
    downbeats_seconds: list[float]
    energy_curve: list[EnergyPoint]
    sections: list[MusicSection]
    analysis_backend: Literal["beat_this", "librosa"] = "librosa"
    rhythm_confidence: float = Field(default=1, ge=0, le=1)
    downbeat_confidence: float = Field(default=0, ge=0, le=1)
    is_rhythmic: bool = True
    onsets_seconds: list[float] = Field(default_factory=list)
    onset_strengths: list[float] = Field(default_factory=list)
    key_moments: list[MusicMoment] = Field(default_factory=list)
    rolls: list[MusicSpan] = Field(default_factory=list)
    silences: list[MusicSpan] = Field(default_factory=list)
    phrases: list[MusicSpan] = Field(default_factory=list)


class StemSceneActivity(BaseModel):
    scene_index: int
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    vocal_energy: float = Field(default=0, ge=0, le=1)
    guitar_energy: float = Field(default=0, ge=0, le=1)


class PerformanceStemReport(BaseModel):
    analysis_backend: Literal["demucs_htdemucs_6s", "unavailable"] = "unavailable"
    vocal_stem: Path | None = None
    guitar_stem: Path | None = None
    scenes: list[StemSceneActivity] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PerformerPlanEntry(BaseModel):
    scene_index: int
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    role: PerformerRole
    action: PerformanceAction
    reference: Path
    secondary_reference: Path | None = None
    reason: str


class PerformerPlan(BaseModel):
    mode: Literal["malaysian_duet"] = "malaysian_duet"
    cast_region: Literal["Malaysia"] = "Malaysia"
    stock_people_allowed: bool = False
    entries: list[PerformerPlanEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VocalBrandCue(BaseModel):
    """A conservative word-level brand detection from the unprompted vocal transcript."""

    time_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    raw_word: str
    confidence: float = Field(ge=0, le=1)
    match_score: float = Field(ge=0, le=1)


class VocalBrandReport(BaseModel):
    brand: str
    analysis_backend: Literal["approved_lyrics_dtw", "faster_whisper", "unavailable"]
    transcript_language: str = ""
    cues: list[VocalBrandCue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _normalized_brand_word(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def match_vocal_brand_words(
    words: list[tuple[str, float, float, float]], brand: str
) -> list[VocalBrandCue]:
    """Reject hotword hallucinations and retain only plausible unprompted brand tokens."""
    expected = _normalized_brand_word(brand)
    if len(expected) < 3:
        return []
    accepted: list[VocalBrandCue] = []
    for raw_word, start, end, confidence in words:
        token = _normalized_brand_word(raw_word)
        if not token or len(token) > len(expected) + 2:
            continue
        score = SequenceMatcher(None, expected, token).ratio()
        exact = token == expected
        if not ((exact and confidence >= 0.18) or (score >= 0.64 and confidence >= 0.28)):
            continue
        cue = VocalBrandCue(
            time_seconds=round(max(0.0, start), 3),
            end_seconds=round(max(end, start + 0.2), 3),
            raw_word=raw_word.strip(),
            confidence=round(float(confidence), 4),
            match_score=round(float(score), 4),
        )
        if accepted and cue.time_seconds - accepted[-1].time_seconds < 0.7:
            previous = accepted[-1]
            if cue.confidence * cue.match_score > previous.confidence * previous.match_score:
                accepted[-1] = cue
        else:
            accepted.append(cue)
    return accepted


def detect_vocal_brand_cues(track: Path, brand: str, settings: Settings) -> VocalBrandReport:
    """Locate credible brand pronunciations without poisoning ASR with a forced hotword."""
    brand = brand.strip()
    if not brand:
        return VocalBrandReport(brand="", analysis_backend="unavailable")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return VocalBrandReport(
            brand=brand,
            analysis_backend="unavailable",
            warnings=["faster-whisper is not installed; vocal brand cues were skipped"],
        )

    cfg = settings.subtitles

    def transcribe(
        device: str, compute_type: str
    ) -> tuple[list[tuple[str, float, float, float]], object]:
        model = WhisperModel(
            cfg.whisper_model,
            device=device,
            compute_type=compute_type,
            download_root=str(settings.model_directory / "whisper"),
        )
        # Deliberately omit initial_prompt and hotwords. On instrumental passages they can make
        # Whisper repeat the requested brand even when no one said it.
        segments, info = model.transcribe(
            str(track),
            beam_size=5,
            vad_filter=False,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        words: list[tuple[str, float, float, float]] = []
        for segment in segments:
            for word in getattr(segment, "words", None) or []:
                raw = str(getattr(word, "word", "")).strip()
                start = getattr(word, "start", None)
                end = getattr(word, "end", None)
                confidence = getattr(word, "probability", None)
                if raw and start is not None and end is not None and confidence is not None:
                    words.append((raw, float(start), float(end), float(confidence)))
        return words, info

    try:
        words, info = transcribe(cfg.whisper_device, cfg.whisper_compute_type)
    except RuntimeError as exc:
        detail = str(exc).casefold()
        if cfg.whisper_device == "cpu" or not any(
            token in detail for token in ("cuda", "cublas", "cudnn")
        ):
            raise
        warnings.warn(
            "Whisper CUDA runtime is unavailable; retrying brand timing on CPU/int8.",
            RuntimeWarning,
            stacklevel=2,
        )
        words, info = transcribe("cpu", "int8")
    cues = match_vocal_brand_words(words, brand)
    brand_warnings = [] if cues else [f"No conservative vocal match for {brand} was accepted"]
    return VocalBrandReport(
        brand=brand,
        analysis_backend="faster_whisper",
        transcript_language=str(getattr(info, "language", "")),
        cues=cues,
        warnings=brand_warnings,
    )


def brand_cues_from_lyrics(lyric_report: LyricTimingReport, brand: str) -> VocalBrandReport:
    """Reuse the approved-lyric alignment instead of transcribing the song twice."""
    expected = _normalized_brand_word(brand)
    cues: list[VocalBrandCue] = []
    for line in lyric_report.lines:
        for word in line.words:
            if not word.matched or _normalized_brand_word(word.text) != expected:
                continue
            cue = VocalBrandCue(
                time_seconds=word.start_seconds,
                end_seconds=word.end_seconds,
                raw_word=word.text,
                confidence=word.confidence,
                match_score=1.0,
            )
            if cues and cue.time_seconds - cues[-1].time_seconds < 0.7:
                if cue.confidence > cues[-1].confidence:
                    cues[-1] = cue
            else:
                cues.append(cue)
    return VocalBrandReport(
        brand=brand,
        analysis_backend="approved_lyrics_dtw",
        transcript_language=lyric_report.language,
        cues=cues,
        warnings=[] if cues else [f"No aligned pronunciation of {brand} passed the lyric matcher"],
    )


def _normalized(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if not values.size:
        return values
    low, high = np.percentile(values, [5, 95])
    if high <= low:
        return np.zeros_like(values)
    return np.clip((values - low) / (high - low), 0, 1)


def _smooth(values: np.ndarray, width: int) -> np.ndarray:
    if values.size == 0 or width <= 1:
        return values.astype(np.float32, copy=False)
    kernel = np.ones(width, dtype=np.float32) / width
    return np.convolve(values, kernel, mode="same").astype(np.float32)


def _decode_master(
    track: Path, ffmpeg: FFmpeg
) -> tuple[np.ndarray, int, Path, tempfile.TemporaryDirectory[str]]:
    """Decode with FFmpeg so analysis and final mux share the same decoder/timing origin."""
    import librosa

    temporary = tempfile.TemporaryDirectory(prefix="atlasforge-music-")
    wav = Path(temporary.name) / "analysis.wav"
    ffmpeg.run(
        [
            "-i",
            str(track),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "22050",
            "-c:a",
            "pcm_f32le",
            str(wav),
        ]
    )
    waveform, sample_rate = librosa.load(wav, sr=None, mono=True)
    return waveform.astype(np.float32, copy=False), int(sample_rate), wav, temporary


_BEAT_THIS_TRACKER: object | None = None
_BEAT_THIS_UNAVAILABLE = False


def _learned_beat_grid(wav: Path) -> tuple[np.ndarray, np.ndarray] | None:
    """Use Beat This when the optional local model is installed; never require it."""
    global _BEAT_THIS_TRACKER, _BEAT_THIS_UNAVAILABLE
    if _BEAT_THIS_UNAVAILABLE:
        return None
    try:
        import torch
        from beat_this.inference import File2Beats
    except ImportError:
        _BEAT_THIS_UNAVAILABLE = True
        return None
    try:
        if _BEAT_THIS_TRACKER is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _BEAT_THIS_TRACKER = File2Beats(checkpoint_path="final0", device=device, dbn=False)
        beats, downbeats = _BEAT_THIS_TRACKER(str(wav))  # type: ignore[operator]
        beats_array = np.asarray(beats, dtype=np.float32)
        downbeats_array = np.asarray(downbeats, dtype=np.float32)
        if beats_array.size >= 4:
            return beats_array, downbeats_array
    except Exception:
        # A missing/corrupt optional checkpoint must not break the zero-setup analyzer.
        _BEAT_THIS_UNAVAILABLE = True
    return None


def _librosa_beat_grid(
    onset_envelope: np.ndarray,
    sample_rate: int,
    hop_length: int,
    duration: float,
) -> tuple[float, np.ndarray, np.ndarray]:
    import librosa
    from scipy.signal import correlate, find_peaks

    centered = onset_envelope - float(np.mean(onset_envelope))
    correlation = correlate(centered, centered, mode="full", method="fft")[centered.size - 1 :]
    min_lag = max(1, round(60 * sample_rate / (220 * hop_length)))
    max_lag = min(correlation.size - 1, round(60 * sample_rate / (45 * hop_length)))
    if max_lag > min_lag:
        lag = int(np.argmax(correlation[min_lag : max_lag + 1])) + min_lag
        bpm = 60 * sample_rate / (hop_length * lag)
    else:
        bpm = 120.0
    if not math.isfinite(bpm) or not 35 <= bpm <= 240:
        bpm = 120.0
    initial_beat_duration = 60 / bpm
    minimum_distance = max(1, round(initial_beat_duration * sample_rate / hop_length * 0.45))
    prominence = max(0.01, float(np.std(onset_envelope)) * 0.3)
    peak_frames, _ = find_peaks(onset_envelope, distance=minimum_distance, prominence=prominence)
    peak_times = librosa.frames_to_time(peak_frames, sr=sample_rate, hop_length=hop_length)
    phase_candidates = peak_times[peak_times < min(duration, 8)]
    if phase_candidates.size:
        normalized = _normalized(onset_envelope)

        def best_grid(candidate_bpm: float) -> tuple[float, float]:
            candidate_duration = 60 / candidate_bpm

            def phase_score(start: float) -> float:
                grid = np.arange(start, duration, candidate_duration)
                frames = librosa.time_to_frames(grid, sr=sample_rate, hop_length=hop_length)
                frames = frames[(frames >= 0) & (frames < normalized.size)]
                return float(np.mean(normalized[frames])) if frames.size else 0.0

            start = float(max(phase_candidates, key=phase_score))
            return phase_score(start), start

        base_score, start_time = best_grid(bpm)
        if bpm < 90 and bpm * 2 <= 220:
            double_score, double_start = best_grid(bpm * 2)
            if double_score >= base_score * 0.72:
                bpm, start_time = bpm * 2, double_start
        elif bpm > 160 and bpm / 2 >= 45:
            half_score, half_start = best_grid(bpm / 2)
            if half_score > base_score * 1.12:
                bpm, start_time = bpm / 2, half_start
    else:
        start_time = 0.0
    beat_duration = 60 / bpm
    expected_grid = np.arange(start_time, duration, beat_duration)
    beats_list: list[float] = []
    for expected in expected_grid:
        nearby = np.where(np.abs(peak_times - expected) <= beat_duration * 0.22)[0]
        if nearby.size:
            selected = nearby[np.argmax(onset_envelope[peak_frames[nearby]])]
            value = float(peak_times[selected])
        else:
            value = float(expected)
        if not beats_list or value - beats_list[-1] > beat_duration * 0.45:
            beats_list.append(value)
    beats = np.asarray(beats_list, dtype=np.float32)
    if beats.size < 4:
        beats = np.arange(0, duration, 60 / bpm, dtype=np.float32)
    beat_frames = librosa.time_to_frames(beats, sr=sample_rate, hop_length=hop_length)
    return bpm, beats.astype(np.float32), np.asarray(beat_frames, dtype=int)


def _rhythm_confidence(onset: np.ndarray, beat_frames: np.ndarray) -> float:
    if onset.size == 0 or beat_frames.size < 4:
        return 0.0
    beat_frames = beat_frames[(beat_frames >= 0) & (beat_frames < onset.size)]
    if beat_frames.size < 4:
        return 0.0
    strength = _normalized(onset)
    windows = [
        float(np.max(strength[max(0, frame - 2) : min(strength.size, frame + 3)]))
        for frame in beat_frames
    ]
    coverage = float(np.mean(np.asarray(windows) >= 0.24))
    median_strength = float(np.median(windows))
    intervals = np.diff(beat_frames).astype(np.float32)
    interval_cv = float(np.std(intervals) / max(float(np.mean(intervals)), 1e-6))
    steadiness = float(np.exp(-4 * interval_cv))
    return float(np.clip(0.45 * coverage + 0.3 * median_strength + 0.25 * steadiness, 0, 1))


def _band_curves(waveform: np.ndarray, sample_rate: int, hop_length: int) -> dict[str, np.ndarray]:
    import librosa

    spectrum = np.abs(librosa.stft(waveform, hop_length=hop_length)) ** 2
    frequencies = librosa.fft_frequencies(sr=sample_rate)
    low = spectrum[frequencies < 180].sum(axis=0)
    mid = spectrum[(frequencies >= 180) & (frequencies < 2500)].sum(axis=0)
    high = spectrum[frequencies >= 2500].sum(axis=0)
    total = low + mid + high + 1e-9
    return {"low": low, "mid": mid, "high": high, "total": total}


def _estimated_downbeats(
    beats: np.ndarray,
    beat_frames: np.ndarray,
    onset: np.ndarray,
    bands: dict[str, np.ndarray],
) -> tuple[np.ndarray, float]:
    if beats.size < 4:
        return np.asarray([], dtype=np.float32), 0.0
    bass = _normalized(bands["low"] / bands["total"])
    attack = _normalized(onset)
    scores: list[float] = []
    for phase in range(4):
        frames = beat_frames[phase::4]
        frames = frames[(frames >= 0) & (frames < min(bass.size, attack.size))]
        if frames.size:
            scores.append(float(np.mean(0.72 * bass[frames] + 0.28 * attack[frames])))
        else:
            scores.append(0.0)
    ranking = np.argsort(scores)
    phase = int(ranking[-1])
    best = scores[phase]
    runner_up = scores[int(ranking[-2])] if len(ranking) > 1 else 0.0
    confidence = float(np.clip((best - runner_up) / max(best, 1e-6), 0, 1))
    return beats[phase::4], confidence


def _detect_spans(
    onset_times: np.ndarray,
    energy: np.ndarray,
    energy_times: np.ndarray,
    beat_duration: float,
) -> tuple[list[MusicSpan], list[MusicSpan]]:
    rolls: list[MusicSpan] = []
    start = 0
    for index in range(1, onset_times.size + 1):
        continuing = (
            index < onset_times.size
            and onset_times[index] - onset_times[index - 1] <= beat_duration * 0.55
        )
        if continuing:
            continue
        run = onset_times[start:index]
        if run.size >= 4 and float(np.mean(np.diff(run))) <= beat_duration * 0.42:
            density = min(1.0, float(run.size / max((run[-1] - run[0]) * 8, 1)))
            rolls.append(
                MusicSpan(
                    start_seconds=round(float(run[0]), 3),
                    end_seconds=round(float(run[-1]), 3),
                    kind="roll",
                    strength=round(density, 4),
                )
            )
        start = index

    silences: list[MusicSpan] = []
    silent = energy <= 0.06
    begin: int | None = None
    for index, value in enumerate([*silent.tolist(), False]):
        if value and begin is None:
            begin = index
        elif not value and begin is not None:
            end_index = min(index, energy_times.size - 1)
            start_time = float(energy_times[begin])
            end_time = float(energy_times[end_index])
            if end_time - start_time >= 0.45:
                silences.append(
                    MusicSpan(
                        start_seconds=round(start_time, 3),
                        end_seconds=round(end_time, 3),
                        kind="silence",
                        strength=round(float(1 - np.mean(energy[begin : end_index + 1])), 4),
                    )
                )
            begin = None
    return rolls, silences


def _nearest_anchor(value: float, anchors: list[float], tolerance: float) -> float:
    if not anchors:
        return value
    nearest = min(anchors, key=lambda anchor: abs(anchor - value))
    return nearest if abs(nearest - value) <= tolerance else value


def _section_feel(
    bands: dict[str, np.ndarray], start_frame: int, end_frame: int
) -> Literal["sparse", "warm", "full", "heavy", "bright"]:
    if end_frame <= start_frame:
        return "sparse"
    low = float(np.sum(bands["low"][start_frame:end_frame]))
    mid = float(np.sum(bands["mid"][start_frame:end_frame]))
    high = float(np.sum(bands["high"][start_frame:end_frame]))
    total = low + mid + high + 1e-9
    if total <= 1e-6:
        return "sparse"
    low_ratio, mid_ratio, high_ratio = low / total, mid / total, high / total
    if low_ratio > 0.48:
        return "heavy"
    if high_ratio > 0.42:
        return "bright"
    if mid_ratio > 0.58:
        return "warm"
    return "full"


def _build_sections(
    waveform: np.ndarray,
    sample_rate: int,
    hop_length: int,
    duration: float,
    energy: np.ndarray,
    rms_times: np.ndarray,
    onset: np.ndarray,
    onset_times: np.ndarray,
    bands: dict[str, np.ndarray],
    anchors: list[float],
    is_rhythmic: bool,
) -> list[MusicSection]:
    import librosa

    stride = max(1, round(sample_rate / hop_length / 2))
    mfcc = librosa.feature.mfcc(y=waveform, sr=sample_rate, n_mfcc=12, hop_length=hop_length)
    chroma = librosa.feature.chroma_stft(y=waveform, sr=sample_rate, hop_length=hop_length)
    feature_frames = min(mfcc.shape[1], chroma.shape[1], energy.size, onset.size)
    features = np.vstack(
        [
            mfcc[:, :feature_frames],
            chroma[:, :feature_frames],
            energy[:feature_frames][None, :] * 2,
            _normalized(onset[:feature_frames])[None, :] * 2,
        ]
    )[:, ::stride]
    segment_count = max(3, min(12, round(duration / 18)))
    if features.shape[1] <= segment_count:
        boundaries = np.linspace(0, duration, min(3, max(2, features.shape[1])) + 1)
    else:
        boundary_frames = librosa.segment.agglomerative(features, segment_count)
        raw_boundaries = [
            float(frame * stride * hop_length / sample_rate) for frame in boundary_frames
        ]
        boundaries = np.asarray([0.0, *raw_boundaries, duration], dtype=np.float32)
    snapped: list[float] = [0.0]
    for boundary in sorted(set(float(value) for value in boundaries[1:-1])):
        candidate = (
            min(anchors, key=lambda anchor: abs(anchor - boundary))
            if is_rhythmic and anchors
            else _nearest_anchor(boundary, anchors, 0.8)
        )
        if candidate - snapped[-1] >= 4 and duration - candidate >= 4:
            snapped.append(candidate)
    snapped.append(duration)

    raw_sections: list[dict[str, float]] = []
    for start, end in zip(snapped[:-1], snapped[1:], strict=True):
        mask = (rms_times >= start) & (rms_times < end)
        average = float(np.mean(energy[mask])) if np.any(mask) else 0.0
        onset_count = int(np.sum((onset_times >= start) & (onset_times < end)))
        raw_sections.append(
            {
                "start": start,
                "end": end,
                "energy": average,
                "rate": onset_count / max(end - start, 1e-6),
            }
        )
    energy_levels = np.asarray([section["energy"] for section in raw_sections])
    high_threshold = float(np.percentile(energy_levels, 75)) if energy_levels.size else 1.0
    sections: list[MusicSection] = []
    for index, raw_section in enumerate(raw_sections):
        label: Literal["intro", "build", "drive", "peak", "break", "outro"]
        if index == 0:
            label = "intro"
        elif index == len(raw_sections) - 1:
            label = "outro"
        elif raw_section["energy"] <= 0.16 or raw_section["rate"] < 0.45:
            label = "break"
        elif raw_section["energy"] >= high_threshold and raw_section["rate"] >= 0.8:
            label = "peak"
        elif raw_section["energy"] > raw_sections[index - 1]["energy"] + 0.08:
            label = "build"
        else:
            label = "drive"
        start_frame = max(0, round(raw_section["start"] * sample_rate / hop_length))
        end_frame = min(
            bands["total"].size,
            round(raw_section["end"] * sample_rate / hop_length),
        )
        beat_cut = is_rhythmic and raw_section["rate"] >= 0.55 and raw_section["energy"] >= 0.12
        sections.append(
            MusicSection(
                start_seconds=round(raw_section["start"], 3),
                end_seconds=round(raw_section["end"], 3),
                label=label,
                energy=round(float(np.clip(raw_section["energy"], 0, 1)), 4),
                onset_rate=round(raw_section["rate"], 3),
                pacing="beat_cut" if beat_cut else "phrase_flow",
                feel=_section_feel(bands, start_frame, end_frame),
            )
        )
    return sections


def _build_moments(
    energy: np.ndarray,
    rms_times: np.ndarray,
    anchors: list[float],
) -> list[MusicMoment]:
    from scipy.signal import find_peaks

    if energy.size < 4:
        return []
    seconds_per_frame = float(np.median(np.diff(rms_times))) if rms_times.size > 1 else 0.5
    lag = max(1, round(1 / max(seconds_per_frame, 1e-6)))
    delta = energy - np.roll(energy, lag)
    delta[:lag] = 0
    distance = max(1, round(2 / max(seconds_per_frame, 1e-6)))
    peaks, properties = find_peaks(np.abs(delta), height=0.16, distance=distance)
    moments: list[MusicMoment] = []
    heights = np.asarray(properties["peak_heights"])
    ordered = [int(peaks[index]) for index in np.argsort(heights)[::-1]]
    for index in ordered[:10]:
        value = float(delta[index])
        time_seconds = _nearest_anchor(float(rms_times[index]), anchors, 0.75)
        kind: Literal["surge", "drop", "hard_stop"] = "surge" if value > 0 else "drop"
        after = energy[index : min(energy.size, index + lag + 1)]
        if value < -0.3 and after.size and float(np.mean(after)) < 0.18:
            kind = "hard_stop"
        moments.append(
            MusicMoment(
                time_seconds=round(time_seconds, 3),
                kind=kind,
                strength=round(float(np.clip(abs(value), 0, 1)), 4),
            )
        )
    return sorted(
        {(moment.time_seconds, moment.kind): moment for moment in moments}.values(),
        key=lambda moment: moment.time_seconds,
    )


def _build_phrases(
    downbeats: np.ndarray, sections: list[MusicSection], duration: float
) -> list[MusicSpan]:
    phrases: list[MusicSpan] = []
    if downbeats.size >= 2:
        if float(downbeats[0]) > 0.4:
            phrases.append(
                MusicSpan(start_seconds=0, end_seconds=round(float(downbeats[0]), 3), kind="phrase")
            )
        for index in range(0, downbeats.size, 4):
            start = float(downbeats[index])
            end = float(downbeats[index + 4]) if index + 4 < downbeats.size else duration
            if end - start >= 0.4:
                phrases.append(
                    MusicSpan(
                        start_seconds=round(start, 3),
                        end_seconds=round(end, 3),
                        kind="phrase",
                    )
                )
    else:
        phrases = [
            MusicSpan(
                start_seconds=section.start_seconds,
                end_seconds=section.end_seconds,
                kind="phrase",
            )
            for section in sections
        ]
    return phrases


def analyze_music(track: Path, ffmpeg: FFmpeg) -> BeatMap:
    """Create one deterministic, confidence-aware edit map from the uploaded master."""
    import librosa

    waveform, sample_rate, analysis_wav, temporary = _decode_master(track, ffmpeg)
    try:
        if waveform.size == 0:
            raise ValueError("The uploaded track contains no decodable audio")
        duration = float(waveform.size / sample_rate)
        if duration < 4:
            raise ValueError("Music-film tracks must be at least four seconds long")
        hop = 512
        _harmonic, percussive = librosa.effects.hpss(waveform)
        onset = librosa.onset.onset_strength(
            y=percussive, sr=sample_rate, hop_length=hop, aggregate=np.median
        )
        bands = _band_curves(waveform, sample_rate, hop)
        learned = _learned_beat_grid(analysis_wav)
        if learned is not None:
            beats, downbeats = learned
            beat_frames = librosa.time_to_frames(beats, sr=sample_rate, hop_length=hop)
            bpm = float(60 / np.median(np.diff(beats))) if beats.size > 1 else 120.0
            backend: Literal["beat_this", "librosa"] = "beat_this"
            rhythm_confidence = 0.96
            downbeat_confidence = 0.95 if downbeats.size else 0.0
        else:
            bpm, beats, beat_frames = _librosa_beat_grid(onset, sample_rate, hop, duration)
            backend = "librosa"
            rhythm_confidence = _rhythm_confidence(onset, beat_frames)
            downbeats, downbeat_confidence = _estimated_downbeats(beats, beat_frames, onset, bands)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset,
            sr=sample_rate,
            hop_length=hop,
            backtrack=True,
            units="frames",
        )
        onset_times = librosa.frames_to_time(onset_frames, sr=sample_rate, hop_length=hop)
        normalized_onset = _normalized(onset)
        onset_strengths = [
            float(
                np.max(
                    normalized_onset[
                        max(0, int(frame) - 2) : min(normalized_onset.size, int(frame) + 3)
                    ]
                )
            )
            for frame in onset_frames
        ]
        raw_rms = librosa.feature.rms(y=waveform, frame_length=2048, hop_length=hop)[0]
        energy = _smooth(_normalized(raw_rms), max(1, round(0.35 * sample_rate / hop)))
        rms_times = librosa.frames_to_time(np.arange(energy.size), sr=sample_rate, hop_length=hop)
        overall_onset_rate = float(onset_times.size / max(duration, 1e-6))
        silence_ratio = float(np.mean(energy <= 0.06)) if energy.size else 1.0
        is_rhythmic = (
            rhythm_confidence >= 0.45 and overall_onset_rate >= 0.52 and silence_ratio < 0.62
        )
        beat_duration = float(np.median(np.diff(beats))) if beats.size > 1 else 60 / max(bpm, 1)
        rolls, silences = _detect_spans(onset_times, energy, rms_times, beat_duration)
        rhythm_confidence = float(np.clip(rhythm_confidence + min(0.08, len(rolls) * 0.02), 0, 1))
        anchors = [float(value) for value in (downbeats if is_rhythmic else onset_times)]
        sections = _build_sections(
            waveform,
            sample_rate,
            hop,
            duration,
            energy,
            rms_times,
            onset,
            onset_times,
            bands,
            anchors,
            is_rhythmic,
        )
        moments = _build_moments(energy, rms_times, anchors)
        phrases = _build_phrases(
            downbeats if is_rhythmic else np.asarray([], dtype=np.float32),
            sections,
            duration,
        )
        bass = _normalized(bands["low"])
        stride = max(1, round(0.25 * sample_rate / hop))
        energy_curve = [
            EnergyPoint(
                time_seconds=round(float(rms_times[index]), 3),
                energy=round(float(np.clip(energy[index], 0, 1)), 4),
                onset_strength=round(float(normalized_onset[min(index, onset.size - 1)]), 4),
                bass_energy=round(float(bass[min(index, bass.size - 1)]), 4),
            )
            for index in range(0, energy.size, stride)
        ]
        return BeatMap(
            duration_seconds=round(duration, 3),
            bpm=round(float(bpm), 2),
            beats_seconds=[round(float(value), 3) for value in beats if value < duration],
            downbeats_seconds=[round(float(value), 3) for value in downbeats if value < duration],
            energy_curve=energy_curve,
            sections=sections,
            analysis_backend=backend,
            rhythm_confidence=round(rhythm_confidence, 4),
            downbeat_confidence=round(downbeat_confidence, 4),
            is_rhythmic=is_rhythmic,
            onsets_seconds=[round(float(value), 3) for value in onset_times],
            onset_strengths=[round(float(value), 4) for value in onset_strengths],
            key_moments=moments,
            rolls=rolls,
            silences=silences,
            phrases=phrases,
        )
    finally:
        temporary.cleanup()


RACING_QUERIES = {
    "intro": [
        "race track aerial sunrise cinematic",
        "sports car garage silhouette close up",
        "race car steering wheel cockpit detail",
        "racing helmet gloves pit garage cinematic",
    ],
    "build": [
        "sports car wheel brake caliper close up",
        "driver hands racing steering wheel close up",
        "pit crew preparing sports car cinematic",
        "sports car rolling through pit lane",
    ],
    "drive": [
        "sports car racing on circuit tracking shot",
        "race car cornering on asphalt track",
        "sports car acceleration race track cinematic",
        "racing car onboard cockpit speed",
    ],
    "peak": [
        "sports cars racing side by side circuit",
        "race car fast corner tire smoke cinematic",
        "sports car night race track lights",
        "motorsport crowd finish line celebration",
    ],
    "break": [
        "race car cockpit quiet anticipation cinematic",
        "pit crew waiting in shadow dramatic",
        "empty race circuit lights atmospheric",
        "racing helmet visor reflection close up",
    ],
    "outro": [
        "sports car cool down lap sunset",
        "race track finish line night cinematic",
        "sports car parked pit lane dramatic lights",
    ],
}

# This grammar is deliberately human-heavy. Cars connect the story, while drift footage is
# rationed to the instrumental solo and actual peaks. Each entry carries an export treatment and
# a director intent so retrieval, source-window selection, and finishing share one plan.
PRAGON_STORY_GRAMMAR: dict[str, list[tuple[str, MusicTreatment, str]]] = {
    "intro": [
        (
            "Malaysian adult friends arriving night garage cinematic",
            "film_texture",
            "Open on human anticipation and an arrival, not tire smoke.",
        ),
        (
            "adult hands greeting friends garage night close up",
            "clean_hold",
            "Use identity-safe hands and over-shoulders to establish friendship.",
        ),
        (
            "Asian adult man smoking cigarette night cafe cinematic",
            "neon_flash",
            "Match the first inhale to a vocal or musical accent; prefer a face-and-hand medium close-up over an anonymous macro.",
        ),
        (
            "black sports car arriving private circuit night",
            "shutter_trail",
            "Use the car only as the friends' arrival punctuation.",
        ),
    ],
    "chorus": [
        (
            "Southeast Asian adult friends laughing night cafe",
            "neon_flash",
            "Let shared reactions sell the chorus before another car shot.",
        ),
        (
            "adult friends cheering garage party night cinematic",
            "shutter_trail",
            "Cut between group energy and intimate reaction details.",
        ),
        (
            "adult smoking cigarette close up night neon",
            "film_texture",
            "Use a tactile ciggies-break insert without packaging or logos.",
        ),
        (
            "friends riding car night city interior silhouettes",
            "clean_hold",
            "Keep faces identity-safe and make travel feel communal.",
        ),
        (
            "sports car rolling circuit night tracking shot",
            "shutter_trail",
            "Use controlled rolling speed, not continuous drifting.",
        ),
    ],
    "verse 1": [
        (
            "adult man routine city morning walking cinematic",
            "clean_hold",
            "Start with repetition and visual routine.",
        ),
        (
            "Southeast Asian adult friends meeting night cafe",
            "film_texture",
            "Turn the lyric toward freedom through a real reunion.",
        ),
        (
            "friends talking mamak cafe table night",
            "clean_hold",
            "Hold long enough to feel genuine conversation.",
        ),
        (
            "adult hands coffee tea cafe night close up",
            "film_texture",
            "Bridge unrelated faces with tactile table details.",
        ),
        (
            "friends walking together city night back view",
            "shutter_trail",
            "Move the group forward without inventing cast continuity.",
        ),
    ],
    "verse 2": [
        (
            "Southeast Asian adult woman dancing neon night cinematic",
            "shutter_trail",
            "Favor a real female performance or dance action on the female verse.",
        ),
        (
            "adult woman smiling friends night cafe candid",
            "film_texture",
            "Use candid female-led life energy, not synthetic lip-sync.",
        ),
        (
            "woman silhouette dancing garage lights night",
            "neon_flash",
            "Use silhouette and rhythm for identity-safe continuity.",
        ),
        (
            "adult female hands cigarette smoke close up night",
            "clean_hold",
            "Make the ciggies break elegant, brief, and adult-only.",
        ),
        (
            "friends leaving cafe together night back view",
            "shutter_trail",
            "Translate forward-motion lyrics into a group departure.",
        ),
    ],
    "verse 3": [
        (
            "Southeast Asian adult man electric guitar performance night",
            "shutter_trail",
            "Use an existing male guitarist as performance texture, never fake lip-sync.",
        ),
        (
            "male guitarist hands strings close up stage",
            "neon_flash",
            "Match real picking motion to guitar or drum accents.",
        ),
        (
            "adult man looking over city night cinematic",
            "clean_hold",
            "Give the aspiration lyric a human face or silhouette.",
        ),
        (
            "friends driving car night interior silhouettes",
            "film_texture",
            "Keep the road image communal and reflective.",
        ),
        (
            "sports car cruising circuit dusk cinematic",
            "shutter_trail",
            "Use a cruise shot to widen the world without overusing drift.",
        ),
    ],
    "pre-chorus": [
        (
            "adult friends walking together night low angle",
            "shutter_trail",
            "Build resolve with feet, shoulders, and group movement.",
        ),
        (
            "friends preparing car garage night cinematic",
            "film_texture",
            "Intercut preparation and glances as the drums build.",
        ),
        (
            "adult cigarette ember inhale close up night",
            "neon_flash",
            "Place one controlled ember accent before the release.",
        ),
        (
            "friends standing together rooftop city night",
            "clean_hold",
            "Hold a united group silhouette into the chorus.",
        ),
    ],
    "guitar solo": [
        (
            "electric guitarist solo hands close up concert",
            "neon_flash",
            "Lead with real guitar mechanics on the instrumental solo.",
        ),
        (
            "sports car drifting closed circuit tire smoke",
            "shutter_trail",
            "Spend the reserved drift shot on the solo's strongest phrase.",
        ),
        (
            "male electric guitar performance silhouette stage",
            "shutter_trail",
            "Use real performance motion and hard practical light.",
        ),
        (
            "friends cheering guitarist night garage",
            "film_texture",
            "Return immediately to the human circle after the drift accent.",
        ),
    ],
    "outro": [
        (
            "adult friends quiet cigarette break night garage",
            "film_texture",
            "Let the outro breathe with a final shared pause.",
        ),
        (
            "friends saying goodbye night car park cinematic",
            "clean_hold",
            "End the human story with departure and affection.",
        ),
        (
            "sports car tail lights leaving night road",
            "shutter_trail",
            "Use departure, not another racing climax.",
        ),
    ],
    "build": [
        (
            "Southeast Asian adult friends meeting garage night",
            "film_texture",
            "Build through reunion and preparation.",
        ),
        (
            "adult smoking cigarette close up night neon",
            "neon_flash",
            "Use one adult-only smoke insert on an accent.",
        ),
        (
            "male guitarist preparing electric guitar close up",
            "clean_hold",
            "Foreshadow the performance with real instrument detail.",
        ),
        (
            "black sports car detail garage night cinematic",
            "shutter_trail",
            "Treat the car as a tactile detail, not the protagonist.",
        ),
    ],
    "drive": [
        (
            "friends riding car night interior silhouettes",
            "film_texture",
            "Keep the drive connected to the friend group.",
        ),
        (
            "Southeast Asian adult woman dancing night lights",
            "shutter_trail",
            "Use real dance footage when female energy is present.",
        ),
        (
            "sports car cruising closed circuit tracking shot",
            "shutter_trail",
            "Favor a clean cruise over tire smoke.",
        ),
        (
            "adult friends laughing garage night",
            "neon_flash",
            "Return to human reaction before the next vehicle shot.",
        ),
    ],
    "peak": [
        (
            "adult friends cheering garage party night",
            "neon_flash",
            "Make the peak feel collective and alive.",
        ),
        (
            "electric guitarist energetic performance close up",
            "shutter_trail",
            "Use real performance motion on the strongest accents.",
        ),
        (
            "sports car drifting closed circuit night tire smoke",
            "shutter_trail",
            "Use drift only as a short peak punctuation.",
        ),
        (
            "Southeast Asian adult friends dancing night",
            "neon_flash",
            "Come back to people immediately after speed.",
        ),
        (
            "cigarette ember macro smoke dark",
            "film_texture",
            "Use a macro smoke detail as a rhythmic breath.",
        ),
    ],
    "break": [
        (
            "adult friends quiet conversation night cafe",
            "clean_hold",
            "Let faces, hands, and silence carry the break.",
        ),
        (
            "adult cigarette smoke close up dark cinematic",
            "film_texture",
            "Hold a calm tactile ciggies-break detail.",
        ),
        (
            "empty garage cyan lights night atmospheric",
            "clean_hold",
            "Use negative space to reset visual intensity.",
        ),
    ],
}

STYLE_PROMPTS: dict[MusicEditStyle, str] = {
    "clean": "restrained premium editorial finish",
    "neon_strobe": "electric neon practicals, sharp contrast, chromatic flash-cut energy",
    "smoke_velocity": "volumetric smoke, sodium-vapor highlights, tactile grain, dangerous speed",
    "luxury_noir": "black-on-black luxury, precise highlights, controlled monochrome tension",
    "flash_editorial": "high-fashion flash photography, hard shadows, graphic off-register framing",
    "pragon_neon": (
        "premium midnight neon, cyan and ember-red practicals, polished black surfaces, "
        "controlled haze, razor-sharp fashion-commercial framing"
    ),
}

_DIRECTION_STOP_WORDS = {
    "about",
    "also",
    "clips",
    "content",
    "example",
    "have",
    "kind",
    "like",
    "more",
    "people",
    "racing",
    "really",
    "that",
    "them",
    "they",
    "things",
    "video",
    "want",
    "where",
    "with",
}


def _direction_search_terms(visual_direction: str) -> str:
    """Turn a free-form directing note into concise terms a stock API can actually use."""
    lowered = visual_direction.lower()
    terms: list[str] = []
    alias_groups = [
        (
            {"smoke", "smoker", "smokers", "smoking", "cigarette", "cigarettes"},
            ["adult", "smoking", "cigarette"],
        ),
        ({"neon", "cyberpunk"}, ["neon", "night"]),
        ({"rain", "rainy", "wet"}, ["wet", "reflections"]),
        ({"drift", "drifting"}, ["drifting", "tire", "smoke"]),
        ({"vintage", "retro", "analog"}, ["vintage", "film"]),
        ({"luxury", "premium", "expensive"}, ["luxury"]),
        ({"gritty", "grunge", "dirty", "raw"}, ["gritty"]),
        ({"street", "underground"}, ["underground", "night"]),
        (
            {"malaysia", "malaysian", "sepang", "kuala", "lumpur"},
            ["Malaysian", "Southeast", "Asian", "adult"],
        ),
    ]
    source_tokens = re.findall(r"[a-z0-9-]+", lowered)
    source_set = set(source_tokens)
    for aliases, replacements in alias_groups:
        if aliases & source_set:
            terms.extend(replacements)
    for token in source_tokens:
        if (
            len(token) >= 4
            and token not in _DIRECTION_STOP_WORDS
            and token not in terms
            and not any(token in aliases for aliases, _replacements in alias_groups)
        ):
            terms.append(token)
        if len(terms) >= 7:
            break
    return " ".join(dict.fromkeys(terms))


def _visual_query(
    base_query: str,
    direction_terms: str,
    *,
    section: MusicSection,
    grammar_index: int,
) -> str:
    if not direction_terms:
        return base_query
    # Keep the authored story role at the front. Stock search engines weight early terms heavily;
    # replacing them with a generic prompt was why nearly every old result became a car clip.
    query = f"{base_query} {direction_terms}"
    return " ".join(query.split()[:15])


def _clean_hook_word(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 &+.-]+", " ", value).strip().upper()
    return re.sub(r"\s+", " ", cleaned)[:32].strip()


def _hook_words(hook_words: str, visual_direction: str) -> list[str]:
    requested = [
        _clean_hook_word(value)
        for value in re.split(r"[,;|\n]+", hook_words)
        if _clean_hook_word(value)
    ]
    if requested:
        return list(dict.fromkeys(requested))[:8]
    lowered = visual_direction.lower()
    inferred: list[str] = []
    if any(word in lowered for word in ("smoke", "smoker", "smoking", "cigarette")):
        inferred.extend(["LIGHT IT UP", "SMOKE / SPEED"])
    if any(word in lowered for word in ("night", "neon", "dark")):
        inferred.append("AFTER DARK")
    if any(word in lowered for word in ("luxury", "premium", "noir")):
        inferred.append("BLACK LABEL")
    inferred.extend(["REDLINE", "NO BRAKES", "FULL SEND"])
    return list(dict.fromkeys(inferred))[:8]


def _scene_music_anchors(
    beat_map: BeatMap,
    *,
    start: float,
    end: float,
    section: MusicSection,
) -> list[float]:
    if beat_map.is_rhythmic:
        anchors = beat_map.downbeats_seconds or beat_map.beats_seconds
    else:
        anchors = sorted(
            {
                *[phrase.start_seconds for phrase in beat_map.phrases],
                *[moment.time_seconds for moment in beat_map.key_moments],
                section.start_seconds,
            }
        )
    local = [
        round(max(0.0, value - start), 3) for value in anchors if start - 0.02 <= value < end - 0.18
    ]
    if not local:
        local = [0.0]
    # Flashing every detected event is tiring and cheap-looking. Strong sections get three
    # accents; the rest get one or two, with a short refractory window between them.
    limit = 3 if section.label == "peak" else 2 if section.label in {"build", "drive"} else 1
    selected: list[float] = []
    for value in local:
        if not selected or value - selected[-1] >= 0.55:
            selected.append(value)
        if len(selected) == limit:
            break
    return selected


def _motion_text_cues(
    accents: list[float],
    *,
    scene_index: int,
    scene_duration: float,
    section: MusicSection,
    edit_style: MusicEditStyle,
    words: list[str],
) -> list[MotionTextCue]:
    if scene_index == 1 or edit_style in {"clean", "pragon_neon"}:
        return []
    if section.label in {"intro", "break", "outro"} and scene_index % 2:
        return []
    style_by_edit: dict[
        MusicEditStyle, Literal["impact", "split", "outline", "stamp", "brand_neon"]
    ] = {
        "clean": "impact",
        "neon_strobe": "split",
        "smoke_velocity": "outline",
        "luxury_noir": "stamp",
        "flash_editorial": "impact",
        "pragon_neon": "impact",
    }
    cue_count = 2 if section.label == "peak" and scene_duration >= 3.1 else 1
    cues: list[MotionTextCue] = []
    for offset, accent in enumerate(accents[:cue_count]):
        if accent > scene_duration - 0.3:
            continue
        cues.append(
            MotionTextCue(
                time_seconds=accent,
                duration_seconds=0.48 if section.label == "peak" else 0.62,
                text=words[(scene_index + offset - 2) % len(words)],
                style=style_by_edit[edit_style],
            )
        )
    return cues


class SyncCut(BaseModel):
    scene_index: int
    time_seconds: float
    anchor_seconds: float
    anchor_type: Literal["downbeat", "beat_bar", "lyric", "phrase"]
    error_seconds: float = Field(ge=0)


class SyncReport(BaseModel):
    pacing: Literal["beat_cut", "lyric_beat", "phrase_flow"]
    fps: int
    cut_count: int
    mean_error_seconds: float = Field(ge=0)
    max_error_seconds: float = Field(ge=0)
    within_frame_tolerance: bool
    cuts: list[SyncCut]


def _section_for_time(beat_map: BeatMap, time_seconds: float) -> MusicSection:
    return next(
        (
            section
            for section in beat_map.sections
            if section.start_seconds <= time_seconds < section.end_seconds
        ),
        beat_map.sections[-1],
    )


def _render_duration(beat_map: BeatMap, max_duration_seconds: float | None, fps: int) -> float:
    requested = min(
        beat_map.duration_seconds,
        max_duration_seconds if max_duration_seconds is not None else beat_map.duration_seconds,
    )
    if requested < beat_map.duration_seconds and beat_map.is_rhythmic:
        candidates = [value for value in beat_map.beats_seconds if 2 <= value <= requested]
        if candidates:
            nearest = candidates[-1]
            median_beat = (
                float(np.median(np.diff(beat_map.beats_seconds)))
                if len(beat_map.beats_seconds) > 1
                else 0.5
            )
            if requested - nearest <= max(0.35, median_beat * 1.1):
                requested = nearest
    return round(round(requested * fps) / fps, 3)


def _bar_anchors(
    beat_map: BeatMap,
    lyric_report: LyricTimingReport | None = None,
) -> tuple[list[float], Literal["downbeat", "beat_bar"]]:
    """Use estimated downbeats only when their measured phase confidence supports the claim."""
    if beat_map.downbeat_confidence >= 0.35 and len(beat_map.downbeats_seconds) >= 2:
        return beat_map.downbeats_seconds, "downbeat"
    beats = beat_map.beats_seconds
    if len(beats) < 8:
        return beats, "beat_bar"
    lyric_starts = (
        [
            line.start_seconds
            for line in lyric_report.lines
            if line.confidence >= 0.18 and line.start_seconds > beats[0]
        ]
        if lyric_report
        else []
    )
    phase = 0
    if lyric_starts:
        phase = min(
            range(4),
            key=lambda candidate: float(
                np.mean(
                    [
                        min(abs(start - anchor) for anchor in beats[candidate::4])
                        for start in lyric_starts
                    ]
                )
            ),
        )
    return beats[phase::4], "beat_bar"


def _quantized_cut_points(
    beat_map: BeatMap,
    duration: float,
    fps: int,
    lyric_report: LyricTimingReport | None = None,
) -> list[float]:
    candidates: set[float] = {0.0, duration}
    bar_anchors, _bar_type = _bar_anchors(beat_map, lyric_report)
    section_boundaries = [
        section.start_seconds
        for section in beat_map.sections[1:]
        if 0 < section.start_seconds < duration
    ]
    if beat_map.is_rhythmic and bar_anchors:
        candidates.update(
            min(bar_anchors, key=lambda anchor: abs(anchor - boundary))
            for boundary in section_boundaries
        )
    else:
        candidates.update(section_boundaries)
    if lyric_report and lyric_report.analysis_backend == "faster_whisper_dtw":
        candidates.update(
            line.start_seconds
            for line in lyric_report.lines
            if line.start_seconds < duration and line.confidence >= 0.12
        )
    if beat_map.is_rhythmic and len(bar_anchors) >= 2:
        median_bar = float(np.median(np.diff(bar_anchors)))
        for section in beat_map.sections:
            start = max(0.0, section.start_seconds)
            end = min(duration, section.end_seconds)
            anchors = [value for value in bar_anchors if start <= value < end]
            preferred_bars = {
                "intro": 2,
                "build": 2,
                "drive": 2,
                "peak": 1,
                "break": 3,
                "outro": 2,
            }[section.label]
            minimum_bars = max(1, math.ceil(2.0 / max(median_bar, 1e-6)))
            stride = max(preferred_bars, minimum_bars)
            candidates.update(anchors[::stride])
        for moment in beat_map.key_moments:
            if moment.strength >= 0.24 and 0 < moment.time_seconds < duration:
                candidates.add(
                    min(
                        bar_anchors,
                        key=lambda anchor: abs(anchor - moment.time_seconds),
                    )
                )
    else:
        candidates.update(
            phrase.start_seconds
            for phrase in beat_map.phrases
            if 0 < phrase.start_seconds < duration
        )
        candidates.update(
            moment.time_seconds
            for moment in beat_map.key_moments
            if moment.strength >= 0.3 and 0 < moment.time_seconds < duration
        )

    points = sorted({round(round(value * fps) / fps, 3) for value in candidates})
    accepted: list[float] = [0.0]
    for point in points[1:-1]:
        if point - accepted[-1] >= 2.0 and duration - point >= 2.0:
            accepted.append(point)
    accepted.append(duration)
    if len(accepted) > 65:
        step = math.ceil((len(accepted) - 1) / 64)
        accepted = [*accepted[:-1:step], duration]
    if len(accepted) > 2 and accepted[-1] - accepted[-2] < 2:
        accepted.pop(-2)
    return accepted


def build_racing_storyboard(
    beat_map: BeatMap,
    *,
    title: str,
    brand: str = "PRAGON",
    max_duration_seconds: float | None = None,
    fps: int = 60,
    visual_direction: str = "",
    hook_words: str = "",
    edit_style: MusicEditStyle = "smoke_velocity",
    vocal_brand_cues: list[VocalBrandCue] | None = None,
    lyric_report: LyricTimingReport | None = None,
) -> Storyboard:
    if edit_style not in MUSIC_EDIT_STYLES:
        raise ValueError(f"Unsupported music edit style: {edit_style}")
    duration = _render_duration(beat_map, max_duration_seconds, fps)
    cut_points = _quantized_cut_points(beat_map, duration, fps, lyric_report)
    visual_direction = visual_direction.strip()
    direction_terms = _direction_search_terms(visual_direction)
    brand = _clean_hook_word(brand) or "PRAGON"
    brand_key = _normalized_brand_word(brand)
    words = [
        word
        for word in _hook_words(hook_words, visual_direction)
        if _normalized_brand_word(word) != brand_key
    ]
    words = words or ["SELAMANYA", "SATU", "BERDUA"]
    vocal_brand_cues = vocal_brand_cues or []
    lowered_direction = visual_direction.casefold()
    regional_cast = any(
        value in lowered_direction
        for value in ("malaysia", "malaysian", "sepang", "kuala lumpur", "southeast asian")
    )

    scenes: list[Scene] = []
    grammar_counts: dict[str, int] = {}
    for index, (start, end) in enumerate(zip(cut_points[:-1], cut_points[1:], strict=True)):
        section = _section_for_time(beat_map, (start + end) / 2)
        scene_number = index + 1
        is_opener = index == 0
        is_outro = scene_number == len(cut_points) - 1
        scene_lyric_lines = (
            [
                line
                for line in lyric_report.lines
                if line.start_seconds < end and line.end_seconds > start
            ]
            if lyric_report
            else []
        )
        lyric_section_key = (
            re.sub(r"\s+", " ", scene_lyric_lines[0].section.casefold().strip())
            if scene_lyric_lines
            else ""
        )
        grammar_key = (
            lyric_section_key if lyric_section_key in PRAGON_STORY_GRAMMAR else section.label
        )
        story_beats = PRAGON_STORY_GRAMMAR.get(grammar_key)
        if story_beats:
            grammar_index = grammar_counts.get(grammar_key, 0)
            base_query, treatment, story_intent = story_beats[grammar_index % len(story_beats)]
            grammar_counts[grammar_key] = grammar_index + 1
        else:
            queries = RACING_QUERIES[section.label]
            grammar_index = grammar_counts.get(section.label, 0)
            base_query = queries[grammar_index % len(queries)]
            treatment = "clean_hold"
            story_intent = "Use a coherent licensed shot that advances the song's human story."
            grammar_counts[section.label] = grammar_index + 1
        if is_outro:
            treatment = "ember_resolve"
            story_intent = (
                "Resolve on the single owned AI ember plate and exact post-rendered wordmark."
            )
        query = (
            base_query
            if story_beats
            else _visual_query(
                base_query,
                direction_terms,
                section=section,
                grammar_index=grammar_index,
            )
        )
        high_energy = section.label in {"drive", "peak"} or section.energy >= 0.68
        scene_duration = round(end - start, 3)
        accents = _scene_music_anchors(
            beat_map,
            start=start,
            end=end,
            section=section,
        )
        text_cues = _motion_text_cues(
            accents,
            scene_index=index + 1,
            scene_duration=scene_duration,
            section=section,
            edit_style=edit_style,
            words=words,
        )
        vocal_cues = [] if edit_style == "pragon_neon" else [
            MotionTextCue(
                time_seconds=round(max(0.0, cue.time_seconds - start), 3),
                duration_seconds=min(1.05, max(0.55, cue.end_seconds - cue.time_seconds + 0.28)),
                text=brand,
                style="brand_neon",
            )
            for cue in vocal_brand_cues
            if start - 0.04 <= cue.time_seconds < end - 0.18
        ]
        timed_lyrics: list[MotionTextCue] = []
        if scene_lyric_lines:
            for line in scene_lyric_lines[:2]:
                local_start = round(max(0.0, line.start_seconds - start), 3)
                local_end = min(scene_duration, max(local_start + 0.2, line.end_seconds - start))
                timed_lyrics.append(
                    MotionTextCue(
                        time_seconds=local_start,
                        duration_seconds=min(8.0, max(0.2, local_end - local_start)),
                        text=line.text,
                        style="lyric_whisper"
                        if line.text.strip().startswith("(")
                        else "lyric_line",
                    )
                )
                for word in line.words:
                    if (
                        edit_style == "pragon_neon"
                        or not word.matched
                        or _normalized_brand_word(word.text) != _normalized_brand_word(brand)
                        or not (start - 0.04 <= word.start_seconds < end - 0.18)
                    ):
                        continue
                    word_start = round(max(0.0, word.start_seconds - start), 3)
                    if word_start >= scene_duration:
                        continue
                    if any(
                        cue.style == "brand_neon" and abs(cue.time_seconds - word_start) < 0.08
                        for cue in vocal_cues
                    ):
                        continue
                    vocal_cues.append(
                        MotionTextCue(
                            time_seconds=word_start,
                            duration_seconds=min(
                                1.05,
                                max(0.45, word.end_seconds - word.start_seconds + 0.22),
                            ),
                            text=brand,
                            style="brand_neon",
                        )
                    )
        if is_outro:
            text_cues = []
            timed_lyrics = []
            vocal_cues.append(
                MotionTextCue(
                    time_seconds=min(0.45, max(0.0, scene_duration - 1.5)),
                    duration_seconds=min(1.2, max(0.7, scene_duration - 0.7)),
                    text=brand,
                    style="brand_outro",
                )
            )
        text_cues = sorted(
            [*vocal_cues, *timed_lyrics, *text_cues],
            key=lambda cue: (cue.time_seconds, 0 if cue.style == "brand_neon" else 1),
        )[:6]
        direction_prompt = (
            f" Creative direction supplied by the editor: {visual_direction}."
            if visual_direction
            else ""
        )
        exclusions = [
            "go kart",
            "motorcycle",
            "motorbike",
            "bicycle",
            "public road traffic",
            "minors",
            "AI generated people",
            "synthetic faces",
            "readable third-party logos",
        ]
        if any(word in lowered_direction for word in ("smoke", "smoking", "cigarette")):
            exclusions.extend(["children", "teenagers", "tobacco brand logos"])
        if any(word in query.casefold() for word in ("smoke", "smoking", "cigarette")):
            exclusions.extend(
                ["cannabis", "marijuana", "weed", "joint", "cigar", "vape", "hookah", "alcohol"]
            )
        scenes.append(
            Scene(
                index=index + 1,
                duration_seconds=scene_duration,
                narration="" if not is_opener else "A music-led Malaysian friendship film.",
                camera_angle="dynamic tracking shot" if high_energy else "locked detail shot",
                environment="Malaysian night cafe, private garage, performance space, and circuit",
                character_description=(
                    "clearly adult Malaysian or Southeast Asian friends and performers in licensed "
                    "existing footage; use identity-safe wides, silhouettes, hands, and details; "
                    "fashion-forward casting; no third-party brands"
                    if regional_cast
                    else "clearly adult friends or performers; no visible third-party brands"
                ),
                emotion="controlled anticipation"
                if section.label in {"intro", "build", "break"}
                else "shared release and forward motion",
                lighting="premium 35mm cyan-edge and warm-amber practical night lighting",
                sound_effects=[],
                transition=section.pacing,
                video_prompt=(
                    f"Premium human-led Malaysian music film assembled from licensed existing "
                    f"footage: {query}. {STYLE_PROMPTS[edit_style]}, real camera behavior, tactile "
                    f"35mm texture, no generated people, no synthetic lip-sync, no logos or readable "
                    f"source text; the {brand} wordmark is added in post, 16:9."
                    f"{' When people are visible, show clearly adult Malaysian or Southeast Asian talent.' if regional_cast else ''}"
                    f"{direction_prompt}"
                ),
                visual_search_query=query,
                visual_exclusion_terms=exclusions,
                onscreen_title=title if is_opener else brand if is_outro else "",
                visual_mode="information_card" if is_outro else "documentary_broll",
                premium_score=0.92
                if section.label == "peak"
                else round(0.35 + section.energy * 0.35, 3),
                start_seconds=start,
                music_section=section.label,
                music_energy=section.energy,
                music_pacing=section.pacing,
                edit_intent=(
                    f"{story_intent} "
                    + (
                        "Land its internal action immediately after the musical anchor."
                        if section.pacing == "beat_cut"
                        else "Hold the coherent action through the vocal phrase."
                    )
                ),
                visual_direction=visual_direction,
                music_edit_style=edit_style,
                music_treatment=treatment,
                beat_accents_seconds=accents,
                motion_text_cues=text_cues,
                selected_video_provider=("openai_imagegen_outro" if is_outro else "local_motion"),
                lyric_section=scene_lyric_lines[0].section if scene_lyric_lines else "",
                lyric_singer=scene_lyric_lines[0].singer if scene_lyric_lines else "",
                lyric_text=" / ".join(line.text for line in scene_lyric_lines)[:300],
            )
        )
    total = round(sum(scene.duration_seconds for scene in scenes), 3)
    return Storyboard(
        title=title, total_duration_seconds=total, scenes=scenes, provider="beat-grid"
    )


def build_sync_report(
    beat_map: BeatMap,
    storyboard: Storyboard,
    fps: int = 60,
    lyric_report: LyricTimingReport | None = None,
) -> SyncReport:
    beat_cut = beat_map.is_rhythmic and bool(beat_map.beats_seconds)
    typed_anchors: list[tuple[float, Literal["downbeat", "beat_bar", "lyric", "phrase"]]] = []
    if beat_cut:
        bar_anchors, bar_type = _bar_anchors(beat_map, lyric_report)
        typed_anchors.extend((value, bar_type) for value in bar_anchors)
    else:
        phrase_anchors = sorted(
            {
                *[phrase.start_seconds for phrase in beat_map.phrases],
                *[section.start_seconds for section in beat_map.sections],
                *[moment.time_seconds for moment in beat_map.key_moments],
            }
        )
        typed_anchors.extend((value, "phrase") for value in phrase_anchors)
    if lyric_report and lyric_report.analysis_backend == "faster_whisper_dtw":
        typed_anchors.extend(
            (line.start_seconds, "lyric") for line in lyric_report.lines if line.confidence >= 0.12
        )
    typed_anchors.sort(key=lambda item: item[0])
    cuts: list[SyncCut] = []
    for scene in storyboard.scenes[1:]:
        if not typed_anchors:
            continue
        nearest, anchor_type = min(
            typed_anchors,
            key=lambda anchor: abs(anchor[0] - scene.start_seconds),
        )
        cuts.append(
            SyncCut(
                scene_index=scene.index,
                time_seconds=scene.start_seconds,
                anchor_seconds=nearest,
                anchor_type=anchor_type,
                error_seconds=round(abs(nearest - scene.start_seconds), 4),
            )
        )
    errors = [cut.error_seconds for cut in cuts]
    maximum = max(errors, default=0.0)
    return SyncReport(
        pacing=(
            "lyric_beat"
            if beat_cut and lyric_report and lyric_report.analysis_backend == "faster_whisper_dtw"
            else "beat_cut"
            if beat_cut
            else "phrase_flow"
        ),
        fps=fps,
        cut_count=len(cuts),
        mean_error_seconds=round(float(np.mean(errors)) if errors else 0.0, 4),
        max_error_seconds=round(maximum, 4),
        within_frame_tolerance=maximum <= 1 / fps + 0.002,
        cuts=cuts,
    )


def analyze_performance_stems(
    track: Path,
    storyboard: Storyboard,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> PerformanceStemReport:
    """Measure vocal and guitar activity without making an LLM guess from the filename.

    Demucs' six-source model is used when installed. The film can still be planned when it is not
    available, but the artifact says so explicitly and falls back to the existing music energy map.
    """
    if importlib.util.find_spec("demucs") is None:
        return PerformanceStemReport(
            warnings=[
                "Demucs is not installed; vocal/guitar role placement uses section energy only."
            ]
        )
    if cache_dir is not None:
        digest = hashlib.sha256()
        with track.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        work_dir = cache_dir / digest.hexdigest()[:16]
    else:
        work_dir = output_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    stem_root = work_dir / "htdemucs_6s" / track.stem
    vocal_stem = stem_root / "vocals.wav"
    guitar_stem = stem_root / "guitar.wav"
    if not vocal_stem.is_file() or not guitar_stem.is_file():
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "demucs.separate",
                    "-n",
                    "htdemucs_6s",
                    "--out",
                    str(work_dir),
                    str(track),
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=30 * 60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return PerformanceStemReport(
                warnings=[f"Demucs analysis could not run: {type(exc).__name__}: {exc}"]
            )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown error").strip()[-800:]
            return PerformanceStemReport(warnings=[f"Demucs analysis failed: {detail}"])
    if not vocal_stem.is_file() or not guitar_stem.is_file():
        return PerformanceStemReport(
            warnings=["Demucs completed but its vocals/guitar stems were not found."]
        )

    import librosa

    def raw_scene_energy(path: Path) -> np.ndarray:
        waveform, sample_rate = librosa.load(path, sr=16_000, mono=True)
        values: list[float] = []
        for scene in storyboard.scenes:
            start = max(0, round(scene.start_seconds * sample_rate))
            end = min(
                waveform.size, round((scene.start_seconds + scene.duration_seconds) * sample_rate)
            )
            window = waveform[start:end]
            values.append(float(np.sqrt(np.mean(np.square(window)))) if window.size else 0.0)
        return np.asarray(values, dtype=np.float32)

    vocal_energy = _normalized(raw_scene_energy(vocal_stem))
    guitar_energy = _normalized(raw_scene_energy(guitar_stem))
    scenes = [
        StemSceneActivity(
            scene_index=scene.index,
            start_seconds=scene.start_seconds,
            end_seconds=round(scene.start_seconds + scene.duration_seconds, 3),
            vocal_energy=round(float(vocal_energy[position]), 4),
            guitar_energy=round(float(guitar_energy[position]), 4),
        )
        for position, scene in enumerate(storyboard.scenes)
    ]
    return PerformanceStemReport(
        analysis_backend="demucs_htdemucs_6s",
        vocal_stem=vocal_stem,
        guitar_stem=guitar_stem,
        scenes=scenes,
    )


_PERFORMANCE_PROMPTS: dict[PerformanceAction, str] = {
    "lip_sync": (
        "tight premium performance close-up of the exact same fictional adult Malaysian singer "
        "from the supplied identity reference, singing the supplied vocal audio with precise "
        "phoneme articulation, natural blinks and restrained head motion, mouth always visible, "
        "cinema-camera skin texture, cyan pit-lane edge light, shallow depth of field"
    ),
    "guitar": (
        "the exact same fictional adult Malaysian male lead from the identity reference playing "
        "a matte-black electric guitar in a neon Sepang pit garage, physically coherent fingers "
        "and fretting, body movement landing on the supplied guitar and drum accents, one coherent "
        "camera move, premium practical lighting"
    ),
    "dance": (
        "the exact same fictional adult Malaysian female lead from the identity reference giving "
        "a controlled fashion-performance dance beside a black race car in a neon pit garage, "
        "movement phrased to the supplied music, natural anatomy, elegant close-to-medium camera"
    ),
    "smoking_closeup": (
        "intimate macro-to-close portrait of the exact same fictional adult Malaysian performer "
        "from the identity reference, clearly an adult, holding an unbranded cigarette, ember glow "
        "and one slow realistic smoke exhale, premium skin and smoke detail, closed mouth, no singing"
    ),
    "duet_performance": (
        "the exact same two fictional adult Malaysian performers from both identity references in "
        "one coherent neon pit-garage two-shot; male lead plays the black electric guitar while the "
        "female lead sings and moves to the supplied audio, stable faces, physically plausible "
        "interaction and hands, deliberate dolly-in"
    ),
    "friend_gathering": (
        "the exact same four fictional adult Malaysian friends from the supplied group reference "
        "sharing a candid late-night ciggies break beside a private circuit; genuine conversation, "
        "eye contact and laughter, restrained realistic cigarette smoke, mamak kopi and teh tarik, "
        "a black performance car secondary in depth, one natural handheld-to-locked camera move"
    ),
    "car_action": "",
    "none": "",
}


def apply_malaysian_duet_plan(
    storyboard: Storyboard,
    beat_map: BeatMap,
    male_reference: Path,
    female_reference: Path,
    stem_report: PerformanceStemReport,
    *,
    group_reference: Path | None = None,
    mix_ratio: float,
    max_scenes: int,
) -> PerformerPlan:
    """Direct two recurring leads and one continuity-locked Malaysian friend circle."""
    male_reference = male_reference.resolve()
    female_reference = female_reference.resolve()
    has_group_reference = group_reference is not None
    group_reference = (group_reference or female_reference).resolve()
    if (
        not male_reference.is_file()
        or not female_reference.is_file()
        or not group_reference.is_file()
    ):
        raise FileNotFoundError(
            "Male, female, and Malaysian friend-group identity references are required"
        )

    interior = [scene for scene in storyboard.scenes[1:-1] if 2.0 <= scene.duration_seconds <= 7.5]
    if len(interior) < 6:
        raise ValueError("Malaysian Duet needs at least six usable interior scenes")
    target = min(max_scenes, len(interior), max(6, round(len(interior) * mix_ratio)))
    activity = {item.scene_index: item for item in stem_report.scenes}

    # Pick one candidate from each timeline bucket so the leads recur throughout the film rather
    # than arriving in a single synthetic block. Within each bucket, favor musical activity.
    selected: list[Scene] = []
    boundaries = np.linspace(0, len(interior), target + 1, dtype=int)
    for bucket in range(target):
        candidates = interior[
            boundaries[bucket] : max(boundaries[bucket] + 1, boundaries[bucket + 1])
        ]
        scene = max(
            candidates,
            key=lambda item: (
                activity.get(
                    item.index,
                    StemSceneActivity(scene_index=item.index, start_seconds=0, end_seconds=0),
                ).vocal_energy
                + activity.get(
                    item.index,
                    StemSceneActivity(scene_index=item.index, start_seconds=0, end_seconds=0),
                ).guitar_energy
                + item.music_energy * 0.65
            ),
        )
        selected.append(scene)

    def vocal(scene: Scene) -> float:
        return activity.get(
            scene.index,
            StemSceneActivity(scene_index=scene.index, start_seconds=0, end_seconds=0),
        ).vocal_energy

    def guitar(scene: Scene) -> float:
        return activity.get(
            scene.index,
            StemSceneActivity(scene_index=scene.index, start_seconds=0, end_seconds=0),
        ).guitar_energy

    remaining = set(scene.index for scene in selected)

    def take_best(score) -> Scene:
        chosen = max((scene for scene in selected if scene.index in remaining), key=score)
        remaining.remove(chosen.index)
        return chosen

    assignments: dict[int, tuple[PerformerRole, PerformanceAction, str]] = {}
    guitar_scene = take_best(
        lambda scene: (
            guitar(scene)
            + scene.music_energy * 0.2
            + ("guitar solo" in scene.lyric_section.casefold()) * 1.5
        )
    )
    assignments[guitar_scene.index] = (
        "male_lead",
        "guitar",
        "highest guitar-stem activity in a distributed performer window",
    )
    male_lip = take_best(
        lambda scene: (
            vocal(scene) + scene.music_energy * 0.15 + (scene.lyric_singer == "male") * 1.2
        )
    )
    assignments[male_lip.index] = (
        "male_lead",
        "lip_sync",
        "strong vocal activity selected as the male identity proof",
    )
    female_lip = take_best(
        lambda scene: (
            vocal(scene) + scene.music_energy * 0.15 + (scene.lyric_singer == "female") * 1.2
        )
    )
    assignments[female_lip.index] = (
        "female_lead",
        "lip_sync",
        "strong vocal activity selected as the female identity proof",
    )
    dance_scene = take_best(lambda scene: scene.music_energy + vocal(scene) * 0.15)
    assignments[dance_scene.index] = (
        "female_lead",
        "dance",
        "high-energy musical passage for full-body movement",
    )
    smoke_scene = take_best(
        lambda scene: 1 - scene.music_energy + (scene.music_section == "break") * 0.5
    )
    assignments[smoke_scene.index] = (
        "female_lead",
        "smoking_closeup",
        "lower-energy breath for an intimate ember-and-smoke close-up",
    )
    duet_scene = take_best(lambda scene: scene.music_energy + vocal(scene) * 0.25)
    assignments[duet_scene.index] = (
        "duet",
        "duet_performance",
        "strong shared-performance passage for the recurring two-shot",
    )

    friend_count = min(len(remaining), max(2, round(target * 0.28))) if has_group_reference else 0
    for _index in range(friend_count):
        friend_scene = take_best(
            lambda scene: (
                0.9
                - abs(scene.music_energy - 0.48)
                + (scene.lyric_singer == "ensemble") * 0.5
                + (scene.music_section in {"intro", "break", "outro"}) * 0.25
            )
        )
        assignments[friend_scene.index] = (
            "ensemble",
            "friend_gathering",
            "human story beat: the continuity-locked Malaysian friend circle takes a ciggies break",
        )

    extension: list[tuple[PerformerRole, PerformanceAction]] = [
        ("male_lead", "lip_sync"),
        ("female_lead", "lip_sync"),
        ("male_lead", "smoking_closeup"),
        ("male_lead", "guitar"),
        ("female_lead", "dance"),
        ("duet", "duet_performance"),
        *((("ensemble", "friend_gathering"),) if has_group_reference else ()),
    ]
    for position, scene in enumerate(
        sorted(
            (item for item in selected if item.index in remaining),
            key=lambda item: item.start_seconds,
        )
    ):
        role, action = extension[position % len(extension)]
        assignments[scene.index] = (
            role,
            action,
            "recurring identity beat distributed through the film",
        )

    entries: list[PerformerPlanEntry] = []
    for scene in storyboard.scenes:
        assignment = assignments.get(scene.index)
        if assignment is None:
            if scene.index not in {1, storyboard.scenes[-1].index}:
                scene.performance_action = "car_action"
                # Explicitly keep people out of stock support shots. Cars, hands, details and
                # locations are permitted; only the two locked identities may be hero talent.
                scene.visual_exclusion_terms.extend(
                    ["portrait", "model", "singer", "woman", "man", "crowd", "recognizable face"]
                )
                scene.visual_search_query = f"{scene.visual_search_query} no people vehicle detail"
            continue
        role, action, reason = assignment
        primary = (
            group_reference
            if role == "ensemble"
            else male_reference
            if role in {"male_lead", "duet"}
            else female_reference
        )
        secondary = female_reference if role == "duet" else None
        scene.performer_role = role
        scene.performance_action = action
        scene.performer_generation_required = True
        scene.performer_reference = primary
        scene.performer_reference_secondary = secondary
        scene.ai_generation_required = True
        scene.ai_generation_reason = (
            "Locked recurring Malaysian performer; stock substitution forbidden"
        )
        scene.visual_mode = "performer_ai"
        scene.character_description = (
            "the exact same fictional adult Malaysian male lead"
            if role == "male_lead"
            else "the exact same fictional adult Malaysian female lead"
            if role == "female_lead"
            else "the exact same two fictional adult Malaysian leads"
            if role == "duet"
            else "the exact same four fictional adult Malaysian friends"
        )
        scene.video_prompt = (
            f"{_PERFORMANCE_PROMPTS[action]}. Photoreal original music-video frame, 16:9, "
            "35mm cinema lens, natural skin pores, coherent reflections and real smoke physics; "
            f"lyric/emotional context: {scene.lyric_text or scene.music_section}. "
            "no identity drift, no extra people, no text, no logo, no watermark, no beauty filter."
        )
        entries.append(
            PerformerPlanEntry(
                scene_index=scene.index,
                start_seconds=scene.start_seconds,
                end_seconds=round(scene.start_seconds + scene.duration_seconds, 3),
                role=role,
                action=action,
                reference=primary,
                secondary_reference=secondary,
                reason=reason,
            )
        )
    return PerformerPlan(
        entries=sorted(entries, key=lambda item: item.start_seconds),
        warnings=stem_report.warnings,
    )


def extract_performance_audio(
    track: Path,
    storyboard: Storyboard,
    output_dir: Path,
    ffmpeg: FFmpeg,
) -> dict[int, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[int, Path] = {}
    for scene in storyboard.scenes:
        if not scene.performer_generation_required:
            continue
        output = output_dir / f"scene_{scene.index:03d}.wav"
        ffmpeg.run(
            [
                "-ss",
                f"{scene.start_seconds:.3f}",
                "-i",
                str(track),
                "-t",
                f"{scene.duration_seconds:.3f}",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output),
            ]
        )
        scene.performance_audio = output
        result[scene.index] = output
    return result


def _font(
    size: int, bold: bool = False, display: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("/app/assets/fonts/BarlowCondensed-Black.ttf")
        if display
        else Path("/app/assets/fonts/Barlow-Regular.ttf"),
        Path("assets/fonts/BarlowCondensed-Black.ttf")
        if display
        else Path("assets/fonts/Barlow-Regular.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def render_racing_title(
    title: str, bpm: float, output: Path, width: int, height: int, brand: str = "PRAGON"
) -> Path:
    image = Image.new("RGB", (width, height), (6, 7, 8))
    draw = ImageDraw.Draw(image, "RGBA")
    for offset in range(-height, width, 150):
        draw.polygon(
            [
                (offset, 0),
                (offset + 55, 0),
                (offset - height + 55, height),
                (offset - height, height),
            ],
            fill=(255, 83, 29, 16),
        )
    image = image.filter(ImageFilter.GaussianBlur(0.6))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, width, 18), fill=(40, 225, 255, 255))
    draw.text((105, 94), brand.upper(), font=_font(42, True, True), fill=(44, 231, 255, 255))
    wrapped = "\n".join(textwrap.wrap(title.upper(), width=23))
    draw.multiline_text(
        (105, 250), wrapped, font=_font(116, True, True), fill=(246, 243, 236, 255), spacing=4
    )
    draw.line((108, height - 210, width - 108, height - 210), fill=(255, 70, 48, 185), width=3)
    draw.text(
        (108, height - 165),
        f"SEPANG / MALAYSIA  ·  MUSIC MASTER {bpm:.0f} BPM",
        font=_font(26, True),
        fill=(190, 190, 184, 255),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=96)
    output.with_suffix(".license.json").write_text(
        json.dumps({"provider": "locally_generated", "license": "project-owned"}, indent=2),
        encoding="utf-8",
    )
    return output


def render_pragon_outro(
    brand: str, output: Path, width: int, height: int, *, title: str = "SEPANG AFTER DARK"
) -> Path:
    """Create an owned cigarette-ember wordmark plate for the closing brand resolve."""
    project_root = Path(__file__).resolve().parents[2]
    background_candidates = (
        Path("assets/pragon/outro/pragon-ember-ai-v1.png"),
        project_root / "assets/pragon/outro/pragon-ember-ai-v1.png",
        Path("/app/assets/pragon/outro/pragon-ember-ai-v1.png"),
        Path("assets/pragon/pragon-outro-bg.png"),
        project_root / "assets/pragon/pragon-outro-bg.png",
        Path("/app/assets/pragon/pragon-outro-bg.png"),
    )
    background_path = next((path for path in background_candidates if path.exists()), None)
    if background_path:
        with Image.open(background_path) as source:
            base = ImageOps.fit(
                source.convert("RGB"),
                (width, height),
                method=Image.Resampling.LANCZOS,
            ).convert("RGBA")
        # Hold detail in the ember while giving the wordmark a clean, expensive black field.
        base = Image.alpha_composite(
            base,
            Image.new("RGBA", (width, height), (0, 0, 0, 42)),
        )
    else:
        base = Image.new("RGBA", (width, height), (3, 5, 8, 255))
        atmosphere = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        atmosphere_draw = ImageDraw.Draw(atmosphere, "RGBA")
        glow_draw = ImageDraw.Draw(glow, "RGBA")

        # Portable fallback for installations that do not include the commissioned plate.
        ember_x = int(width * 0.75)
        ember_y = int(height * 0.72)
        for ribbon in range(8):
            points = []
            for step in range(90):
                y = ember_y - step * height / 130
                x = ember_x + math.sin(step * 0.15 + ribbon * 0.9) * (32 + ribbon * 7)
                x += math.sin(step * 0.043 + ribbon) * 44
                points.append((x, y))
            atmosphere_draw.line(
                points,
                fill=(174, 214, 225, max(12, 42 - ribbon * 4)),
                width=max(4, 20 - ribbon),
            )
        atmosphere = atmosphere.filter(ImageFilter.GaussianBlur(22))
        for radius, alpha in ((170, 18), (100, 34), (54, 68), (24, 180)):
            glow_draw.ellipse(
                (ember_x - radius, ember_y - radius, ember_x + radius, ember_y + radius),
                fill=(255, 64, 28, alpha),
            )
        base = Image.alpha_composite(base, atmosphere)
        base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(18)))

    draw = ImageDraw.Draw(base, "RGBA")

    # The supplied Pragon artwork is the typography source of truth.  It is composited as
    # artwork instead of approximated with a font so the distinctive P, terminals and long
    # g descender remain pixel-for-pixel faithful to the client's mark.
    logo_candidates = (
        Path("assets/pragon/branding/pragon-script-logo-white.png"),
        project_root / "assets/pragon/branding/pragon-script-logo-white.png",
        Path("/app/assets/pragon/branding/pragon-script-logo-white.png"),
    )
    logo_path = next((path for path in logo_candidates if path.exists()), None)
    if logo_path:
        with Image.open(logo_path) as supplied_logo:
            logo = supplied_logo.convert("RGBA")
        target_width = round(width * 0.54)
        scale = target_width / logo.width
        logo = logo.resize(
            (target_width, max(1, round(logo.height * scale))),
            Image.Resampling.LANCZOS,
        )
        logo_x = (width - logo.width) // 2
        logo_y = round(height * 0.14)
        logo_alpha = logo.getchannel("A")

        shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
        shadow.putalpha(logo_alpha.point(lambda value: round(value * 0.76)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(2, round(height * 0.008))))
        base.alpha_composite(shadow, (logo_x, logo_y + round(height * 0.013)))

        for offset, color, opacity in (
            (-6, (33, 229, 255), 0.40),
            (6, (255, 42, 91), 0.38),
        ):
            ghost = Image.new("RGBA", logo.size, (*color, 0))
            ghost.putalpha(logo_alpha.point(lambda value, alpha=opacity: round(value * alpha)))
            base.alpha_composite(ghost, (logo_x + offset, logo_y))
        base.alpha_composite(logo, (logo_x, logo_y))
    else:
        # Portable fallback for deployments that have not yet mounted the approved artwork.
        wordmark = " ".join(_clean_hook_word(brand) or "PRAGON")
        display_font = _font(round(height * 0.19), True, True)
        bounds = draw.textbbox((0, 0), wordmark, font=display_font)
        text_width = bounds[2] - bounds[0]
        text_y = int(height * 0.25)
        text_x = (width - text_width) // 2
        for offset, color in ((-7, (33, 229, 255, 105)), (7, (255, 42, 91, 100))):
            draw.text((text_x + offset, text_y), wordmark, font=display_font, fill=color)
        draw.text(
            (text_x, text_y),
            wordmark,
            font=display_font,
            fill=(247, 245, 238, 255),
            stroke_width=2,
            stroke_fill=(10, 13, 18, 255),
        )
    subtitle_font = _font(round(height * 0.026), True)
    subtitle = f"{title.upper()}  /  MALAYSIA"
    subtitle_bounds = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    draw.text(
        ((width - (subtitle_bounds[2] - subtitle_bounds[0])) // 2, int(height * 0.59)),
        subtitle,
        font=subtitle_font,
        fill=(109, 224, 235, 225),
    )
    draw.line(
        (width * 0.34, height * 0.65, width * 0.66, height * 0.65),
        fill=(255, 64, 32, 180),
        width=3,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(output, quality=97)
    output.with_suffix(".license.json").write_text(
        json.dumps(
            {
                "provider": (
                    "OpenAI image generation"
                    if background_path and background_path.name == "pragon-ember-ai-v1.png"
                    else "locally_generated"
                ),
                "license": "project-owned production asset",
                "synthetic_media": bool(
                    background_path and background_path.name == "pragon-ember-ai-v1.png"
                ),
                "synthetic_scope": "final PRAGON ember resolve only",
                "wordmark": (
                    str(logo_path)
                    if logo_path
                    else "Barlow fallback / SIL Open Font License 1.1"
                ),
                "background": str(background_path) if background_path else "procedural-fallback",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return output


class MusicVideoPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ffmpeg = FFmpeg()
        self.store = RunStore(settings.output_directory.resolve())

    def _stage(self, manifest: RunManifest, name: str, operation):
        manifest.current_stage = name
        self.store.stage(manifest.run_id, name, StageStatus.running)
        self.store.save_manifest(manifest)
        try:
            result = operation()
        except Exception as exc:
            self.store.stage(manifest.run_id, name, StageStatus.failed, str(exc))
            manifest.status = RunStatus.failed
            manifest.errors.append(f"{name}: {exc}")
            self.store.save_manifest(manifest)
            raise
        self.store.stage(manifest.run_id, name, StageStatus.completed)
        self.store.save_manifest(manifest)
        return result

    def run(
        self,
        track: Path,
        *,
        title: str = "Sepang Track Experience",
        brand: str = "PRAGON",
        max_duration_seconds: float | None = 60,
        visual_direction: str = "",
        hook_words: str = "",
        edit_style: MusicEditStyle = "smoke_velocity",
        performer_mode: Literal["stock_mix", "malaysian_duet"] = "stock_mix",
        male_performer_reference: Path | None = None,
        female_performer_reference: Path | None = None,
        friend_group_reference: Path | None = None,
        lyrics_text: str = "",
        lyrics_language: str = "auto",
        audit_only: bool = False,
    ) -> RunManifest:
        self.ffmpeg.require()
        track = track.resolve()
        if not track.is_file():
            raise FileNotFoundError(track)
        publication_date = date.today()
        run_id = f"music-{publication_date.isoformat()}-{uuid.uuid4().hex[:8]}"
        paths = RunPaths.create(self.settings.output_directory.resolve(), publication_date, run_id)
        manifest = RunManifest(
            run_id=run_id,
            publication_date=publication_date,
            status=RunStatus.running,
            pipeline_kind="music_film",
            topic=title,
            output_root=paths.root,
        )
        self.store.save_manifest(manifest)

        beat_map = self._stage(manifest, "beat_analysis", lambda: analyze_music(track, self.ffmpeg))
        paths.write_json("music/audiomap.json", beat_map)
        lyrics_text = lyrics_text.strip()
        if lyrics_text:
            lyric_report = self._stage(
                manifest,
                "lyric_alignment",
                lambda: align_supplied_lyrics(
                    track,
                    lyrics_text,
                    self.settings,
                    duration_seconds=beat_map.duration_seconds,
                    language=lyrics_language,
                ),
            )
            paths.write_text("music/lyrics_supplied.txt", lyrics_text + "\n")
            paths.write_json("music/lyrics_timing.json", lyric_report)
            paths.write_json("music/lyrics_remotion.json", remotion_captions(lyric_report))
            paths.write_text("music/lyrics.lrc", lrc_text(lyric_report))
        else:
            lyric_report = LyricTimingReport(
                analysis_backend="unavailable",
                language=lyrics_language,
                warnings=["No editor-approved lyrics were supplied."],
            )

        def analyze_brand_vocals() -> VocalBrandReport:
            if lyric_report.analysis_backend == "faster_whisper_dtw":
                return brand_cues_from_lyrics(lyric_report, brand)
            return detect_vocal_brand_cues(track, brand, self.settings)

        vocal_brand_report = self._stage(
            manifest,
            "brand_vocal_analysis",
            analyze_brand_vocals,
        )
        paths.write_json("music/vocal_brand_cues.json", vocal_brand_report)
        storyboard = self._stage(
            manifest,
            "storyboard",
            lambda: build_racing_storyboard(
                beat_map,
                title=title,
                brand=brand,
                max_duration_seconds=max_duration_seconds,
                fps=self.settings.video.fps,
                visual_direction=visual_direction,
                hook_words=hook_words,
                edit_style=edit_style,
                vocal_brand_cues=vocal_brand_report.cues,
                lyric_report=lyric_report,
            ),
        )
        if performer_mode == "malaysian_duet":
            project_root = Path(__file__).resolve().parents[2]
            male_reference = (
                male_performer_reference
                or project_root / "assets/pragon/performers/malaysian-male-lead.png"
            ).resolve()
            female_reference = (
                female_performer_reference
                or project_root / "assets/pragon/performers/malaysian-female-lead.png"
            ).resolve()
            group_reference = (
                friend_group_reference
                or project_root / "assets/pragon/performers/malaysian-friend-group-v2.png"
            ).resolve()
            if self.settings.video.performance_stem_analysis:
                stem_report = self._stage(
                    manifest,
                    "performance_stem_analysis",
                    lambda: analyze_performance_stems(
                        track,
                        storyboard,
                        paths.music / "stems",
                        self.settings.model_directory / "demucs_stems",
                    ),
                )
            else:
                stem_report = PerformanceStemReport(
                    warnings=["Performance stem analysis is disabled in this profile."]
                )
            paths.write_json("music/performance_stems.json", stem_report)
            performer_plan = self._stage(
                manifest,
                "performer_direction",
                lambda: apply_malaysian_duet_plan(
                    storyboard,
                    beat_map,
                    male_reference,
                    female_reference,
                    stem_report,
                    group_reference=group_reference,
                    mix_ratio=self.settings.video.performance_mix_ratio,
                    max_scenes=self.settings.video.performance_max_scenes_per_video,
                ),
            )
            paths.write_json("music/performer_plan.json", performer_plan)
            performance_audio = self._stage(
                manifest,
                "performance_audio_slices",
                lambda: extract_performance_audio(
                    track,
                    storyboard,
                    paths.music / "performance_slices",
                    self.ffmpeg,
                ),
            )
            paths.write_json(
                "music/performance_audio.json",
                {str(index): str(path) for index, path in performance_audio.items()},
            )
        paths.write_json("storyboards/storyboard_timed.json", storyboard)

        def validate_sync() -> SyncReport:
            report = build_sync_report(
                beat_map,
                storyboard,
                self.settings.video.fps,
                lyric_report=lyric_report,
            )
            if beat_map.is_rhythmic and not report.within_frame_tolerance:
                raise RuntimeError(
                    "The generated cut list drifted more than one output frame from the beat grid"
                )
            return report

        sync_report = self._stage(manifest, "sync_validation", validate_sync)
        paths.write_json("music/sync_report.json", sync_report)

        if performer_mode == "malaysian_duet" and lyrics_text and not audit_only:

            def validate_lyrics() -> None:
                if lyric_report.analysis_backend != "faster_whisper_dtw":
                    raise RuntimeError(
                        "Exact lyric timing is unavailable; paid lip-sync generation was stopped"
                    )
                if lyric_report.anchor_coverage < 0.62:
                    raise RuntimeError(
                        f"Lyric anchor coverage is {lyric_report.anchor_coverage:.0%}; "
                        "review lyrics.lrc before paid lip-sync generation"
                    )

            self._stage(manifest, "lyric_sync_gate", validate_lyrics)

        if audit_only:
            manifest.status = RunStatus.ready
            manifest.current_stage = "creative_audit_ready"
            manifest.finished_at = datetime.now(UTC)
            self.store.save_manifest(manifest)
            paths.write_json("manifest.json", manifest)
            return manifest

        images: dict[int, Path] = {}

        def make_images() -> dict[int, Path]:
            generator = SceneImageGenerator(self.settings)
            final_scene_index = storyboard.scenes[-1].index
            strict_stock = self.settings.video.stock_video_require_all_music_scenes
            for scene in storyboard.scenes:
                target = paths.scenes / f"scene_{scene.index:03d}.jpg"
                if scene.index == 1:
                    images[scene.index] = render_racing_title(
                        title,
                        beat_map.bpm,
                        target,
                        self.settings.video.width,
                        self.settings.video.height,
                        brand,
                    )
                elif scene.index == final_scene_index:
                    images[scene.index] = render_pragon_outro(
                        brand,
                        target,
                        self.settings.video.width,
                        self.settings.video.height,
                        title=title,
                    )
                elif strict_stock:
                    # A strict licensed-footage music film cannot use photo-motion fallback.
                    # Avoid downloading stills that the coverage gate will never admit.
                    continue
                elif scene.performer_generation_required and scene.performer_reference:
                    with Image.open(scene.performer_reference) as source:
                        plate = ImageOps.fit(
                            source.convert("RGB"),
                            (self.settings.video.width, self.settings.video.height),
                            method=Image.Resampling.LANCZOS,
                        )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    plate.save(target, format="JPEG", quality=96, subsampling=0)
                    images[scene.index] = target
                else:
                    _provider, images[scene.index] = generator.run(scene, target)
            paths.write_json(
                "scenes/images.json",
                [{"scene": index, "path": str(path)} for index, path in images.items()],
            )
            return images

        self._stage(manifest, "images", make_images)

        performer, performer_costs = self._stage(
            manifest,
            "performer_video",
            lambda: PerformanceSceneScheduler(self.settings).generate(
                storyboard.scenes,
                paths.videos / "performers",
            ),
        )
        manifest.costs.extend(performer_costs)
        protected_performer_ids = {
            scene.index for scene in storyboard.scenes if scene.performer_generation_required
        }
        stock = self._stage(
            manifest,
            "stock_video",
            lambda: StockVideoScheduler(self.settings).generate(
                storyboard.scenes,
                paths.videos / "stock",
                excluded_scene_ids=protected_performer_ids,
            ),
        )

        def validate_stock_coverage() -> None:
            if not self.settings.video.stock_video_require_all_music_scenes:
                return
            required = [
                scene
                for scene in storyboard.scenes
                if scene.visual_mode != "information_card"
                and not scene.performer_generation_required
            ]
            missing = [scene for scene in required if scene.index not in stock]
            if missing:
                detail = "; ".join(
                    f"{scene.index}: {scene.visual_search_query}" for scene in missing[:8]
                )
                raise RuntimeError(
                    f"Licensed-footage coverage gate rejected {len(missing)} scene(s): {detail}"
                )

        self._stage(manifest, "stock_coverage_gate", validate_stock_coverage)
        premium, premium_costs = self._stage(
            manifest,
            "premium_video",
            lambda: PremiumSceneScheduler(self.settings).generate(
                [
                    scene
                    for scene in storyboard.scenes
                    if scene.index not in stock and scene.index not in protected_performer_ids
                ],
                paths.videos / "premium",
            ),
        )
        manifest.costs.extend(premium_costs)

        remaining = [
            scene
            for scene in storyboard.scenes
            if scene.index not in stock
            and scene.index not in premium
            and scene.index not in protected_performer_ids
        ]
        for scene in remaining:
            if scene.ai_generation_required:
                scene.reference_image = images[scene.index]
                scene.generation_task = "image_to_video"
        local, local_costs = self._stage(
            manifest,
            "local_video",
            lambda: LocalSceneScheduler(self.settings).generate(
                remaining,
                paths.videos / "local_ai",
            ),
        )
        manifest.costs.extend(local_costs)
        paths.write_json(
            "videos/selection.json",
            {
                "performer": {str(key): str(value) for key, value in performer.items()},
                "premium": {str(key): str(value) for key, value in premium.items()},
                "local": {str(key): str(value) for key, value in local.items()},
                "stock": {str(key): str(value) for key, value in stock.items()},
                "owned": {
                    str(storyboard.scenes[-1].index): str(images[storyboard.scenes[-1].index])
                },
            },
        )

        renderer = VideoRenderer(self.settings, self.ffmpeg)
        silent = paths.videos / "assembled_silent.mp4"
        # Music-film scene boundaries are already locked to the analyzed beat grid. Blending
        # adjacent focal planes creates a focus-hunt/refocus artifact, so assemble hard cuts.
        music_transition = 0.0

        def render() -> Path:
            rendered: list[Path] = []
            count = len(storyboard.scenes)
            for position, scene in enumerate(storyboard.scenes):
                output = paths.videos / f"scene_{scene.index:03d}.mp4"
                visual_duration = scene.duration_seconds
                if position < count - 1:
                    visual_duration += music_transition
                clip = (
                    performer.get(scene.index)
                    or stock.get(scene.index)
                    or premium.get(scene.index)
                    or local.get(scene.index)
                )
                if clip:
                    renderer.normalize_video_scene(
                        scene, clip, output, duration_seconds=visual_duration
                    )
                else:
                    renderer.render_scene(
                        scene, images[scene.index], output, duration_seconds=visual_duration
                    )
                rendered.append(output)
            return renderer.concatenate(
                rendered,
                silent,
                [scene.duration_seconds for scene in storyboard.scenes],
                transition_seconds=music_transition,
            )

        self._stage(manifest, "render", render)
        paths.write_json("storyboards/storyboard_timed.json", storyboard)
        paths.write_json(
            "videos/edit_windows.json",
            [
                {
                    "scene": scene.index,
                    "track_start_seconds": scene.start_seconds,
                    "duration_seconds": scene.duration_seconds,
                    "music_section": scene.music_section,
                    "music_energy": scene.music_energy,
                    "music_edit_style": scene.music_edit_style,
                    "music_treatment": scene.music_treatment,
                    "music_camera_motion": scene.music_camera_motion,
                    "beat_accents_seconds": scene.beat_accents_seconds,
                    "motion_text_cues": [cue.model_dump() for cue in scene.motion_text_cues],
                    "source_inpoint_seconds": scene.source_inpoint_seconds,
                    "source_inpoint_locked": scene.source_inpoint_locked,
                    "source_stabilization": scene.source_stabilization,
                    "source_reframe_zoom": scene.source_reframe_zoom,
                    "source_reframe_x": scene.source_reframe_x,
                    "source_reframe_y": scene.source_reframe_y,
                }
                for scene in storyboard.scenes
            ],
        )
        master = paths.music / f"master{track.suffix.lower()}"
        shutil.copy2(track, master)
        final = paths.final / "video.mp4"

        def mux() -> Path:
            duration = storyboard.total_duration_seconds
            self.ffmpeg.run(
                [
                    "-i",
                    str(silent),
                    "-i",
                    str(master),
                    "-t",
                    f"{duration:.3f}",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "320k",
                    "-af",
                    "aresample=48000,alimiter=limit=0.98",
                    "-movflags",
                    "+faststart",
                    str(final),
                ]
            )
            return final

        self._stage(manifest, "audio_master", mux)
        manifest.final_video = final
        manifest.thumbnail = images[1]
        manifest.status = RunStatus.ready
        manifest.current_stage = "complete"
        manifest.finished_at = datetime.now(UTC)
        self.store.save_manifest(manifest)
        paths.write_json("manifest.json", manifest)
        return manifest
