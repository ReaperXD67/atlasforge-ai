"""Author the Question That Stayed edit from its measured words, without changing voice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from daily_video_factory.edit_plan import EditPlan, MeasuredTiming  # noqa: E402


def prepare(project: Path) -> None:
    timing = MeasuredTiming.model_validate_json(
        (project / "timing.json").read_text(encoding="utf-8")
    )
    if not 20 <= timing.duration_seconds <= 40:
        raise ValueError("The ribbon story requires 20–40 seconds of measured narration")
    rows = [
        (
            None,
            "seed",
            "object",
            "question-core",
            "extreme_close",
            "push_in",
            "A small question sits inside the first open ribbon loop.",
        ),
        (
            "First",
            "compliment",
            "object",
            "compliment-ribbon",
            "close",
            "orbit",
            "A gold compliment ribbon winds around the question.",
        ),
        (
            "Then",
            "apology",
            "object",
            "apology-ribbon",
            "insert",
            "pan",
            "A second blush ribbon joins and conceals more of the core.",
        ),
        (
            "By the time",
            "approach",
            "environment",
            "overwrapped-message",
            "wide",
            "pull_out",
            "Reveal the oversized tangle between two separated endpoints.",
        ),
        (
            "pressed send",
            "send",
            "object",
            "failed-message-transfer",
            "medium",
            "tracking",
            "The wrapped message nudges forward but remains trapped in its loops.",
        ),
        (
            "actual question",
            "missing",
            "object",
            "concealed-core",
            "extreme_close",
            "push_in",
            "Inspect the center now crowded by decorative layers.",
        ),
        (
            "So I tried",
            "reset",
            "environment",
            "unfolding-ribbon-world",
            "wide",
            "locked",
            "The coils begin a deliberate continuous unrolling motion.",
        ),
        (
            "Fewer words",
            "fewer",
            "object",
            "loosening-gold-strip",
            "close",
            "orbit",
            "The gold wrapper straightens and becomes a narrow bridge edge.",
        ),
        (
            "No performance",
            "plain",
            "object",
            "flattening-blush-strip",
            "medium",
            "tilt",
            "The second strip relaxes, exposing an unobstructed path.",
        ),
        (
            "what am I agreeing to",
            "question",
            "diagram",
            "clear-question-bridge",
            "wide",
            "pull_out",
            "The exact question becomes visible above a continuous physical bridge.",
        ),
        (
            "The question didn't",
            "clarity",
            "environment",
            "crossing-message",
            "wide",
            "tracking",
            "The camera traverses the bridge as the clear message reaches the other side.",
        ),
        (
            "It became possible",
            "answer",
            "diagram",
            "received-question",
            "medium",
            "locked",
            "Hold the received message on the far endpoint of the now-continuous bridge.",
        ),
    ]
    shots, directions = [], {}
    for i, (phrase, mode, kind, subject, framing, camera, action) in enumerate(rows, 1):
        shot_id = f"s{i:02d}"
        shots.append(
            {
                "id": shot_id,
                "start": {"phrase": phrase} if phrase else {"boundary": "start"},
                "asset": "assets/world.json",
                "visual_kind": kind,
                "subject": subject,
                "location": "ribbon-message-world",
                "layout": mode,
                "framing": framing,
                "camera": camera,
                "subject_motion": "action",
                "action": action,
                "expression": "Self-conscious decoration becomes direct, warm clarity.",
                "cut_reason": action,
                "transition": {"kind": "cut", "frames": 0},
            }
        )
        directions[shot_id] = {"mode": mode}
        if mode in ("question", "answer"):
            shots[-1]["start"]["offset_frames"] = -10
            directions[shot_id].update(
                heading="What am I|agreeing to?"
                if mode == "question"
                else "It became|possible|to answer.",
                hide_captions=True,
            )
    audio = [
        {"id": "voice", "role": "voice", "asset": "assets/audio/narration.wav", "gain_db": 0},
        {
            "id": "score",
            "role": "music",
            "asset": "assets/audio/score.wav",
            "gain_db": 0,
            "duck_db": -6,
            "duck_attack_frames": 2,
            "duck_release_frames": 6,
        },
        {
            "id": "mechanism",
            "role": "foley",
            "asset": "assets/audio/machine.wav",
            "gain_db": -4,
            "duck_db": -3,
            "duck_attack_frames": 1,
            "duck_release_frames": 3,
        },
    ]
    for cue in audio:
        cue.update(start={"boundary": "start"}, end={"boundary": "end"})
    plan = EditPlan.model_validate(
        {
            "schema_version": 1,
            "project_id": project.name,
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "timing_file": "timing.json",
            "shots": shots,
            "audio": audio,
            "captions": {"max_words": 6, "max_characters": 38, "hold_frames": 9},
            "policy": {
                "min_shots": 12,
                "min_visual_assets": 1,
                "min_visual_kinds": 3,
                "min_layouts": 12,
                "min_subjects": 10,
                "min_framings": 4,
                "min_camera_moves": 4,
                "min_shot_seconds": 0.35,
                "max_shot_seconds": 8,
                "max_static_seconds": 5,
                "max_same_layout_seconds": 8,
                "max_dominant_layout_fraction": 0.3,
                "max_typography_fraction": 0,
            },
        }
    )
    direction = {
        "schema_version": 1,
        "title": "The Question That Stayed — BizNex Stories",
        "audio_master": "assets/audio/master.wav",
        "brand": "BizNex Stories",
        "context": "Atomy · independent educational community",
        "shots": directions,
    }
    for name, value in [
        ("EDIT_PLAN.json", plan.model_dump(mode="json", exclude_none=True)),
        ("DIRECTION.json", direction),
    ]:
        (project / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "project": project.name,
                "shots": len(shots),
                "measured_seconds": timing.duration_seconds,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    prepare(parser.parse_args().project.resolve())
