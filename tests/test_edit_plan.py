from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from daily_video_factory.edit_plan import (
    EditPlan,
    EditPlanError,
    MeasuredTiming,
    VoiceAnchor,
    audit_edit_plan,
    compile_edit_plan,
    compile_project_edit_plan,
    resolve_anchor,
    validate_edit_plan_bundle,
)


def fixture_data() -> tuple[dict[str, Any], dict[str, Any]]:
    shots = []
    words = []
    for i in range(12):
        shots.append({
            "id": f"s{i + 1:02}", "start": {"boundary": "start"} if i == 0 else {"phrase": f"Beat{i + 1:02}"},
            "asset": f"assets/plate-{i % 4}.svg",
            "visual_kind": ["character", "environment", "interface", "object"][i % 4],
            "subject": ["Mira", "rain-window", "phone"][i % 3], "location": "bedroom" if i < 6 else "street",
            "layout": f"layout-{i % 6}", "framing": ["wide", "close", "extreme_close", "insert", "medium"][i % 5],
            "camera": ["push_in", "pan", "locked", "tilt"][i % 4],
            "action": "Mira pauses before the decision.", "expression": "hesitant",
            "cut_reason": "The measured phrase introduces a concrete new detail.",
        })
        for j, token in enumerate([f"Beat{i + 1:02}", "Mira", "waits."]):
            words.append({"text": token, "start": i * 3.0 + j * 0.5, "end": i * 3.0 + j * 0.5 + 0.4})
    audio = [{"id": role, "role": role, "asset": f"assets/{role}.wav",
              "start": {"boundary": "start"}, "end": {"boundary": "end"}}
             for role in ("voice", "music", "ambience")]
    audio[1].update({"gain_db": -18, "duck_db": -10, "fade_in_frames": 30, "fade_out_frames": 30})
    audio[2].update({"gain_db": -24, "duck_db": -6})
    return ({"schema_version": 1, "project_id": "example-film", "shots": shots, "audio": audio},
            {"duration_seconds": 36.0, "words": words})


def make_project(root: Path) -> Path:
    plan, timing = fixture_data()
    (root / "assets").mkdir()
    for name in [*(f"plate-{i}.svg" for i in range(4)), "voice.wav", "music.wav", "ambience.wav"]:
        (root / "assets" / name).write_text("fixture media, not an actual render", encoding="utf-8")
    (root / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    path = root / "EDIT_PLAN.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def test_diverse_edit_covers_the_exact_voice_clock_without_quality_overclaim() -> None:
    raw, timing = fixture_data()
    plan = EditPlan.model_validate(raw)
    result = compile_edit_plan(plan, timing)
    audit = audit_edit_plan(plan, result)
    assert result.duration_frames == 1080
    assert [(s["start_frame"], s["end_frame"]) for s in result.shots] == [(i * 90, (i + 1) * 90) for i in range(12)]
    assert audit.passed and audit.metrics["caption_word_count"] == 36
    assert audit.metrics["declared_variety"]["asset"] == 4
    assert not audit.visual_quality_automatically_verified
    assert not audit.semantic_accuracy_automatically_verified
    assert not audit.rendered_motion_measured
    assert not audit.audience_performance_predicted


def test_phrase_anchors_preserve_punctuation_case_and_explicit_occurrence() -> None:
    _, raw = fixture_data()
    timing = MeasuredTiming.model_validate(raw)
    assert resolve_anchor(VoiceAnchor(phrase="BEAT02, Mira waits!", edge="end"), timing, 30)["frame"] == 132
    with pytest.raises(EditPlanError, match="Ambiguous"):
        resolve_anchor(VoiceAnchor(phrase="Mira"), timing, 30)
    assert resolve_anchor(VoiceAnchor(phrase="Mira", occurrence=2), timing, 30)["frame"] == 105


@pytest.mark.parametrize("anchor, message", [
    ({"phrase": "never spoken"}, "not found"),
    ({"phrase": "Mira", "occurrence": 13}, "exceeds"),
    ({"word_index": 36}, "exceeds"),
    ({"boundary": "start", "offset_frames": -1}, "outside"),
])
def test_bad_anchor_fails_instead_of_guessing(anchor: dict[str, Any], message: str) -> None:
    _, raw = fixture_data()
    with pytest.raises(EditPlanError, match=message):
        resolve_anchor(VoiceAnchor.model_validate(anchor), MeasuredTiming.model_validate(raw), 30)


@pytest.mark.parametrize("anchor", [{}, {"phrase": "Mira", "word_index": 1},
                                   {"boundary": "start", "occurrence": 1}])
def test_ambiguous_anchor_schema_rejected(anchor: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        VoiceAnchor.model_validate(anchor)


def test_frame_quantization_extends_tail_only_and_does_not_truncate_audio() -> None:
    raw, timing = fixture_data()
    timing["duration_seconds"] = 36.01
    timing["words"][0]["start"] = 1 / 60
    compiled = compile_edit_plan(EditPlan.model_validate(raw), timing)
    assert compiled.duration_frames == 1081
    assert compiled.audio[0]["end_frame"] == 1081
    assert compiled.captions[0]["start_frame"] == 1
    assert compiled.duration_seconds - timing["duration_seconds"] < 1 / 30


def test_transition_handles_do_not_shorten_primary_timeline_or_voice() -> None:
    raw, timing = fixture_data()
    raw["shots"][1]["transition"] = {"kind": "dissolve", "frames": 12}
    result = compile_edit_plan(EditPlan.model_validate(raw), timing)
    assert result.duration_frames == 1080
    assert result.shots[0]["end_frame"] == result.shots[1]["start_frame"] == 90
    assert result.shots[0]["display_end_frame"] == 96
    assert result.shots[1]["display_start_frame"] == 84
    assert result.transitions[0]["start_frame"] == 84
    assert result.transitions[0]["end_frame"] == 96
    assert result.audio[0]["duration_frames"] == 1080


@pytest.mark.parametrize("mutation, message", [
    ("same_start", "strictly increasing"), ("no_opening", "frame zero"),
    ("opening_transition", "opening shot"), ("long_transition", "adjacent shot"),
])
def test_invalid_shot_clock_is_rejected(mutation: str, message: str) -> None:
    raw, timing = fixture_data()
    if mutation == "same_start":
        raw["shots"][2]["start"] = raw["shots"][1]["start"]
    elif mutation == "no_opening":
        raw["shots"][0]["start"] = {"phrase": "Mira", "occurrence": 1}
    elif mutation == "opening_transition":
        raw["shots"][0]["transition"] = {"kind": "dissolve", "frames": 12}
    else:
        raw["shots"][1]["transition"] = {"kind": "dissolve", "frames": 100}
    with pytest.raises(EditPlanError, match=message):
        compile_edit_plan(EditPlan.model_validate(raw), timing)


@pytest.mark.parametrize("mutation", ["overlap", "reverse", "outside", "nan", "multiple_words"])
def test_untrustworthy_alignment_is_rejected(mutation: str) -> None:
    _, timing = fixture_data()
    if mutation == "overlap":
        timing["words"][1]["start"] = 0.2
    elif mutation == "reverse":
        timing["words"] = list(reversed(timing["words"]))
    elif mutation == "outside":
        timing["words"][-1]["end"] = 40.0
    elif mutation == "nan":
        timing["words"][1]["end"] = float("nan")
    else:
        timing["words"][1]["text"] = "Mira and"
    with pytest.raises(ValidationError):
        MeasuredTiming.model_validate(timing)


def test_captions_preserve_every_spoken_word_and_boundaries() -> None:
    raw, timing = fixture_data()
    raw["captions"] = {"max_words": 2, "max_characters": 20}
    compiled = compile_edit_plan(EditPlan.model_validate(raw), timing)
    words = [word["text"] for c in compiled.captions for word in c["words"]]
    assert words == [word["text"] for word in timing["words"]]
    assert all(len(c["words"]) <= 2 and len(c["text"]) <= 20 for c in compiled.captions)
    assert all(a["end_frame"] <= b["start_frame"] for a, b in zip(compiled.captions, compiled.captions[1:], strict=False))
    assert all(c["start_frame"] <= w["start_frame"] < w["end_frame"] <= c["end_frame"]
               for c in compiled.captions for w in c["words"])


def test_unrenderable_caption_word_is_not_silently_truncated() -> None:
    raw, timing = fixture_data()
    timing["words"][1]["text"] = "x" * 65
    with pytest.raises(EditPlanError, match="do not truncate"):
        compile_edit_plan(EditPlan.model_validate(raw), timing)


def test_audio_cues_use_frame_offsets_and_voice_ducking() -> None:
    raw, timing = fixture_data()
    raw["audio"].append({"id": "tap", "role": "foley", "asset": "assets/tap.wav",
                         "start": {"phrase": "Beat02"}, "duration_frames": 15,
                         "source_start_frame": 6, "gain_db": -6})
    compiled = compile_edit_plan(EditPlan.model_validate(raw), timing)
    tap = compiled.audio[-1]
    assert (tap["start_frame"], tap["end_frame"], tap["source_start_frame"]) == (90, 105, 6)
    assert compiled.audio[0]["gain_envelope"] == [{"frame": 0, "gain_db": 0.0}, {"frame": 1080, "gain_db": 0.0}]
    music = {point["frame"]: point["gain_db"] for point in compiled.audio[1]["gain_envelope"]}
    assert music[30] == -28
    assert music[51] == -18
    assert music[0] == -96


def test_authored_gain_composes_with_fades_and_ducking_in_the_actual_mixer() -> None:
    import numpy as np

    from daily_video_factory.cinematic_audio import gain_samples

    raw, timing = fixture_data()
    raw["audio"][1]["gain_keyframes"] = [
        {"at": {"boundary": "start"}, "offset_db": 0},
        {"at": {"word_index": 2}, "offset_db": -6},  # frame 30
        {"at": {"boundary": "end"}, "offset_db": -6},
    ]
    compiled = compile_edit_plan(EditPlan.model_validate(raw), timing)
    music = compiled.audio[1]
    assert [(p["frame"], p["offset_db"]) for p in music["gain_keyframes"]] == [(0, 0), (30, -6), (1080, -6)]
    assert music["gain_keyframes"][1]["voice_anchor"]["word_indices"] == [2]
    frames = np.array([0., 5., 15., 30., 42., 46.5, 51., 1080.])
    # Base -18; ramp offset 0 -> -6; opening fade -90 -> 0; speech duck -10.
    # The silence floor has an exact crossing, not an incorrectly softened ramp.
    actual_db = 20 * np.log10(gain_samples(music["gain_envelope"], frames))
    assert actual_db == pytest.approx([-96, -96, -76, -34, -34, -29, -24, -96])


def test_partial_gain_points_hold_their_end_values_and_empty_points_preserve_old_output() -> None:
    raw, timing = fixture_data()
    original = compile_edit_plan(EditPlan.model_validate(raw), timing)
    raw["audio"][1]["gain_keyframes"] = []
    assert compile_edit_plan(EditPlan.model_validate(raw), timing) == original
    raw["audio"][1].update({"fade_in_frames": 0, "fade_out_frames": 0, "duck_db": None,
                            "gain_keyframes": [{"at": {"phrase": "Beat02"}, "offset_db": -6}]})
    compiled = compile_edit_plan(EditPlan.model_validate(raw), timing)
    assert all(point["gain_db"] == -24 for point in compiled.audio[1]["gain_envelope"])
    assert compiled.audio[0] == original.audio[0]
    assert compiled.audio[2] == original.audio[2]


@pytest.mark.parametrize("anchors", [
    [{"phrase": "Beat03"}, {"phrase": "Beat02"}],
    [{"phrase": "Beat02"}, {"word_index": 3}],
])
def test_gain_points_reject_reversed_or_colliding_resolved_frames(anchors: list[dict[str, Any]]) -> None:
    raw, timing = fixture_data()
    raw["audio"][1]["gain_keyframes"] = [{"at": anchor, "offset_db": -6} for anchor in anchors]
    with pytest.raises(EditPlanError, match="strictly increasing after frame quantization"):
        compile_edit_plan(EditPlan.model_validate(raw), timing)


def test_gain_points_accept_exact_cue_boundaries_but_not_adjacent_frames() -> None:
    raw, timing = fixture_data()
    cue = raw["audio"][2]
    cue.update({"start": {"phrase": "Beat02"}, "end": {"phrase": "Beat03"},
                "gain_keyframes": [{"at": {"phrase": "Beat02"}, "offset_db": 0},
                                   {"at": {"phrase": "Beat03"}, "offset_db": -6}]})
    assert [p["frame"] for p in compile_edit_plan(EditPlan.model_validate(raw), timing).audio[2]["gain_keyframes"]] == [90, 180]
    for point, offset in ((0, -1), (1, 1)):
        cue["gain_keyframes"][point]["at"]["offset_frames"] = offset
        with pytest.raises(EditPlanError, match="outside its cue"):
            compile_edit_plan(EditPlan.model_validate(raw), timing)
        cue["gain_keyframes"][point]["at"].pop("offset_frames")


@pytest.mark.parametrize("offset", [-61, 13, float("nan"), float("inf")])
def test_gain_offsets_are_finite_and_bounded(offset: float) -> None:
    raw, _ = fixture_data()
    raw["audio"][1]["gain_keyframes"] = [{"at": {"boundary": "start"}, "offset_db": offset}]
    with pytest.raises(ValidationError):
        EditPlan.model_validate(raw)


def test_gain_keyframe_change_invalidates_compiled_bundle(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    raw = json.loads(path.read_text())
    raw["audio"][1]["gain_keyframes"] = [{"at": {"boundary": "start"}, "offset_db": -6}]
    path.write_text(json.dumps(raw), encoding="utf-8")
    compiled, _ = compile_project_edit_plan(path)
    assert validate_edit_plan_bundle(path).passed
    original_fingerprint = compiled.provenance["plan_sha256"]
    raw["audio"][1]["gain_keyframes"][0]["offset_db"] = -5
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(EditPlanError, match="Stale"):
        validate_edit_plan_bundle(path)
    updated, _ = compile_project_edit_plan(path)
    assert updated.provenance["plan_sha256"] != original_fingerprint
    assert updated.audio[1]["gain_envelope"] != compiled.audio[1]["gain_envelope"]


@pytest.mark.parametrize("mutation, message", [("short_voice", "complete approved"),
                                               ("long_cue", "outside"), ("fades", "fades overlap")])
def test_audio_cannot_trim_narration_or_escape_film(mutation: str, message: str) -> None:
    raw, timing = fixture_data()
    if mutation == "short_voice":
        raw["audio"][0]["end"] = {"phrase": "Beat12"}
    elif mutation == "long_cue":
        raw["audio"][1].pop("end")
        raw["audio"][1]["duration_frames"] = 1200
    else:
        raw["audio"][1].update({"fade_in_frames": 600, "fade_out_frames": 600})
    with pytest.raises(EditPlanError, match=message):
        compile_edit_plan(EditPlan.model_validate(raw), timing)


@pytest.mark.parametrize("change", [{"fade_in_frames": 1}, {"source_start_frame": 1}, {"duck_db": -6},
                                   {"gain_keyframes": [{"at": {"boundary": "start"}, "offset_db": 0}]}])
def test_voice_layer_cannot_fade_trim_or_duck(change: dict[str, Any]) -> None:
    raw, _ = fixture_data()
    raw["audio"][0].update(change)
    with pytest.raises(ValidationError, match="approved narration"):
        EditPlan.model_validate(raw)


def test_old_static_template_is_rejected_despite_twelve_nominal_shots() -> None:
    raw, timing = fixture_data()
    for shot in raw["shots"]:
        shot.update({"asset": "assets/plate-0.svg", "visual_kind": "typography", "layout": "paper",
                     "subject": "card", "framing": "wide", "camera": "locked"})
    plan = EditPlan.model_validate(raw)
    audit = audit_edit_plan(plan, compile_edit_plan(plan, timing))
    codes = {finding.code for finding in audit.findings}
    assert not audit.passed
    assert {"insufficient_visual_assets", "insufficient_layout", "insufficient_camera_moves",
            "dominant_layout", "repeated_layout_run", "typography_dominance"} <= codes


def test_cut_offset_cannot_pass_as_a_nearby_voice_motive() -> None:
    raw, timing = fixture_data()
    raw["shots"][1]["start"]["offset_frames"] = 30
    plan = EditPlan.model_validate(raw)
    assert "unanchored_cut" in {f.code for f in audit_edit_plan(plan, compile_edit_plan(plan, timing)).findings}


def test_timeline_gap_or_falsified_duration_fails_audit() -> None:
    raw, timing = fixture_data()
    plan = EditPlan.model_validate(raw)
    compiled = compile_edit_plan(plan, timing)
    compiled.shots[1]["start_frame"] += 1
    compiled.shots[2]["duration_frames"] = 1
    assert "shot_coverage" in {f.code for f in audit_edit_plan(plan, compiled).findings}


def test_missing_audio_layers_are_a_gate_not_a_success_metric() -> None:
    raw, timing = fixture_data()
    raw["audio"] = raw["audio"][:1]
    plan = EditPlan.model_validate(raw)
    assert "audio_layers" in {f.code for f in audit_edit_plan(plan, compile_edit_plan(plan, timing)).findings}


def test_project_bundle_is_reproducible_and_current(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    compiled, audit = compile_project_edit_plan(path)
    saved = (tmp_path / "EDIT_PLAN.compiled.json").read_bytes()
    assert audit.passed and validate_edit_plan_bundle(path).passed
    assert len(compiled.provenance["asset_sha256"]) == 7
    compile_project_edit_plan(path)
    assert saved == (tmp_path / "EDIT_PLAN.compiled.json").read_bytes()


@pytest.mark.parametrize("name", ["assets/plate-0.svg", "assets/voice.wav", "timing.json", "EDIT_PLAN.json"])
def test_source_change_requires_recompile(tmp_path: Path, name: str) -> None:
    path = make_project(tmp_path)
    compile_project_edit_plan(path)
    target = tmp_path / name
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(EditPlanError, match="Stale"):
        validate_edit_plan_bundle(path)


@pytest.mark.parametrize("name", ["EDIT_PLAN.compiled.json", "EDIT_PLAN.compiled.js", "EDIT_PLAN.audit.json"])
def test_payload_tampering_fails_verification(tmp_path: Path, name: str) -> None:
    path = make_project(tmp_path)
    compile_project_edit_plan(path)
    (tmp_path / name).write_text("tampered", encoding="utf-8")
    with pytest.raises(EditPlanError, match="modified"):
        validate_edit_plan_bundle(path)


def test_failed_quality_writes_reviewable_audit_but_no_new_runnable_payload(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    raw = json.loads(path.read_text())
    raw["shots"] = raw["shots"][:2]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(EditPlanError, match="quality contract failed"):
        compile_project_edit_plan(path)
    assert not json.loads((tmp_path / "EDIT_PLAN.audit.json").read_text())["passed"]
    assert not (tmp_path / "EDIT_PLAN.compiled.js").exists()


def test_failed_recompile_invalidates_existing_bundle(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    compile_project_edit_plan(path)
    raw = json.loads(path.read_text())
    raw["shots"] = raw["shots"][:2]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(EditPlanError):
        compile_project_edit_plan(path)
    with pytest.raises(EditPlanError, match="quality contract"):
        validate_edit_plan_bundle(path)


@pytest.mark.parametrize("asset", ["../secret", "C:/secret", "/secret", "assets\\secret", "https://example.org/a"])
def test_assets_must_be_project_local(asset: str) -> None:
    raw, _ = fixture_data()
    raw["shots"][0]["asset"] = asset
    with pytest.raises(ValidationError, match="project-relative"):
        EditPlan.model_validate(raw)


def test_missing_asset_fails_before_payload_write(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    (tmp_path / "assets/voice.wav").unlink()
    with pytest.raises(EditPlanError, match="Missing"):
        compile_project_edit_plan(path)
    assert not (tmp_path / "EDIT_PLAN.compiled.js").exists()


def test_symlink_cannot_escape_project(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    target = tmp_path / "assets/plate-0.svg"
    target.unlink()
    outside = tmp_path.parent / f"{tmp_path.name}-outside.svg"
    outside.write_text("external media", encoding="utf-8")
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    with pytest.raises(EditPlanError, match="escaping"):
        compile_project_edit_plan(path)


def test_generated_javascript_cannot_close_an_embedding_script(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    raw = json.loads(path.read_text())
    raw["shots"][0]["action"] = "Mira sees </script><script>alert(1)</script>."
    path.write_text(json.dumps(raw), encoding="utf-8")
    compile_project_edit_plan(path)
    assert "</script>" not in (tmp_path / "EDIT_PLAN.compiled.js").read_text(encoding="utf-8")


def test_cli_compile_and_check_reject_changed_source(tmp_path: Path) -> None:
    path = make_project(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts/compile_edit_plan.py"
    command = [sys.executable, str(script), str(path)]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["passed"]
    assert subprocess.run([*command, "--check"], capture_output=True, check=False).returncode == 0
    (tmp_path / "assets/voice.wav").write_text("changed voice", encoding="utf-8")
    changed = subprocess.run([*command, "--check"], capture_output=True, text=True, check=False)
    assert changed.returncode == 1 and "Stale" in changed.stderr
