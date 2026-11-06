"""Voice-anchored editorial timelines, compiled without a rendering dependency.

Frame ranges are half-open. Primary shots partition the complete film; transition
handles overlap only their display ranges and never shorten the spoken narrative.
Declared variety is an authoring check, not a measurement of rendered visual quality.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EditPlanError(ValueError):
    """An edit cannot be compiled or its authored quality contract does not pass."""


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def _relative(value: str) -> str:
    if (
        not value or "\\" in value or ":" in value or "\x00" in value
        or PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
        or ".." in PurePosixPath(value).parts
    ):
        raise ValueError("Use a project-relative POSIX path without parent traversal")
    return value


class VoiceAnchor(Contract):
    boundary: Literal["start", "end"] | None = None
    phrase: str | None = Field(default=None, min_length=1, max_length=240)
    word_index: int | None = Field(default=None, ge=0)
    occurrence: int | None = Field(default=None, ge=1)
    edge: Literal["start", "end"] = "start"
    offset_frames: int = Field(default=0, ge=-120, le=120)

    @model_validator(mode="after")
    def one_locator(self) -> VoiceAnchor:
        if sum(v is not None for v in (self.boundary, self.phrase, self.word_index)) != 1:
            raise ValueError("An anchor needs exactly one boundary, phrase or word_index")
        if self.occurrence is not None and self.phrase is None:
            raise ValueError("occurrence only applies to a phrase")
        if self.boundary is not None and self.edge != "start":
            raise ValueError("A boundary already determines its edge")
        return self


class Transition(Contract):
    kind: Literal["cut", "match_cut", "dissolve", "whip", "wipe"] = "cut"
    frames: int = Field(default=0, ge=0, le=120)

    @model_validator(mode="after")
    def duration_matches_kind(self) -> Transition:
        if (self.kind in {"cut", "match_cut"}) != (self.frames == 0):
            raise ValueError("Hard cuts need zero frames; animated transitions need positive frames")
        return self


class EditShot(Contract):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    start: VoiceAnchor
    asset: str
    visual_kind: Literal[
        "character", "environment", "object", "interface", "diagram", "typography", "footage"
    ]
    subject: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=100)
    layout: str = Field(min_length=1, max_length=100)
    framing: Literal["extreme_close", "close", "medium", "wide", "insert"]
    camera: Literal["locked", "push_in", "pull_out", "pan", "tilt", "tracking", "orbit", "handheld"]
    subject_motion: Literal["still", "performance", "action"] = "still"
    action: str = Field(min_length=8, max_length=1000)
    expression: str = Field(default="", max_length=240)
    cut_reason: str = Field(min_length=8, max_length=600)
    transition: Transition = Field(default_factory=Transition)

    _asset_path = field_validator("asset")(_relative)

    @field_validator("subject", "location", "layout", "action", "cut_reason")
    @classmethod
    def substantive_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Editorial descriptions must contain text")
        return value.strip()


class AudioGainKeyframe(Contract):
    at: VoiceAnchor
    offset_db: float = Field(ge=-60, le=12, description="Additive offset from the cue's base gain, in decibels")


class AudioCue(Contract):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    role: Literal["voice", "music", "ambience", "foley", "accent"]
    asset: str
    start: VoiceAnchor
    end: VoiceAnchor | None = None
    duration_frames: int | None = Field(default=None, ge=1)
    source_start_frame: int = Field(default=0, ge=0)
    gain_db: float = Field(default=0, ge=-60, le=12)
    gain_keyframes: list[AudioGainKeyframe] = Field(default_factory=list, max_length=200)
    fade_in_frames: int = Field(default=0, ge=0, le=600)
    fade_out_frames: int = Field(default=0, ge=0, le=600)
    duck_db: float | None = Field(default=None, ge=-30, le=0)
    duck_attack_frames: int = Field(default=3, ge=1, le=60)
    duck_release_frames: int = Field(default=9, ge=1, le=120)

    _asset_path = field_validator("asset")(_relative)

    @model_validator(mode="after")
    def one_end(self) -> AudioCue:
        if (self.end is None) == (self.duration_frames is None):
            raise ValueError("Audio needs exactly one end anchor or duration_frames")
        if self.role == "voice" and (
            self.source_start_frame or self.fade_in_frames or self.fade_out_frames
            or self.duck_db is not None or self.gain_keyframes
        ):
            raise ValueError("Do not trim, fade, duck or automate gain on the approved narration in the edit plan")
        return self


class CaptionPolicy(Contract):
    max_words: int = Field(default=4, ge=1, le=8)
    max_characters: int = Field(default=32, ge=8, le=64)
    max_gap_seconds: float = Field(default=0.35, ge=0, le=2)
    hold_frames: int = Field(default=3, ge=0, le=15)


class EditQualityPolicy(Contract):
    min_shots: int = Field(default=12, ge=2, le=100)
    min_visual_kinds: int = Field(default=3, ge=1, le=7)
    min_visual_assets: int = Field(default=4, ge=1, le=100)
    min_layouts: int = Field(default=5, ge=2, le=100)
    min_subjects: int = Field(default=3, ge=1, le=100)
    min_framings: int = Field(default=4, ge=1, le=5)
    min_camera_moves: int = Field(default=3, ge=1, le=7)
    min_shot_seconds: float = Field(default=0.45, ge=0.1, le=5)
    max_shot_seconds: float = Field(default=5.5, ge=1, le=30)
    max_same_layout_seconds: float = Field(default=7, ge=1, le=60)
    max_static_seconds: float = Field(default=4.5, ge=1, le=30)
    max_dominant_layout_fraction: float = Field(default=0.4, gt=0, le=1)
    max_typography_fraction: float = Field(default=0.18, ge=0, le=1)
    max_cut_anchor_offset_frames: int = Field(default=15, ge=0, le=120)
    require_layered_audio: bool = True

    @model_validator(mode="after")
    def sensible_lengths(self) -> EditQualityPolicy:
        if self.min_shot_seconds >= self.max_shot_seconds:
            raise ValueError("Minimum shot duration must be shorter than maximum")
        return self


class EditPlan(Contract):
    schema_version: Literal[1] = 1
    project_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$")
    fps: int = Field(default=30, ge=24, le=60)
    width: int = Field(default=1080, ge=320, le=7680)
    height: int = Field(default=1920, ge=320, le=7680)
    timing_file: str = "timing.json"
    shots: list[EditShot] = Field(min_length=2, max_length=200)
    audio: list[AudioCue] = Field(min_length=1, max_length=500)
    captions: CaptionPolicy = Field(default_factory=CaptionPolicy)
    policy: EditQualityPolicy = Field(default_factory=EditQualityPolicy)

    _timing_path = field_validator("timing_file")(_relative)

    @model_validator(mode="after")
    def identities(self) -> EditPlan:
        ids = [s.id for s in self.shots] + [a.id for a in self.audio]
        if len(ids) != len(set(ids)):
            raise ValueError("Shot and audio IDs must be unique")
        if sum(a.role == "voice" for a in self.audio) != 1:
            raise ValueError("Use exactly one complete approved narration layer")
        return self


class TimingWord(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)
    text: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class MeasuredTiming(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)
    duration_seconds: float = Field(gt=0, le=3600)
    words: list[TimingWord] = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def ordered_words(self) -> MeasuredTiming:
        previous_end = 0.0
        for word in self.words:
            if len(word.text.split()) != 1 or not _token(word.text):
                raise ValueError("Each timing word needs one nonempty spoken token")
            if word.start < previous_end - 1e-7 or word.end <= word.start:
                raise ValueError("Measured words must be ordered, nonoverlapping, positive ranges")
            if word.end > self.duration_seconds + 1e-7:
                raise ValueError("A word extends past the measured audio duration")
            previous_end = word.end
        return self


class CompiledEditPlan(Contract):
    schema_version: Literal[1] = 1
    project_id: str
    fps: int
    width: int
    height: int
    duration_frames: int
    duration_seconds: float
    shots: list[dict[str, Any]]
    transitions: list[dict[str, Any]]
    captions: list[dict[str, Any]]
    audio: list[dict[str, Any]]
    provenance: dict[str, Any] = Field(default_factory=dict)


class EditFinding(Contract):
    code: str
    severity: Literal["error", "warning"]
    message: str
    shot_ids: list[str] = Field(default_factory=list)


class EditAudit(Contract):
    schema_version: Literal[1] = 1
    passed: bool
    metrics: dict[str, Any]
    findings: list[EditFinding]
    visual_quality_automatically_verified: Literal[False] = False
    semantic_accuracy_automatically_verified: Literal[False] = False
    rendered_motion_measured: Literal[False] = False
    audience_performance_predicted: Literal[False] = False


def _token(text: str) -> str:
    return re.sub(r"[^\w]", "", text.casefold(), flags=re.UNICODE)


def _frame(seconds: float, fps: int, *, ceil: bool = False) -> int:
    # Decimal input avoids binary rounding drift; sub-nanoframe differences are
    # timestamp serialization noise (for example float(1 / 60) at 30 fps).
    frames = (Decimal(str(seconds)) * fps).quantize(Decimal("0.000000001"))
    return int(frames.to_integral_value(
        rounding=ROUND_CEILING if ceil else ROUND_HALF_UP
    ))


def resolve_anchor(anchor: VoiceAnchor, timing: MeasuredTiming, fps: int) -> dict[str, Any]:
    """Resolve a literal phrase; repeated phrases require a one-based occurrence."""
    indices: list[int] = []
    if anchor.boundary:
        seconds = 0.0 if anchor.boundary == "start" else timing.duration_seconds
        frame = 0 if anchor.boundary == "start" else _frame(seconds, fps, ceil=True)
    else:
        if anchor.word_index is not None:
            if anchor.word_index >= len(timing.words):
                raise EditPlanError("Anchor word_index exceeds the measured transcript")
            indices = [anchor.word_index]
        else:
            phrase = [_token(w) for w in (anchor.phrase or "").split()]
            if not phrase or not all(phrase):
                raise EditPlanError("Anchor phrase contains no spoken words")
            words = [_token(w.text) for w in timing.words]
            matches = [i for i in range(len(words) - len(phrase) + 1)
                       if words[i:i + len(phrase)] == phrase]
            if not matches:
                raise EditPlanError(f"Voice anchor was not found: {anchor.phrase!r}")
            if len(matches) > 1 and anchor.occurrence is None:
                raise EditPlanError(f"Ambiguous voice anchor requires occurrence: {anchor.phrase!r}")
            occurrence = anchor.occurrence or 1
            if occurrence > len(matches):
                raise EditPlanError("Anchor occurrence exceeds phrase matches")
            first = matches[occurrence - 1]
            indices = list(range(first, first + len(phrase)))
        word = timing.words[indices[0] if anchor.edge == "start" else indices[-1]]
        seconds = word.start if anchor.edge == "start" else word.end
        frame = _frame(seconds, fps)
    resolved = frame + anchor.offset_frames
    if not 0 <= resolved <= _frame(timing.duration_seconds, fps, ceil=True):
        raise EditPlanError("Anchor offset falls outside the measured film")
    return {"frame": resolved, "measured_seconds": seconds, "word_indices": indices,
            "locator": anchor.model_dump(exclude_none=True)}


def _captions(timing: MeasuredTiming, plan: EditPlan, duration: int) -> list[dict[str, Any]]:
    policy = plan.captions
    groups: list[list[tuple[int, TimingWord]]] = []
    group: list[tuple[int, TimingWord]] = []
    for index, word in enumerate(timing.words):
        if len(word.text) > policy.max_characters:
            raise EditPlanError("A spoken word exceeds the caption character limit; do not truncate it")
        proposed = " ".join([w.text for _, w in group] + [word.text])
        if group and (len(group) >= policy.max_words or len(proposed) > policy.max_characters
                      or word.start - group[-1][1].end > policy.max_gap_seconds):
            groups.append(group)
            group = []
        group.append((index, word))
        if re.search(r"[.!?][\"'”’]?$", word.text):
            groups.append(group)
            group = []
    if group:
        groups.append(group)
    result = []
    for index, group in enumerate(groups):
        start = _frame(group[0][1].start, plan.fps)
        following = _frame(groups[index + 1][0][1].start, plan.fps) if index + 1 < len(groups) else duration
        end = min(following, duration, _frame(group[-1][1].end, plan.fps, ceil=True) + policy.hold_frames)
        if end <= start:
            raise EditPlanError("Caption groups collapse onto one frame; revise measured timing")
        result.append({"id": f"caption-{index + 1:03}", "start_frame": start, "end_frame": end,
                       "text": " ".join(w.text for _, w in group),
                       "words": [{"index": i, "text": w.text,
                                  "start_frame": _frame(w.start, plan.fps),
                                  "end_frame": min(end, max(_frame(w.start, plan.fps) + 1,
                                                            _frame(w.end, plan.fps, ceil=True)))}
                                 for i, w in group]})
    return result


def _speech_ranges(timing: MeasuredTiming, fps: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for word in timing.words:
        start, end = _frame(word.start, fps), _frame(word.end, fps, ceil=True)
        if ranges and start - ranges[-1][1] <= math.ceil(fps * 0.18):
            ranges[-1] = (ranges[-1][0], max(end, ranges[-1][1]))
        else:
            ranges.append((start, end))
    return ranges


def _gain_offset(frame: int, keyframes: list[dict[str, Any]]) -> float:
    if not keyframes:
        return 0.0
    if frame <= keyframes[0]["frame"]:
        return float(keyframes[0]["offset_db"])
    for left, right in zip(keyframes, keyframes[1:], strict=False):
        if frame <= right["frame"]:
            progress = (frame - left["frame"]) / (right["frame"] - left["frame"])
            return float(left["offset_db"] + progress * (right["offset_db"] - left["offset_db"]))
    return float(keyframes[-1]["offset_db"])


def _gain_envelope(cue: AudioCue, start: int, end: int,
                   speech: list[tuple[int, int]],
                   keyframes: list[dict[str, Any]]) -> list[dict[str, float | int]]:
    # Keep the bed down across short pauses instead of overlapping release/attack
    # ramps. This makes every emitted breakpoint exact under linear dB interpolation.
    merged: list[tuple[int, int]] = []
    for a, b in speech:
        if merged and a - merged[-1][1] <= cue.duck_attack_frames + cue.duck_release_frames:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    speech = merged
    points = {start, end, start + cue.fade_in_frames, end - cue.fade_out_frames}
    points.update(point["frame"] for point in keyframes)
    if cue.duck_db is not None:
        for a, b in speech:
            points.update(max(start, min(end, p)) for p in
                          (a - cue.duck_attack_frames, a, b, b + cue.duck_release_frames))
    result: list[dict[str, float | int]] = []
    for frame in sorted(points):
        fade = 0.0
        if cue.fade_in_frames and frame < start + cue.fade_in_frames:
            fade = -90 * (1 - (frame - start) / cue.fade_in_frames)
        if cue.fade_out_frames and frame > end - cue.fade_out_frames:
            fade = min(fade, -90 * (1 - (end - frame) / cue.fade_out_frames))
        duck = 0.0
        if cue.duck_db is not None:
            for a, b in speech:
                if a <= frame <= b:
                    strength = 1.0
                elif a - cue.duck_attack_frames < frame < a:
                    strength = (frame - a + cue.duck_attack_frames) / cue.duck_attack_frames
                elif b < frame < b + cue.duck_release_frames:
                    strength = 1 - (frame - b) / cue.duck_release_frames
                else:
                    strength = 0.0
                duck = min(duck, cue.duck_db * strength)
        result.append({"frame": frame,
                       "gain_db": cue.gain_db + fade + duck + _gain_offset(frame, keyframes)})
    # A gain ride can cross the silence floor between authored/fade/duck points.
    # Preserve that intersection rather than bending the whole ramp by clipping
    # its endpoints. Fractional-frame breakpoints are valid for sample-level mixing.
    # Unautomated cues retain their existing envelope byte-for-byte.
    clipped: list[dict[str, float | int]] = []
    for index, point in enumerate(result):
        if keyframes and index:
            previous = result[index - 1]
            a, b = previous["gain_db"], point["gain_db"]
            if min(a, b) < -96 < max(a, b):
                crossing = previous["frame"] + (-96 - a) * (point["frame"] - previous["frame"]) / (b - a)
                clipped.append({"frame": crossing, "gain_db": -96.0})
        clipped.append({"frame": point["frame"], "gain_db": round(max(-96, point["gain_db"]), 6)})
    return clipped


def compile_edit_plan(plan: EditPlan, measured: dict[str, Any]) -> CompiledEditPlan:
    timing = MeasuredTiming.model_validate(measured)
    duration = _frame(timing.duration_seconds, plan.fps, ceil=True)
    anchors = [resolve_anchor(shot.start, timing, plan.fps) for shot in plan.shots]
    starts = [anchor["frame"] for anchor in anchors]
    if starts[0] != 0 or starts[-1] >= duration:
        raise EditPlanError("Primary shots must start at frame zero and finish within the film")
    if any(b <= a for a, b in zip(starts, starts[1:], strict=False)):
        raise EditPlanError("Shot starts must be strictly increasing after frame quantization")
    if plan.shots[0].transition.frames:
        raise EditPlanError("The opening shot cannot transition from nonexistent previous media")
    shots: list[dict[str, Any]] = []
    for i, shot in enumerate(plan.shots):
        end = starts[i + 1] if i + 1 < len(starts) else duration
        shots.append({**shot.model_dump(exclude={"start", "transition"}),
                      "start_frame": starts[i], "end_frame": end,
                      "duration_frames": end - starts[i], "display_start_frame": starts[i],
                      "display_end_frame": end, "voice_anchor": anchors[i]})
    transitions = []
    for i, shot in enumerate(plan.shots[1:], start=1):
        transition = shot.transition
        if transition.frames > min(shots[i - 1]["duration_frames"], shots[i]["duration_frames"]):
            raise EditPlanError("Transition handles cannot consume an adjacent shot")
        before = transition.frames // 2
        after = transition.frames - before
        shots[i]["display_start_frame"] -= before
        shots[i - 1]["display_end_frame"] += after
        transitions.append({"from_shot": shots[i - 1]["id"], "to_shot": shot.id,
                            "kind": transition.kind, "cut_frame": starts[i],
                            "start_frame": starts[i] - before,
                            "end_frame": starts[i] + after,
                            "frames": transition.frames})
    audio = []
    speech = _speech_ranges(timing, plan.fps)
    for cue in plan.audio:
        start = resolve_anchor(cue.start, timing, plan.fps)["frame"]
        end = resolve_anchor(cue.end, timing, plan.fps)["frame"] if cue.end else start + int(cue.duration_frames or 0)
        if not 0 <= start < end <= duration:
            raise EditPlanError(f"Audio cue {cue.id!r} falls outside the film")
        if cue.fade_in_frames + cue.fade_out_frames > end - start:
            raise EditPlanError("Audio fades overlap; reduce their durations")
        if cue.role == "voice" and (start != 0 or end != duration):
            raise EditPlanError("The complete approved narration must span the film unchanged")
        keyframes = []
        for point in cue.gain_keyframes:
            anchor = resolve_anchor(point.at, timing, plan.fps)
            frame = anchor["frame"]
            if not start <= frame <= end:
                raise EditPlanError(f"Gain keyframe for audio cue {cue.id!r} falls outside its cue")
            if keyframes and frame <= keyframes[-1]["frame"]:
                raise EditPlanError("Gain keyframes must be strictly increasing after frame quantization")
            keyframes.append({"frame": frame, "offset_db": point.offset_db, "voice_anchor": anchor})
        audio.append({**cue.model_dump(exclude={"start", "end", "duration_frames", "gain_keyframes"}),
                      "start_frame": start, "end_frame": end, "duration_frames": end - start,
                      **({"gain_keyframes": keyframes} if keyframes else {}),
                      "gain_envelope": _gain_envelope(cue, start, end, speech, keyframes)})
    return CompiledEditPlan(project_id=plan.project_id, fps=plan.fps, width=plan.width,
                            height=plan.height, duration_frames=duration,
                            duration_seconds=duration / plan.fps, shots=shots,
                            transitions=transitions, captions=_captions(timing, plan, duration),
                            audio=audio)


def audit_edit_plan(plan: EditPlan, compiled: CompiledEditPlan) -> EditAudit:
    """Check authored diversity and clock structure; never infer quality from labels."""
    policy = plan.policy
    findings: list[EditFinding] = []
    shots = compiled.shots

    def error(code: str, message: str, ids: list[str] | None = None) -> None:
        findings.append(EditFinding(code=code, severity="error", message=message, shot_ids=ids or []))

    expected_start = 0
    for shot in shots:
        if (shot["start_frame"] != expected_start or shot["end_frame"] <= shot["start_frame"]
                or shot["duration_frames"] != shot["end_frame"] - shot["start_frame"]):
            error("shot_coverage", "Primary shots must partition the complete film", [shot["id"]])
        expected_start = shot["end_frame"]
    if expected_start != compiled.duration_frames:
        error("shot_coverage", "Primary coverage ends before or after the film")
    varieties = {key: len({s[key] for s in shots}) for key in
                 ("visual_kind", "asset", "layout", "subject", "location", "framing")}
    varieties["camera_moves"] = len({s["camera"] for s in shots if s["camera"] != "locked"})
    checks = {"shots": (len(shots), policy.min_shots),
              "visual_kind": (varieties["visual_kind"], policy.min_visual_kinds),
              "visual_assets": (varieties["asset"], policy.min_visual_assets),
              "layout": (varieties["layout"], policy.min_layouts),
              "subject": (varieties["subject"], policy.min_subjects),
              "framing": (varieties["framing"], policy.min_framings),
              "camera_moves": (varieties["camera_moves"], policy.min_camera_moves)}
    for name, (actual, required) in checks.items():
        if actual < required:
            error(f"insufficient_{name}", f"Declared {name}: {actual}; required at least {required}")
    layout_frames: Counter[str] = Counter()
    typography_frames = 0
    longest_layout_run = 0
    run_frames = 0
    previous_layout = None
    longest_static = 0
    for index, shot in enumerate(shots):
        frames = shot["duration_frames"]
        seconds = frames / plan.fps
        if seconds > policy.max_shot_seconds or seconds < policy.min_shot_seconds:
            error("shot_duration", f"Shot duration {seconds:.3f}s is outside the authored range", [shot["id"]])
        layout_frames[shot["layout"]] += frames
        run_frames = run_frames + frames if shot["layout"] == previous_layout else frames
        longest_layout_run = max(longest_layout_run, run_frames)
        previous_layout = shot["layout"]
        if shot["camera"] == "locked" and shot["subject_motion"] == "still":
            longest_static = max(longest_static, frames)
            if seconds > policy.max_static_seconds:
                error("static_shot", "Declared still subject and locked camera hold too long", [shot["id"]])
        if shot["visual_kind"] == "typography":
            typography_frames += frames
        if index and (not shot["voice_anchor"]["word_indices"] or
                      abs(plan.shots[index].start.offset_frames) > policy.max_cut_anchor_offset_frames):
            error("unanchored_cut", "Every later cut needs a nearby measured speech anchor", [shot["id"]])
    dominant = max(layout_frames.values(), default=0) / compiled.duration_frames
    if dominant > policy.max_dominant_layout_fraction:
        error("dominant_layout", "One declared layout occupies too much of the film")
    if longest_layout_run / plan.fps > policy.max_same_layout_seconds:
        error("repeated_layout_run", "Consecutive shots retain the same layout for too long")
    if typography_frames / compiled.duration_frames > policy.max_typography_fraction:
        error("typography_dominance", "Too much of this narrative is declared as typography")
    roles = {a["role"] for a in compiled.audio}
    if policy.require_layered_audio and ("music" not in roles or not roles.intersection({"ambience", "foley", "accent"})):
        error("audio_layers", "Declare music and at least one motivated ambience/foley/accent layer")
    for cue in compiled.audio:
        if cue["role"] in {"music", "ambience"} and cue["duck_db"] is None:
            findings.append(EditFinding(code="unducked_bed", severity="warning",
                                        message=f"Bed {cue['id']} has no voice ducking envelope"))
    return EditAudit(passed=not any(f.severity == "error" for f in findings), findings=findings,
                     metrics={"shot_count": len(shots), "declared_variety": varieties,
                              "coverage_frames": expected_start,
                              "longest_layout_run_seconds": longest_layout_run / plan.fps,
                              "longest_declared_static_seconds": longest_static / plan.fps,
                              "dominant_layout_fraction": dominant,
                              "typography_fraction": typography_frames / compiled.duration_frames,
                              "audio_roles": sorted(roles),
                              "caption_word_count": sum(len(c["words"]) for c in compiled.captions)})


def _local_file(root: Path, value: str) -> Path:
    _relative(value)
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise EditPlanError(f"Missing or escaping project file: {value}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(value: BaseModel) -> str:
    return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _javascript(compiled: CompiledEditPlan) -> str:
    payload = _json(compiled).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return "window.ATLASFORGE_EDIT_PLAN = " + payload.rstrip() + ";\n"


def _write_artifact(path: Path, text: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_edit_plan(path: Path) -> EditPlan:
    return EditPlan.model_validate_json(path.read_text(encoding="utf-8-sig"))


def _compile_project(plan_path: Path) -> tuple[CompiledEditPlan, EditAudit]:
    plan_path = plan_path.resolve()
    root = plan_path.parent
    plan = load_edit_plan(plan_path)
    timing_path = _local_file(root, plan.timing_file)
    timing = json.loads(timing_path.read_text(encoding="utf-8-sig"))
    compiled = compile_edit_plan(plan, timing)
    assets = sorted({shot.asset for shot in plan.shots} | {cue.asset for cue in plan.audio})
    compiled.provenance = {"plan_sha256": _sha256(plan_path),
                           "timing_sha256": _sha256(timing_path),
                           "asset_sha256": {asset: _sha256(_local_file(root, asset)) for asset in assets}}
    return compiled, audit_edit_plan(plan, compiled)


def compile_project_edit_plan(plan_path: Path, *, require_quality: bool = True) -> tuple[CompiledEditPlan, EditAudit]:
    """Write a local renderer payload and audit. Failing quality never emits new runnable data."""
    compiled, audit = _compile_project(plan_path)
    root = plan_path.resolve().parent
    audit_path = root / "EDIT_PLAN.audit.json"
    _write_artifact(audit_path, _json(audit))
    if require_quality and not audit.passed:
        raise EditPlanError("Edit quality contract failed: " + ", ".join(
            f.code for f in audit.findings if f.severity == "error"
        ))
    _write_artifact(root / "EDIT_PLAN.compiled.json", _json(compiled))
    _write_artifact(root / "EDIT_PLAN.compiled.js", _javascript(compiled))
    return compiled, audit


def validate_edit_plan_bundle(plan_path: Path) -> EditAudit:
    """Reject stale/tampered payloads before a new project's renderer uses them."""
    compiled, audit = _compile_project(plan_path)
    if not audit.passed:
        raise EditPlanError("Current edit plan does not pass its quality contract")
    root = plan_path.resolve().parent
    expected = {"EDIT_PLAN.compiled.json": _json(compiled),
                "EDIT_PLAN.compiled.js": _javascript(compiled), "EDIT_PLAN.audit.json": _json(audit)}
    for name, content in expected.items():
        path = root / name
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise EditPlanError(f"Stale or modified edit artifact: {name}; recompile the plan")
    return audit
