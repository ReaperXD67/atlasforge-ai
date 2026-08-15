from __future__ import annotations

import re
from pathlib import Path

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
    max_words: int,
    settings: Settings,
) -> list[SubtitleCue]:
    """Align captions to synthesized speech locally with faster-whisper word timestamps."""
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
    )
    timed_words: list[tuple[str, float, float]] = []
    for segment in segments:
        for word in getattr(segment, "words", None) or []:
            text = str(getattr(word, "word", "")).strip()
            start = getattr(word, "start", None)
            end = getattr(word, "end", None)
            if text and start is not None and end is not None:
                timed_words.append((text, float(start), float(end)))
    cues: list[SubtitleCue] = []
    for start_index in range(0, len(timed_words), max_words):
        group = timed_words[start_index : start_index + max_words]
        cues.append(
            SubtitleCue(
                index=len(cues) + 1,
                start_seconds=group[0][1],
                end_seconds=max(group[-1][2], group[0][1] + 0.12),
                text=" ".join(value[0] for value in group),
            )
        )
    return cues


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
        text = cue.text.replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")
        animation = r"{\fad(90,120)\fscx92\fscy92\t(0,160,\fscx100\fscy100)}"
        dialogue.append(
            f"Dialogue: 0,{_timestamp_ass(cue.start_seconds)},{_timestamp_ass(cue.end_seconds)},"
            f"Default,,0,0,0,,{animation}{text}"
        )
    ass_path.write_text(header + "\n".join(dialogue) + "\n", encoding="utf-8-sig")
    return cues
