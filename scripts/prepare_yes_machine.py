"""Prepare the authored Yes Machine edit using measured spoken-word anchors.

This recipe is specific creative direction. The pipeline, renderer and validation
are reusable; generating a new story still requires an authored storyboard.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from daily_video_factory.edit_plan import EditPlan, MeasuredTiming  # noqa: E402


def prepare(project: Path) -> None:
    timing = MeasuredTiming.model_validate_json((project / "timing.json").read_text(encoding="utf-8"))
    if not 15 <= timing.duration_seconds <= 55:
        raise ValueError("This authored short needs 15–55 seconds of measured speech and ending")
    # phrase, mode, kind, subject, framing, camera, causal action
    rows = [
        (None, "button_macro", "object", "yes-button", "extreme_close", "push_in", "Pressure gathers on a tactile coral YES button."),
        ("Saying yes", "button_press", "object", "yes-button", "close", "tilt", "The button depresses and drives the first mechanical linkage."),
        ("before I'd", "chain", "environment", "domino-chain", "wide", "pull_out", "A spreading chain reveals what the small button has started."),
        ("One little yes", "chain_macro", "object", "trigger", "insert", "tracking", "A tiny trigger transfers its motion into a much larger mechanism."),
        ("Then the money", "money", "object", "cost-mechanism", "medium", "orbit", "Brass tokens feed the cost mechanism as consequences accumulate."),
        ("The time", "clock", "object", "clock", "close", "orbit", "The rotating mechanism matches into a clock advancing under tension."),
        ("The stuff", "unused", "environment", "unused-boxes", "wide", "pull_out", "Boxes accumulate on a conveyor while the camera reveals their scale."),
        ("So I tried", "brake", "object", "brake", "insert", "pan", "A brake enters the machine and begins to resist its movement."),
        ("I paused", "still", "environment", "stopped-machine", "wide", "locked", "The entire mechanism stops and leaves a deliberate moment of stillness."),
        ("What does it cost", "gate_cost", "diagram", "cost-gate", "medium", "tracking", "A physical gate opens with the first practical question about cost."),
        ("Will I use it", "gate_use", "diagram", "use-gate", "close", "pan", "The route bends through a second gate asking about actual use."),
        ("Does it fit my life", "gate_life", "diagram", "life-gate", "medium", "pull_out", "A third gate reconnects the choice to the viewer's life."),
        ("Turns out", "choice", "environment", "choice-paths", "wide", "pull_out", "The machine resolves into two legitimate paths: YES and NOT NOW."),
    ]
    shots, directions = [], {}
    headings = {
        "button_macro": "My most|expensive habit?",
        "button_press": "YES.",
        "gate_cost": "What does|it cost?", "gate_use": "Will I|use it?",
        "gate_life": "Does it fit|my life?", "choice": "A good choice|can wait for you.",
    }
    for n, (phrase, mode, kind, subject, framing, camera, action) in enumerate(rows, 1):
        shot_id = f"s{n:02d}"
        shots.append({
            "id": shot_id, "start": {"phrase": phrase} if phrase else {"boundary": "start"},
            "asset": "assets/world.json", "visual_kind": kind, "subject": subject,
            "location": "continuous-mechanical-world", "layout": mode, "framing": framing,
            "camera": camera, "subject_motion": "still" if mode == "still" else "action",
            "action": action, "expression": "Pressure becomes self-aware pause, then relief.",
            "cut_reason": action, "transition": {"kind": "match_cut" if mode == "clock" else "cut", "frames": 0},
        })
        directions[shot_id] = {"mode": mode}
        if mode in headings:
            directions[shot_id]["heading"] = headings[mode]
        if mode.startswith("gate_") or mode in {"choice", "button_macro"}:
            directions[shot_id]["hide_captions"] = True
    audio = [
        {"id": "voice", "role": "voice", "asset": "assets/audio/narration.wav", "gain_db": 0.0},
        {"id": "score", "role": "music", "asset": "assets/audio/score.wav", "gain_db": 0.0,
         "duck_db": -6.0, "duck_attack_frames": 2, "duck_release_frames": 6},
        {"id": "mechanism", "role": "foley", "asset": "assets/audio/machine.wav", "gain_db": -4.0,
         "duck_db": -3.0, "duck_attack_frames": 1, "duck_release_frames": 3},
    ]
    for cue in audio:
        cue.update(start={"boundary": "start"}, end={"boundary": "end"})
    plan = EditPlan.model_validate({
        "schema_version": 1, "project_id": "biznex-the-yes-machine", "fps": 30,
        "width": 1080, "height": 1920, "timing_file": "timing.json", "shots": shots,
        "audio": audio, "captions": {"max_words": 4, "max_characters": 30},
        "policy": {"min_shots": 13, "min_visual_assets": 1, "min_visual_kinds": 3,
                   "min_layouts": 12, "min_subjects": 10, "min_framings": 4,
                   "min_camera_moves": 4, "min_shot_seconds": 0.35, "max_shot_seconds": 7.0,
                   "max_static_seconds": 5.0, "max_same_layout_seconds": 7.0,
                   "max_dominant_layout_fraction": 0.3, "max_typography_fraction": 0.0},
    })
    direction = {
        "schema_version": 1, "title": "The Yes Machine — BizNex Stories",
        "audio_master": "assets/audio/master.wav", "brand": "BizNex Stories",
        "context": "Atomy · independent educational community", "shots": directions,
    }
    for name, value in (("EDIT_PLAN.json", plan.model_dump(mode="json", exclude_none=True)), ("DIRECTION.json", direction)):
        (project / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"project": project.name, "shots": len(shots), "measured_seconds": timing.duration_seconds}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    prepare(parser.parse_args().project.resolve())
