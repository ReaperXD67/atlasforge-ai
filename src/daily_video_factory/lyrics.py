from __future__ import annotations

import re
import warnings
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from .config import Settings

LyricSinger = Literal["male", "female", "ensemble", "instrumental"]


class LyricLineSpec(BaseModel):
    index: int = Field(ge=0)
    section: str
    singer: LyricSinger
    text: str
    words: list[str]


class LyricWordCue(BaseModel):
    text: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    matched: bool = False


class LyricLineCue(BaseModel):
    index: int = Field(ge=0)
    section: str
    singer: LyricSinger
    text: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    words: list[LyricWordCue] = Field(default_factory=list)


class LyricTimingReport(BaseModel):
    analysis_backend: Literal["faster_whisper_dtw", "estimated", "unavailable"]
    language: str = ""
    supplied_word_count: int = Field(default=0, ge=0)
    matched_word_count: int = Field(default=0, ge=0)
    anchor_coverage: float = Field(default=0, ge=0, le=1)
    mean_anchor_confidence: float = Field(default=0, ge=0, le=1)
    lines: list[LyricLineCue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


_SECTION_SINGERS: dict[str, LyricSinger] = {
    "intro": "ensemble",
    "chorus": "ensemble",
    "verse 1": "male",
    "verse 2": "female",
    "verse 3": "male",
    "pre-chorus": "female",
    "pre chorus": "female",
    "guitar solo": "instrumental",
    "outro": "ensemble",
}


def _tokens(value: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*", value)


def _normalized_word(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def parse_lyrics(value: str) -> list[LyricLineSpec]:
    """Parse section/directing annotations while retaining only words that are actually sung."""
    section = "song"
    singer: LyricSinger = "ensemble"
    result: list[LyricLineSpec] = []
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            annotation = line[1:-1].strip()
            lowered = annotation.casefold()
            if lowered in _SECTION_SINGERS:
                section = annotation
                singer = _SECTION_SINGERS[lowered]
            elif "female vocal" in lowered:
                singer = "female"
            elif "male vocal" in lowered:
                singer = "male"
            continue
        words = _tokens(line)
        if not words:
            continue
        line_singer = singer
        if line_singer == "instrumental":
            # Ad-libs inside a solo are ensemble vocal responses, not an instrumental action cue.
            line_singer = "ensemble"
        result.append(
            LyricLineSpec(
                index=len(result),
                section=section,
                singer=line_singer,
                text=line,
                words=words,
            )
        )
    return result


def _transcribe_words(
    track: Path,
    settings: Settings,
    language: str,
) -> tuple[list[tuple[str, float, float, float]], str]:
    from faster_whisper import WhisperModel

    configured = settings.subtitles.whisper_model
    model_name = configured[:-3] if configured.endswith(".en") else configured

    def transcribe(
        device: str, compute_type: str
    ) -> tuple[list[tuple[str, float, float, float]], str]:
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            download_root=str(settings.model_directory / "whisper"),
        )
        segments, info = model.transcribe(
            str(track),
            language=None if language == "auto" else language,
            beam_size=5,
            vad_filter=False,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        words: list[tuple[str, float, float, float]] = []
        for segment in segments:
            for word in getattr(segment, "words", None) or []:
                raw = str(getattr(word, "word", "")).strip()
                normalized = _normalized_word(raw)
                start = getattr(word, "start", None)
                end = getattr(word, "end", None)
                probability = getattr(word, "probability", None)
                if normalized and start is not None and end is not None:
                    words.append(
                        (
                            raw,
                            float(start),
                            float(end),
                            float(probability) if probability is not None else 0.5,
                        )
                    )
        detected = str(getattr(info, "language", language if language != "auto" else ""))
        return words, detected

    device = settings.subtitles.whisper_device
    compute_type = settings.subtitles.whisper_compute_type
    try:
        return transcribe(device, compute_type)
    except RuntimeError as exc:
        detail = str(exc).casefold()
        if device == "cpu" or not any(token in detail for token in ("cuda", "cublas", "cudnn")):
            raise
        warnings.warn(
            "Whisper CUDA runtime is unavailable; retrying lyric alignment on CPU/int8.",
            RuntimeWarning,
            stacklevel=2,
        )
        return transcribe("cpu", "int8")


def _similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _monotonic_matches(
    supplied: list[str],
    observed: list[str],
) -> dict[int, tuple[int, float]]:
    """Globally align repeated hooks without letting later choruses jump backwards in time."""
    rows = len(supplied) + 1
    columns = len(observed) + 1
    gap = -0.72
    scores = np.empty((rows, columns), dtype=np.float32)
    moves = np.zeros((rows, columns), dtype=np.int8)
    scores[:, 0] = np.arange(rows, dtype=np.float32) * gap
    scores[0, :] = np.arange(columns, dtype=np.float32) * gap
    for row in range(1, rows):
        for column in range(1, columns):
            similarity = _similarity(supplied[row - 1], observed[column - 1])
            match_score = 2.1 * similarity - 0.95
            diagonal = scores[row - 1, column - 1] + match_score
            delete = scores[row - 1, column] + gap
            insert = scores[row, column - 1] + gap
            best = max(diagonal, delete, insert)
            scores[row, column] = best
            moves[row, column] = 1 if best == diagonal else 2 if best == delete else 3
    row = len(supplied)
    column = len(observed)
    matches: dict[int, tuple[int, float]] = {}
    while row > 0 or column > 0:
        move = moves[row, column] if row > 0 and column > 0 else 2 if row > 0 else 3
        if move == 1:
            similarity = _similarity(supplied[row - 1], observed[column - 1])
            if similarity >= 0.55:
                matches[row - 1] = (column - 1, similarity)
            row -= 1
            column -= 1
        elif move == 2:
            row -= 1
        else:
            column -= 1
    return matches


def _estimated_report(
    specs: list[LyricLineSpec],
    duration_seconds: float,
    warning: str,
) -> LyricTimingReport:
    total_words = sum(len(line.words) for line in specs)
    usable_start = min(2.0, duration_seconds * 0.05)
    usable_end = max(usable_start + 0.5, duration_seconds - min(1.2, duration_seconds * 0.03))
    cursor = usable_start
    lines: list[LyricLineCue] = []
    for spec in specs:
        share = len(spec.words) / max(1, total_words)
        line_duration = max(0.5, (usable_end - usable_start) * share)
        end = min(usable_end, cursor + line_duration)
        step = max(0.08, (end - cursor) / max(1, len(spec.words)))
        words = [
            LyricWordCue(
                text=word,
                start_seconds=round(cursor + index * step, 3),
                end_seconds=round(min(end, cursor + (index + 1) * step), 3),
                confidence=0,
            )
            for index, word in enumerate(spec.words)
        ]
        lines.append(
            LyricLineCue(
                index=spec.index,
                section=spec.section,
                singer=spec.singer,
                text=spec.text,
                start_seconds=round(cursor, 3),
                end_seconds=round(end, 3),
                confidence=0,
                words=words,
            )
        )
        cursor = end
    return LyricTimingReport(
        analysis_backend="estimated",
        language="",
        supplied_word_count=total_words,
        lines=lines,
        warnings=[warning],
    )


def align_supplied_lyrics(
    track: Path,
    lyrics_text: str,
    settings: Settings,
    *,
    duration_seconds: float,
    language: str = "auto",
) -> LyricTimingReport:
    """Align editor-approved lyrics to an unprompted ASR pass and expose honest coverage."""
    specs = parse_lyrics(lyrics_text)
    if not specs:
        return LyricTimingReport(
            analysis_backend="unavailable",
            language=language,
            warnings=["No sung lyric lines were supplied."],
        )
    try:
        observed, detected_language = _transcribe_words(track, settings, language)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        return _estimated_report(
            specs,
            duration_seconds,
            f"Exact lyric alignment was unavailable ({type(exc).__name__}: {exc}).",
        )
    supplied_flat = [word for line in specs for word in line.words]
    supplied_normalized = [_normalized_word(word) for word in supplied_flat]
    observed_normalized = [_normalized_word(word[0]) for word in observed]
    matches = _monotonic_matches(supplied_normalized, observed_normalized)
    if not observed or not matches:
        return _estimated_report(
            specs,
            duration_seconds,
            "The vocal ASR pass found no reliable lyric anchors; timings are estimated.",
        )

    flat_to_line: list[tuple[int, int]] = []
    for line_index, spec in enumerate(specs):
        flat_to_line.extend((line_index, word_index) for word_index in range(len(spec.words)))
    matched_by_line: dict[int, dict[int, tuple[float, float, float, float]]] = {}
    anchor_confidences: list[float] = []
    for supplied_index, (observed_index, similarity) in matches.items():
        line_index, word_index = flat_to_line[supplied_index]
        _raw, start, end, probability = observed[observed_index]
        confidence = float(np.clip(similarity * probability, 0, 1))
        matched_by_line.setdefault(line_index, {})[word_index] = (
            start,
            end,
            confidence,
            similarity,
        )
        anchor_confidences.append(confidence)

    line_bounds: list[tuple[float | None, float | None]] = []
    for line_index, spec in enumerate(specs):
        line_matches = matched_by_line.get(line_index, {})
        if line_matches:
            first_index = min(line_matches)
            last_index = max(line_matches)
            first = line_matches[first_index][0] - first_index * 0.26
            last = line_matches[last_index][1] + (len(spec.words) - last_index - 1) * 0.26
            line_bounds.append((max(0.0, first), min(duration_seconds, last)))
        else:
            line_bounds.append((None, None))

    known = [index for index, (start, _end) in enumerate(line_bounds) if start is not None]
    if not known:
        return _estimated_report(
            specs, duration_seconds, "No lyric lines retained a timing anchor."
        )

    def known_bound(index: int, position: int) -> float:
        value = line_bounds[index][position]
        if value is None:
            raise RuntimeError("Internal lyric alignment bound is missing")
        return value

    for line_index, (bound_start, bound_end) in enumerate(line_bounds):
        if bound_start is not None and bound_end is not None:
            continue
        previous = max((value for value in known if value < line_index), default=None)
        following = min((value for value in known if value > line_index), default=None)
        if previous is None:
            following_start = known_bound(following, 0) if following is not None else 2.0
            estimated_start = (
                max(0.0, following_start - (following - line_index) * 2.2)
                if following is not None
                else 0.0
            )
        elif following is None:
            previous_end = known_bound(previous, 1)
            estimated_start = previous_end + (line_index - previous - 1) * 2.2
        else:
            previous_end = known_bound(previous, 1)
            following_start = known_bound(following, 0)
            fraction = (line_index - previous) / (following - previous)
            estimated_start = previous_end + max(0.0, following_start - previous_end) * fraction
        estimated_end = min(
            duration_seconds, estimated_start + max(0.7, len(specs[line_index].words) * 0.32)
        )
        line_bounds[line_index] = (estimated_start, estimated_end)

    # Enforce a monotonic readable clock. This cannot invent confidence: interpolated words stay 0.
    lines: list[LyricLineCue] = []
    previous_end = 0.0
    for line_index, spec in enumerate(specs):
        raw_start, raw_end = line_bounds[line_index]
        start = max(previous_end, float(raw_start or previous_end))
        end = max(start + 0.35, min(duration_seconds, float(raw_end or start + 1.0)))
        next_bound = line_bounds[line_index + 1][0] if line_index + 1 < len(line_bounds) else None
        following_start = float(next_bound) if next_bound is not None else duration_seconds
        if following_start > start:
            end = min(end, max(start + 0.35, following_start - 0.03))
        line_matches = matched_by_line.get(line_index, {})
        word_cues: list[LyricWordCue] = []
        cursor = start
        for word_index, word in enumerate(spec.words):
            match = line_matches.get(word_index)
            if match:
                word_start = max(cursor, match[0])
                word_end = max(word_start + 0.06, match[1])
                confidence = match[2]
                matched = True
            else:
                remaining = max(1, len(spec.words) - word_index)
                step = max(0.08, (end - cursor) / remaining)
                word_start = cursor
                word_end = min(end, cursor + step)
                confidence = 0.0
                matched = False
            word_cues.append(
                LyricWordCue(
                    text=word,
                    start_seconds=round(word_start, 3),
                    end_seconds=round(word_end, 3),
                    confidence=round(confidence, 4),
                    matched=matched,
                )
            )
            cursor = word_end
        matched_values = [item.confidence for item in word_cues if item.matched]
        lines.append(
            LyricLineCue(
                index=spec.index,
                section=spec.section,
                singer=spec.singer,
                text=spec.text,
                start_seconds=round(start, 3),
                end_seconds=round(end, 3),
                confidence=round(float(np.mean(matched_values)) if matched_values else 0.0, 4),
                words=word_cues,
            )
        )
        previous_end = end

    coverage = len(matches) / max(1, len(supplied_flat))
    warnings: list[str] = []
    if coverage < 0.62:
        warnings.append(
            "Lyric anchor coverage is below 62%; review the generated LRC before paid lip-sync generation."
        )
    return LyricTimingReport(
        analysis_backend="faster_whisper_dtw",
        language=detected_language,
        supplied_word_count=len(supplied_flat),
        matched_word_count=len(matches),
        anchor_coverage=round(coverage, 4),
        mean_anchor_confidence=round(float(np.mean(anchor_confidences)), 4),
        lines=lines,
        warnings=warnings,
    )


def remotion_captions(report: LyricTimingReport) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    first = True
    for line in report.lines:
        for word in line.words:
            result.append(
                {
                    "text": word.text if first else f" {word.text}",
                    "startMs": round(word.start_seconds * 1000),
                    "endMs": round(word.end_seconds * 1000),
                    "timestampMs": round(word.start_seconds * 1000),
                    "confidence": word.confidence,
                }
            )
            first = False
    return result


def lrc_text(report: LyricTimingReport) -> str:
    def stamp(seconds: float) -> str:
        minutes = int(seconds // 60)
        remainder = seconds - minutes * 60
        return f"[{minutes:02d}:{remainder:05.2f}]"

    return "\n".join(f"{stamp(line.start_seconds)}{line.text}" for line in report.lines) + "\n"
