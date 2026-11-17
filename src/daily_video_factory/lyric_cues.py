"""Align supplied lyrics locally and export cue timings for the lyric editor."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

from pydantic import BaseModel, FiniteFloat, ValidationError

from .artifacts import atomic_write
from .config import load_settings
from .lyrics import align_supplied_lyrics
from .media.ffmpeg import FFmpeg

MINIMUM_ANCHOR_COVERAGE = 0.62


class Cue(BaseModel, strict=True, frozen=True):
    text: str
    start: FiniteFloat
    end: FiniteFloat
    section: str = ""


def _validate_cues(payload: object, duration: float) -> list[Cue]:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("The recording duration must be a finite, positive number.")
    if isinstance(payload, dict):
        payload = payload.get("cues")
    if not isinstance(payload, list) or not payload:
        raise ValueError("Provide a nonempty cue array or an object with a nonempty 'cues' array.")

    cues: list[Cue] = []
    previous_end = 0.0
    for number, value in enumerate(payload, start=1):
        try:
            cue = Cue.model_validate(value)
        except ValidationError as exc:
            error = exc.errors(include_input=False, include_url=False)[0]
            field = ".".join(map(str, error["loc"]))
            raise ValueError(f"Cue {number}{f' {field}' if field else ''}: {error['msg']}.") from exc
        if not cue.text.strip():
            raise ValueError(f"Cue {number} needs lyric text.")
        if not 0 <= cue.start < cue.end <= duration:
            raise ValueError(
                f"Cue {number} needs 0 <= start < end <= {duration:.6f} seconds "
                f"(received {cue.start:g}–{cue.end:g})."
            )
        if cue.start < previous_end:
            raise ValueError(
                f"Cue {number} starts at {cue.start:g}s before cue {number - 1} ends "
                f"at {previous_end:g}s. Sort cues and remove the overlap."
            )
        cues.append(cue)
        previous_end = cue.end
    return cues


def load_cues(path: Path, duration: float) -> list[Cue]:
    """Read an editor export, preserving visible text and checking its time bounds."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read cue JSON from {path}: {exc}") from exc
    if isinstance(payload, dict) and payload.get("status") == "needs_review":
        raise ValueError("Open this draft in the lyric editor, review the timing, and export its cues.")
    return _validate_cues(payload, duration)


def _write_json(path: Path, value: object) -> None:
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def _audio_duration(path: Path) -> float:
    try:
        duration = FFmpeg().duration(path)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"ffprobe could not determine the duration of {path}.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"ffprobe returned an invalid recording duration for {path}.")
    return duration


def _generate(args: argparse.Namespace, report_path: Path) -> None:
    result: dict[str, object] = {
        "audio": args.audio.name,
        "lyrics": args.lyrics.name,
        "minimum_anchor_coverage": MINIMUM_ANCHOR_COVERAGE,
    }
    status = "error"
    try:
        duration = _audio_duration(args.audio)
        result["duration_seconds"] = duration
        lyric_text = args.lyrics.read_text(encoding="utf-8-sig")
        report = align_supplied_lyrics(
            args.audio,
            lyric_text,
            load_settings(args.config),
            duration_seconds=duration,
            language=args.language,
        )
        result["alignment"] = json.loads(report.model_dump_json())
        if not report.lines:
            raise ValueError("No lyric timings were produced. Check the lyric file and alignment report.")
        cues = _validate_cues(
            [
                {
                    "text": line.text,
                    "start": line.start_seconds,
                    # The aligner serializes milliseconds. Its final cue can round up.
                    "end": min(line.end_seconds, duration)
                    if line.end_seconds <= round(duration, 3)
                    else line.end_seconds,
                    "section": line.section,
                }
                for line in report.lines
            ],
            duration,
        )
        records = [cue.model_dump() for cue in cues]
        if (
            report.analysis_backend != "faster_whisper_dtw"
            or report.anchor_coverage < MINIMUM_ANCHOR_COVERAGE
        ):
            status = "needs_review"
            if args.review_output is not None:
                _write_json(args.review_output, {"status": status, "draft_cues": records})
            review = (
                f"Review {args.review_output} in the lyric editor."
                if args.review_output is not None
                else "Use --review-output to save a draft for the lyric editor."
            )
            raise ValueError(
                f"Vocal anchor coverage is {report.anchor_coverage:.1%} "
                f"({report.analysis_backend}). Verify that the lyrics match the recording. {review}"
            )
        _write_json(args.output, records)
        status = "ready"
    except (OSError, ValueError, RuntimeError) as exc:
        result["message"] = str(exc)
        raise
    finally:
        result["status"] = status
        _write_json(report_path, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True, help="Original recording")
    parser.add_argument("--lyrics", type=Path, required=True, help="UTF-8 lyrics")
    parser.add_argument("--output", type=Path, required=True, help="Validated cue JSON")
    parser.add_argument(
        "--review-output", type=Path, help="Optional editor-only JSON for low-confidence drafts"
    )
    parser.add_argument("--language", default="auto", help="Whisper language, e.g. zh, en, or auto")
    parser.add_argument("--config", type=Path, help="AtlasForge YAML, defaults to normal configuration")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"(?:auto|[a-z]{2})", args.language):
        parser.error("--language must be 'auto' or a two-letter language code such as 'zh'")

    report_path = args.output.with_suffix(".alignment.json")
    outputs = [args.output, report_path]
    if args.review_output is not None:
        outputs.append(args.review_output)
    resolved_outputs = {path.resolve() for path in outputs}
    resolved_inputs = {
        path.resolve() for path in (args.audio, args.lyrics, args.config) if path is not None
    }
    if len(resolved_outputs) != len(outputs) or resolved_outputs & resolved_inputs:
        parser.error("Choose distinct paths for the source files, cue output, report, and draft.")

    try:
        _generate(args, report_path)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Lyric cue export failed. {exc}", file=sys.stderr)
        if report_path.is_file():
            print(f"Alignment report: {report_path}", file=sys.stderr)
        if args.output.is_file():
            print(f"The cue file at {args.output} may contain an earlier export.", file=sys.stderr)
        return 1
    print(f"Lyric cues: {args.output}\nAlignment report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
