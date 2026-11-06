"""Decode real shot/cut samples into portable review sheets; do not auto-approve art."""
from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from daily_video_factory.story_delivery import verify_current_render
from daily_video_factory.story_pipeline import PipelineError, sha, write


def review(project: Path) -> dict:
    project = project.resolve()
    verified = verify_current_render(project)
    plan = verified["plan"]
    fps, last = plan["fps"], plan["duration_frames"] - 1
    samples = [{"frame": (s["start_frame"] + s["end_frame"] - 1) // 2,
                "label": s["id"] + " midpoint"} for s in plan["shots"]]
    for index, cut in enumerate(plan["transitions"], 1):
        samples.extend({"frame": cut["cut_frame"] + offset, "label": f"cut{index:02} {label}"}
                       for offset, label in ((-1, "before"), (0, "boundary"), (1, "after")))
        if cut["frames"]:
            samples.extend({"frame": frame, "label": "transition handle"} for frame in
                           (cut["start_frame"] - 1, cut["start_frame"], cut["end_frame"] - 1, cut["end_frame"]))
    for shot in plan["shots"]:
        if shot["subject_motion"] != "still":
            samples.extend({"frame": round(shot["start_frame"] + fraction * (shot["duration_frames"] - 1)),
                            "label": shot["id"] + f" motion {fraction:.0%}"} for fraction in (0.1, 0.5, 0.9))
    samples.extend({"frame": frame, "label": "bookend"} for frame in (0, 1, last - 1, last))
    frames = sorted({s["frame"] for s in samples})
    if not all(0 <= frame <= last for frame in frames):
        raise PipelineError("Review sample exceeds the actual film")
    out = project / "qa/frames"
    out.mkdir(parents=True, exist_ok=True)
    select = "+".join(f"eq(n\\,{frame})" for frame in frames)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-threads", "2",
                    "-i", str(verified["video"]), "-filter_threads", "1", "-vf", f"select={select},scale=540:960",
                    "-fps_mode", "vfr", str(out / "frame-%03d.png")], check=True, timeout=300)
    lookup = {frame: out / f"frame-{index:03d}.png" for index, frame in enumerate(frames, 1)}
    if not all(path.is_file() for path in lookup.values()):
        raise PipelineError("Frame extraction did not return every selected frame")
    files = {path.name: sha(path) for path in lookup.values()}
    font = ImageFont.load_default(size=15)
    for offset in range(0, len(samples), 9):
        batch = samples[offset:offset + 9]
        sheet = Image.new("RGB", (850, math.ceil(len(batch) / 3) * 525 + 45), "#11151a")
        draw = ImageDraw.Draw(sheet)
        draw.text((10, 12), f"ACTUAL MP4 | {verified['video_sha256'][:16]}", font=font, fill="white")
        for index, sample in enumerate(batch):
            x, y = 10 + index % 3 * 280, 45 + index // 3 * 525
            with Image.open(lookup[sample["frame"]]) as frame_image:
                sheet.paste(frame_image.convert("RGB").resize((270, 480)), (x, y + 35))
            draw.text((x, y), sample["label"], font=font, fill="white")
            draw.text((x, y + 17), f"f{sample['frame']} | {sample['frame'] / fps:.3f}s", font=font, fill="#bec7ce")
        name = f"sheet-{offset // 9 + 1:02d}.jpg"
        sheet.save(out / name, quality=94)
        files[name] = sha(out / name)
    if sha(verified["video"]) != verified["video_sha256"]:
        raise PipelineError("Film changed while decoding review images")
    result = {"schema_version": 1, "video_sha256": verified["video_sha256"],
              "frame_samples_verified": True, "unique_frames": len(frames), "samples": samples,
              "shot_midpoints": len(plan["shots"]), "cut_boundaries": len(plan["transitions"]),
              "files": files, "visual_review_verified": False, "full_speed_playback_reviewed": False,
              "limitation": "These are decoded review materials, not an automatic story, motion or aesthetic approval."}
    write(out / "frame-review.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        result = review(args.project)
    except Exception:
        print("Decoded frame review failed; inspect current delivery and media tools.")
        return 1
    print(f"[frames] decoded {result['unique_frames']} distinct frames; visual review remains separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
