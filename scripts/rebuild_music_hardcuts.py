from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from daily_video_factory.config import load_settings
from daily_video_factory.logging import configure_logging
from daily_video_factory.media.ffmpeg import FFmpeg
from daily_video_factory.media.render import VideoRenderer
from daily_video_factory.models import Storyboard


def rebuild(
    run_dir: Path, profile: Path, pass_name: str, *, reuse_scenes: bool = False
) -> tuple[Path, Path]:
    run_dir = run_dir.resolve()
    settings = load_settings(profile)
    storyboard = Storyboard.model_validate_json(
        (run_dir / "storyboards" / "storyboard_timed.json").read_text(encoding="utf-8")
    )
    selection = json.loads((run_dir / "videos" / "selection.json").read_text(encoding="utf-8"))
    selected_video: dict[int, Path] = {}
    for group in ("performer", "stock", "premium", "local"):
        selected_video.update(
            {int(index): Path(path) for index, path in selection.get(group, {}).items()}
        )
    selected_image = {
        int(index): Path(path) for index, path in selection.get("owned", {}).items()
    }

    ffmpeg = FFmpeg()
    renderer = VideoRenderer(settings, ffmpeg)
    scene_dir = run_dir / "videos" / pass_name
    scene_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []

    for position, scene in enumerate(storyboard.scenes, start=1):
        # Music-film geometry is deliberately locked. Beat sync comes from edit timing,
        # typography and color accents instead of artificial camera zooms.
        scene.music_camera_motion = "none"
        output = scene_dir / f"scene_{scene.index:03d}.mp4"
        if reuse_scenes and output.exists() and output.stat().st_size > 0:
            rendered.append(output)
            print(
                f"reused   {position:02d}/{len(storyboard.scenes):02d}: scene {scene.index:03d}",
                flush=True,
            )
            continue
        source = selected_video.get(scene.index)
        if source is not None:
            renderer.normalize_video_scene(
                scene,
                source,
                output,
                duration_seconds=scene.duration_seconds,
            )
        else:
            image = selected_image.get(scene.index, run_dir / "scenes" / f"scene_{scene.index:03d}.jpg")
            renderer.render_scene(
                scene,
                image,
                output,
                duration_seconds=scene.duration_seconds,
            )
        rendered.append(output)
        print(f"rendered {position:02d}/{len(storyboard.scenes):02d}: scene {scene.index:03d}", flush=True)

    silent = run_dir / "videos" / f"assembled_silent_{pass_name}.mp4"
    renderer.concatenate(
        rendered,
        silent,
        [scene.duration_seconds for scene in storyboard.scenes],
        transition_seconds=0.0,
    )
    final = run_dir / "final" / f"video-{pass_name.replace('_', '-')}.mp4"
    ffmpeg.run(
        [
            "-i",
            str(silent),
            "-i",
            str(run_dir / "final" / "video.mp4"),
            "-t",
            f"{storyboard.total_duration_seconds:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )
    return silent, final


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild an existing music-film run with beat-locked hard cuts and locked camera geometry."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--pass-name", default="hardcut_locked_pass")
    parser.add_argument(
        "--reuse-scenes",
        action="store_true",
        help="Reuse already rendered scene files and rebuild only the assembly and audio mux.",
    )
    args = parser.parse_args()
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    configure_logging()
    silent, final = rebuild(
        args.run_dir,
        args.profile,
        args.pass_name,
        reuse_scenes=args.reuse_scenes,
    )
    print(silent.resolve(), flush=True)
    print(final.resolve(), flush=True)


if __name__ == "__main__":
    main()
