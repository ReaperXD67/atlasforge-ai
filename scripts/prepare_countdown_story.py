"""Author the Borrowed Countdown edit from its measured words, without changing voice."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from daily_video_factory.edit_plan import EditPlan, MeasuredTiming  # noqa: E402


def prepare(project: Path) -> None:
    timing = MeasuredTiming.model_validate_json((project / "timing.json").read_text(encoding="utf-8"))
    if not 20 <= timing.duration_seconds <= 40:
        raise ValueError("The countdown story requires 20–40 seconds of measured narration")
    rows = [
        (None, "timer_macro", "object", "timer-digits", "extreme_close", "push_in", "A large mechanical numeral fills the view and physically flips a segment."),
        ("My reason", "reason_empty", "object", "undecided-token", "insert", "tilt", "A solitary ceramic token sits in an empty decision track under the digits' shadow."),
        ("Ten seconds", "countdown", "environment", "timer-tower", "wide", "pull_out", "Reveal the imposing countdown tower and its much smaller undecided token."),
        ("suddenly", "want", "object", "token-shadow", "medium", "tracking", "The timer's shadow crosses the token as the central route starts to feel inevitable."),
        ("My hand", "reach", "object", "moving-token", "close", "push_in", "The token glides toward the countdown, closing its distance to the tower."),
        ("Then I stopped", "halt", "environment", "stopped-route", "medium", "locked", "The token stops before the tower while the numeral mechanism continues independently."),
        ("Was I choosing", "question", "diagram", "choice-route", "wide", "pan", "The camera makes the gap between the token and its supposed destination visible."),
        ("or escaping", "backstage", "object", "shallow-number-frame", "close", "orbit", "Travel behind the giant digits and expose their shallow plates and thin support rods."),
        ("I let the numbers", "exit", "environment", "side-route", "wide", "tracking", "The token takes an unhurried curved side route instead of entering the countdown."),
        ("keep falling", "numbers", "object", "independent-digits", "insert", "pan", "The digits keep changing even though the token has left their route."),
        ("The clock", "clock_finish", "environment", "separated-clock-token", "wide", "pull_out", "Keep the moving clock and independent token in the same world, on separate paths."),
        ("finish its countdown", "empty_front", "object", "empty-timer", "close", "locked", "The numeral mechanism reaches its end with no token beneath it."),
        ("I still needed", "resolve", "diagram", "reason-token", "medium", "pull_out", "Hold the token on its own quiet route beside the question that remains."),
    ]
    shots, directions = [], {}
    for i, (phrase, mode, kind, subject, framing, camera, action) in enumerate(rows, 1):
        shot_id = f"s{i:02d}"
        shots.append({"id": shot_id, "start": {"phrase": phrase} if phrase else {"boundary": "start"},
                      "asset": "assets/world.json", "visual_kind": kind, "subject": subject,
                      "location": "kinetic-countdown-desk", "layout": mode, "framing": framing,
                      "camera": camera, "subject_motion": "still" if mode == "halt" else "action",
                      "action": action, "expression": "Urgency becomes self-questioning, then calm agency.",
                      "cut_reason": action, "transition": {"kind": "cut", "frames": 0}})
        directions[shot_id] = {"mode": mode}
        if mode == "resolve":
            shots[-1]["start"]["offset_frames"] = -10
            directions[shot_id].update(heading="I still needed|a reason.", hide_captions=True)
    audio = [
        {"id": "voice", "role": "voice", "asset": "assets/audio/narration.wav", "gain_db": 0},
        {"id": "score", "role": "music", "asset": "assets/audio/score.wav", "gain_db": 0,
         "duck_db": -6, "duck_attack_frames": 2, "duck_release_frames": 6},
        {"id": "mechanism", "role": "foley", "asset": "assets/audio/machine.wav", "gain_db": -4,
         "duck_db": -3, "duck_attack_frames": 1, "duck_release_frames": 3},
    ]
    for cue in audio:
        cue.update(start={"boundary": "start"}, end={"boundary": "end"})
    plan = EditPlan.model_validate({"schema_version": 1, "project_id": project.name, "fps": 30,
        "width": 1080, "height": 1920, "timing_file": "timing.json", "shots": shots, "audio": audio,
        "captions": {"max_words": 6, "max_characters": 38, "hold_frames": 9},
        "policy": {"min_shots": 12, "min_visual_assets": 1, "min_visual_kinds": 3,
                   "min_layouts": 12, "min_subjects": 10, "min_framings": 4, "min_camera_moves": 4,
                   "min_shot_seconds": 0.35, "max_shot_seconds": 7, "max_static_seconds": 5,
                   "max_same_layout_seconds": 7, "max_dominant_layout_fraction": 0.3,
                   "max_typography_fraction": 0}})
    direction = {"schema_version": 1, "title": "The Borrowed Countdown — BizNex Stories",
                 "audio_master": "assets/audio/master.wav", "brand": "BizNex Stories",
                 "context": "Atomy · independent educational community", "shots": directions}
    for name, value in [("EDIT_PLAN.json", plan.model_dump(mode="json", exclude_none=True)), ("DIRECTION.json", direction)]:
        (project / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"project": project.name, "shots": len(shots), "measured_seconds": timing.duration_seconds}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    prepare(parser.parse_args().project.resolve())
