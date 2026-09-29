from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..config import Settings
from ..logging import get_logger
from ..models import ScriptDocument, SubtitleCue

log = get_logger(component="subtitles")


def _timestamp_srt(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _timestamp_ass(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def build_cues(
    script: ScriptDocument, duration_seconds: float, max_words: int
) -> list[SubtitleCue]:
    words = re.findall(r"\S+", re.sub(r"\s+", " ", script.full_text).strip())
    if not words:
        return []
    groups: list[list[str]] = []
    for index in range(0, len(words), max_words):
        groups.append(words[index : index + max_words])
    total_words = len(words)
    cues: list[SubtitleCue] = []
    elapsed_words = 0
    for index, group in enumerate(groups, start=1):
        start = duration_seconds * elapsed_words / total_words
        elapsed_words += len(group)
        end = duration_seconds * elapsed_words / total_words
        cues.append(
            SubtitleCue(index=index, start_seconds=start, end_seconds=end, text=" ".join(group))
        )
    return cues


def build_whisper_cues(
    narration: Path,
    script: ScriptDocument,
    max_words: int,
    settings: Settings,
) -> list[SubtitleCue]:
    """Use Whisper for timing while keeping the authored script as caption truth."""
    timed_words = transcribe_timed_words(narration, settings)
    if not timed_words:
        return []
    canonical = re.findall(r"\S+", re.sub(r"\s+", " ", script.full_text).strip())
    aligned = _align_script_words(canonical, timed_words)
    cues: list[SubtitleCue] = []
    for group in _caption_groups(aligned, max_words):
        cues.append(
            SubtitleCue(
                index=len(cues) + 1,
                start_seconds=group[0][1],
                end_seconds=max(group[-1][2], group[0][1] + 0.12),
                text=" ".join(value[0] for value in group),
            )
        )
    return cues


def transcribe_timed_words(
    narration: Path, settings: Settings
) -> list[tuple[str, float, float]]:
    """Return ASR word anchors for providers that do not expose synthesis boundaries."""
    from faster_whisper import WhisperModel

    cfg = settings.subtitles
    model = WhisperModel(
        cfg.whisper_model,
        device=cfg.whisper_device,
        compute_type=cfg.whisper_compute_type,
        download_root=str(settings.model_directory / "whisper"),
    )
    segments, _info = model.transcribe(
        str(narration),
        beam_size=3,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt="Correct brand terms: " + ", ".join(cfg.glossary) + ".",
        hotwords=" ".join(cfg.glossary),
    )
    timed_words: list[tuple[str, float, float]] = []
    for segment in segments:
        for word in getattr(segment, "words", None) or []:
            text = str(getattr(word, "word", "")).strip()
            start = getattr(word, "start", None)
            end = getattr(word, "end", None)
            if text and start is not None and end is not None:
                timed_words.append((text, float(start), float(end)))
    return timed_words


def write_forced_aligned_caption_sidecars(
    canonical_text: str,
    narration: Path,
    output_dir: Path,
    settings: Settings,
) -> list[SubtitleCue]:
    """Create canonical caption sidecars using ASR only as a timing reference."""
    timed_words = transcribe_timed_words(narration, settings)
    if not timed_words:
        raise RuntimeError("Whisper returned no word timing anchors")
    return write_exact_caption_sidecars(
        canonical_text,
        timed_words,
        output_dir,
        max_words=settings.voice.edge_caption_max_words,
        minimum_seconds=settings.voice.edge_caption_min_seconds,
    )


def _normalize_word(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _align_script_words(
    canonical: list[str], recognized: list[tuple[str, float, float]]
) -> list[tuple[str, float, float]]:
    """Force-align canonical words onto ASR anchors, correcting names and hallucinations."""
    if not canonical:
        return []
    if not recognized:
        return []
    canonical_keys = [_normalize_word(word) for word in canonical]
    recognized_keys = [_normalize_word(word[0]) for word in recognized]
    matcher = difflib.SequenceMatcher(None, canonical_keys, recognized_keys, autojunk=False)
    anchors: dict[int, tuple[float, float]] = {}
    for canonical_start, recognized_start, size in matcher.get_matching_blocks():
        for offset in range(size):
            _text, start, end = recognized[recognized_start + offset]
            anchors[canonical_start + offset] = (start, end)

    # When ASR misses or misspells a scripted word (Atomy -> ADAMI), interpolate it between
    # surrounding anchors. ASR insertions are intentionally discarded.
    total_end = max(end for _text, _start, end in recognized)
    timestamps: list[tuple[float, float] | None] = [
        anchors.get(index) for index in range(len(canonical))
    ]
    index = 0
    while index < len(timestamps):
        if timestamps[index] is not None:
            index += 1
            continue
        gap_start = index
        while index < len(timestamps) and timestamps[index] is None:
            index += 1
        gap_end = index
        left_anchor = timestamps[gap_start - 1] if gap_start > 0 else None
        right_anchor = timestamps[gap_end] if gap_end < len(timestamps) else None
        left = left_anchor[1] if left_anchor is not None else 0.0
        right = right_anchor[0] if right_anchor is not None else total_end
        right = max(right, left + 0.12 * (gap_end - gap_start))
        weights = [max(1, len(_normalize_word(word))) for word in canonical[gap_start:gap_end]]
        total_weight = sum(weights)
        elapsed = left
        for offset, weight in enumerate(weights):
            word_duration = (right - left) * weight / total_weight
            timestamps[gap_start + offset] = (elapsed, elapsed + word_duration)
            elapsed += word_duration

    aligned: list[tuple[str, float, float]] = []
    previous_end = 0.0
    for word, timing in zip(canonical, timestamps, strict=True):
        start, end = timing or (previous_end, previous_end + 0.12)
        start = max(previous_end, start)
        end = max(start + 0.06, end)
        aligned.append((word, start, end))
        previous_end = end
    return aligned


def _caption_groups(
    words: list[tuple[str, float, float]], max_words: int
) -> list[list[tuple[str, float, float]]]:
    groups: list[list[tuple[str, float, float]]] = []
    current: list[tuple[str, float, float]] = []
    minimum_before_punctuation_break = max(3, max_words // 2)
    for word in words:
        current.append(word)
        sentence_break = word[0].endswith((".", "?", "!", ";", ":"))
        if len(current) >= max_words or (
            sentence_break and len(current) >= minimum_before_punctuation_break
        ):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _timed_caption_groups(
    words: list[tuple[str, float, float]],
    *,
    max_words: int,
    target_seconds: float,
    max_seconds: float = 6.5,
) -> list[list[tuple[str, float, float]]]:
    """Build readable, strictly bounded phrases without moving real word anchors."""
    groups: list[list[tuple[str, float, float]]] = []
    current: list[tuple[str, float, float]] = []
    for word in words:
        if current and (
            len(current) >= max_words or word[2] - current[0][1] > max_seconds
        ):
            groups.append(current)
            current = []
        current.append(word)
        duration = current[-1][2] - current[0][1]
        sentence_break = word[0].endswith((".", "?", "!", ";", ":"))
        if (
            len(current) >= max_words
            or duration >= max_seconds
            or (sentence_break and duration >= target_seconds)
        ):
            groups.append(current)
            current = []
    if current:
        tail_duration = current[-1][2] - current[0][1]
        if (
            groups
            and tail_duration < 1.25
            and len(groups[-1]) + len(current) <= max_words
            and current[-1][2] - groups[-1][0][1] <= max_seconds
        ):
            groups[-1].extend(current)
        else:
            groups.append(current)
    return groups


def write_exact_caption_sidecars(
    canonical_text: str,
    timed_words: list[tuple[str, float, float]],
    output_dir: Path,
    *,
    max_words: int,
    minimum_seconds: float,
) -> list[SubtitleCue]:
    """Persist authored captions anchored to real synthesis or ASR word timings."""
    canonical = re.findall(r"\S+", re.sub(r"\s+", " ", canonical_text).strip())
    aligned = _align_script_words(canonical, timed_words)
    cues = [
        SubtitleCue(
            index=index,
            start_seconds=group[0][1],
            end_seconds=max(group[-1][2], group[0][1] + 0.12),
            text=" ".join(value[0] for value in group),
        )
        for index, group in enumerate(
            _timed_caption_groups(
                aligned,
                max_words=max_words,
                target_seconds=minimum_seconds,
            ),
            start=1,
        )
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    word_payload = [
        {"text": text, "start": round(start, 4), "end": round(end, 4)}
        for text, start, end in aligned
    ]
    cue_payload = [
        {
            "index": cue.index,
            "start": round(cue.start_seconds, 4),
            "end": round(cue.end_seconds, 4),
            "duration": round(cue.end_seconds - cue.start_seconds, 4),
            "text": cue.text,
        }
        for cue in cues
    ]
    (output_dir / "narration.words.json").write_text(
        json.dumps(word_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "narration.captions.json").write_text(
        json.dumps(cue_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    exact_text = " ".join(item["text"] for item in word_payload) == " ".join(canonical)
    monotonic = all(
        float(current["start"]) >= float(previous["end"])
        for previous, current in zip(word_payload, word_payload[1:], strict=False)
    )
    verification = {
        "exact_authored_text": exact_text,
        "monotonic_word_timings": monotonic,
        "script_sha256": hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
        "word_count": len(word_payload),
        "cue_count": len(cue_payload),
        "maximum_words_per_cue": max(
            (len(str(item["text"]).split()) for item in cue_payload), default=0
        ),
        "first_word_start": word_payload[0]["start"] if word_payload else None,
        "last_word_end": word_payload[-1]["end"] if word_payload else None,
    }
    if not exact_text or not monotonic:
        raise RuntimeError(f"Exact caption verification failed: {verification}")
    (output_dir / "narration.caption-verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8"
    )
    blocks = [
        f"{cue.index}\n{_timestamp_srt(cue.start_seconds)} --> {_timestamp_srt(cue.end_seconds)}\n{cue.text}"
        for cue in cues
    ]
    (output_dir / "narration.exact.srt").write_text(
        "\n\n".join(blocks) + "\n", encoding="utf-8"
    )
    return cues


def rebuild_exact_caption_sidecars(
    canonical_text: str,
    output_dir: Path,
    *,
    max_words: int,
    minimum_seconds: float,
) -> list[SubtitleCue]:
    """Reflow an existing exact word track without synthesizing the voice again."""
    words_path = output_dir / "narration.words.json"
    if not words_path.is_file():
        raise FileNotFoundError(f"Exact word timing file not found: {words_path}")
    payload: list[dict[str, Any]] = json.loads(words_path.read_text(encoding="utf-8"))
    timed_words = [
        (str(item["text"]), float(item["start"]), float(item["end"])) for item in payload
    ]
    return write_exact_caption_sidecars(
        canonical_text,
        timed_words,
        output_dir,
        max_words=max_words,
        minimum_seconds=minimum_seconds,
    )


def scale_exact_caption_sidecars(output_dir: Path, factor: float) -> None:
    """Scale exact timing sidecars after pitch-preserving duration fitting."""
    if factor <= 0:
        raise ValueError("Caption timing scale must be positive")
    words_path = output_dir / "narration.words.json"
    captions_path = output_dir / "narration.captions.json"
    if not words_path.is_file() or not captions_path.is_file():
        return
    words: list[dict[str, Any]] = json.loads(words_path.read_text(encoding="utf-8"))
    captions: list[dict[str, Any]] = json.loads(captions_path.read_text(encoding="utf-8"))
    for item in words:
        item["start"] = round(float(item["start"]) * factor, 4)
        item["end"] = round(float(item["end"]) * factor, 4)
    for item in captions:
        item["start"] = round(float(item["start"]) * factor, 4)
        item["end"] = round(float(item["end"]) * factor, 4)
        item["duration"] = round(float(item["end"]) - float(item["start"]), 4)
    words_path.write_text(
        json.dumps(words, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    captions_path.write_text(
        json.dumps(captions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    blocks = [
        f"{index}\n{_timestamp_srt(float(item['start']))} --> {_timestamp_srt(float(item['end']))}\n{item['text']}"
        for index, item in enumerate(captions, start=1)
    ]
    (output_dir / "narration.exact.srt").write_text(
        "\n\n".join(blocks) + "\n", encoding="utf-8"
    )
    verification_path = output_dir / "narration.caption-verification.json"
    if verification_path.is_file():
        verification: dict[str, Any] = json.loads(
            verification_path.read_text(encoding="utf-8")
        )
        if verification.get("first_word_start") is not None:
            verification["first_word_start"] = round(
                float(verification["first_word_start"]) * factor, 4
            )
        if verification.get("last_word_end") is not None:
            verification["last_word_end"] = round(
                float(verification["last_word_end"]) * factor, 4
            )
        verification_path.write_text(
            json.dumps(verification, indent=2) + "\n", encoding="utf-8"
        )


def _merge_short_cues(cues: list[SubtitleCue], minimum_seconds: float) -> list[SubtitleCue]:
    """Keep readable text on screen long enough to register without desynchronizing it.

    Consecutive short cues are merged, preserving their original start and end anchors. The
    final short cue is folded into the preceding cue so the track remains continuous.
    """
    if minimum_seconds <= 1.0 or len(cues) < 2:
        return cues
    merged: list[SubtitleCue] = []
    pending: list[SubtitleCue] = []
    for cue in cues:
        pending.append(cue)
        span = pending[-1].end_seconds - pending[0].start_seconds
        if span >= minimum_seconds:
            merged.append(
                SubtitleCue(
                    index=len(merged) + 1,
                    start_seconds=pending[0].start_seconds,
                    end_seconds=pending[-1].end_seconds,
                    text=" ".join(item.text for item in pending),
                )
            )
            pending = []
    if pending:
        if merged:
            previous = merged.pop()
            merged.append(
                SubtitleCue(
                    index=len(merged) + 1,
                    start_seconds=previous.start_seconds,
                    end_seconds=pending[-1].end_seconds,
                    text=" ".join([previous.text, *(item.text for item in pending)]),
                )
            )
        else:
            merged.append(
                SubtitleCue(
                    index=1,
                    start_seconds=pending[0].start_seconds,
                    end_seconds=pending[-1].end_seconds,
                    text=" ".join(item.text for item in pending),
                )
            )
    return merged


def _ass_caption_text(text: str, settings: Settings) -> str:
    escaped = text.replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")
    glossary = sorted(settings.subtitles.glossary, key=len, reverse=True)
    if not glossary:
        return escaped
    pattern = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(term) for term in glossary) + r")(?!\w)",
        flags=re.IGNORECASE,
    )
    accent = settings.subtitles.highlight_color.rstrip("&")
    return pattern.sub(lambda match: rf"{{\c{accent}&}}{match.group(0)}{{\c&H00FFFFFF&}}", escaped)


def write_subtitles(
    script: ScriptDocument,
    duration_seconds: float,
    srt_path: Path,
    ass_path: Path,
    settings: Settings,
    *,
    narration: Path | None = None,
) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    alignment = settings.subtitles.alignment
    if narration is not None and alignment in {"auto", "whisper"}:
        try:
            cues = build_whisper_cues(
                narration,
                script,
                settings.subtitles.max_words_per_caption,
                settings,
            )
            if not cues:
                raise RuntimeError("Whisper returned no timed words")
        except Exception as exc:
            if alignment == "whisper":
                raise
            log.warning("subtitle_alignment_fallback", error=str(exc))
    if not cues:
        cues = build_cues(script, duration_seconds, settings.subtitles.max_words_per_caption)
    cues = _merge_short_cues(cues, settings.subtitles.minimum_caption_seconds)
    srt_blocks = [
        f"{cue.index}\n{_timestamp_srt(cue.start_seconds)} --> {_timestamp_srt(cue.end_seconds)}\n{cue.text}"
        for cue in cues
    ]
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")

    cfg = settings.subtitles
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {settings.video.width}
PlayResY: {settings.video.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{cfg.font_name},{cfg.font_size},&H00FFFFFF,{cfg.highlight_color},&HCC080B12,&H66080B12,-1,0,0,0,100,100,0,0,1,4,1,2,120,120,84,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue: list[str] = []
    for cue in cues:
        text = _ass_caption_text(cue.text, settings)
        animation = r"{\fad(90,120)\fscx92\fscy92\t(0,160,\fscx100\fscy100)}"
        dialogue.append(
            f"Dialogue: 0,{_timestamp_ass(cue.start_seconds)},{_timestamp_ass(cue.end_seconds)},"
            f"Default,,0,0,0,,{animation}{text}"
        )
    ass_path.write_text(header + "\n".join(dialogue) + "\n", encoding="utf-8-sig")
    return cues
