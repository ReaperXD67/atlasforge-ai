from __future__ import annotations

import hashlib
from pathlib import Path

from ..artifacts import atomic_write
from ..config import Settings
from ..models import Scene
from .ffmpeg import FFmpeg


class VideoRenderer:
    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.settings = settings
        self.cfg = settings.video
        self.ffmpeg = ffmpeg
        self.encoder = (
            self.cfg.codec if ffmpeg.can_encode(self.cfg.codec) else self.cfg.fallback_codec
        )
        if not ffmpeg.can_encode(self.encoder):
            raise RuntimeError(
                f"Neither {self.cfg.codec} nor {self.cfg.fallback_codec} can encode a test frame"
            )

    def _video_codec_args(self) -> list[str]:
        if self.encoder.endswith("_nvenc"):
            return ["-c:v", self.encoder, "-preset", self.cfg.preset, "-cq", str(self.cfg.crf)]
        return [
            "-c:v",
            self.encoder,
            "-preset",
            self.cfg.fallback_preset,
            "-crf",
            str(self.cfg.crf),
        ]

    def render_scene(
        self,
        scene: Scene,
        image: Path,
        output: Path,
        *,
        duration_seconds: float | None = None,
    ) -> Path:
        duration = duration_seconds or scene.duration_seconds
        frames = max(2, round(duration * self.cfg.fps))
        progress = f"(0.5-0.5*cos(PI*on/{frames - 1}))"
        direction = 1 if scene.index % 2 else -1
        if scene.visual_mode == "information_card":
            x_expr = "(iw-iw/zoom)*0.5"
            zoom_amount = 0.018
        else:
            x_expr = (
                f"(iw-iw/zoom)*(0.25+0.5*{progress})"
                if direction > 0
                else f"(iw-iw/zoom)*(0.75-0.5*{progress})"
            )
            zoom_amount = 0.045
        # Render the crop from a 2x supersampled canvas. zoompan rounds crop positions to
        # source pixels, so the old 1.25x canvas and vertical sine visibly stepped at 60 fps.
        # A locked optical axis plus 2x sampling makes the fallback feel like a controlled
        # dolly instead of handheld shake.
        y_expr = "(ih-ih/zoom)*0.5"
        source_width = self.cfg.width * 2
        source_height = self.cfg.height * 2
        video_filter = (
            f"scale={source_width}:{source_height}:force_original_aspect_ratio=increase,"
            f"crop={source_width}:{source_height},"
            f"zoompan=z='1+{zoom_amount}*{progress}':x='{x_expr}':y='{y_expr}':"
            f"d={frames}:s={self.cfg.width}x{self.cfg.height}:fps={self.cfg.fps},"
            "format=yuv420p"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        self.ffmpeg.run(
            [
                "-loop",
                "1",
                "-i",
                str(image),
                "-t",
                f"{duration:.3f}",
                "-vf",
                video_filter,
                "-an",
                *self._video_codec_args(),
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]
        )
        return output

    def normalize_video_scene(
        self,
        scene: Scene,
        source: Path,
        output: Path,
        *,
        duration_seconds: float | None = None,
    ) -> Path:
        duration = duration_seconds or scene.duration_seconds
        source_duration = self.ffmpeg.duration(source)
        local_ai = scene.selected_video_provider == "comfyui_wan22"
        speed_factor = duration / source_duration if source_duration > 0 else 1.0
        can_retime = local_ai and 1.0 < speed_factor <= 1.75
        input_args: list[str] = []
        if source_duration > duration + 0.5:
            available = source_duration - duration
            seed = int(hashlib.sha256(str(scene.index).encode()).hexdigest()[:8], 16)
            input_args.extend(["-ss", f"{(seed % 1000) / 1000 * available:.3f}"])
        elif source_duration + 0.2 < duration and not can_retime:
            input_args.extend(["-stream_loop", "-1"])

        filters: list[str] = []
        if can_retime:
            filters.append(f"setpts={speed_factor:.6f}*PTS")
        else:
            filters.append("setpts=PTS-STARTPTS")
        if local_ai and self.cfg.interpolate_low_fps_clips:
            filters.append(
                f"minterpolate=fps={self.cfg.fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
            )
        filters.extend(
            [
                f"scale={self.cfg.width}:{self.cfg.height}:force_original_aspect_ratio=increase",
                f"crop={self.cfg.width}:{self.cfg.height}",
            ]
        )
        if not (local_ai and self.cfg.interpolate_low_fps_clips):
            filters.append(f"fps={self.cfg.fps}")
        if self.cfg.clip_color_grade:
            filters.extend(["eq=contrast=1.035:saturation=0.94:gamma=0.99", "unsharp=3:3:0.18"])
        filters.append("format=yuv420p")
        self.ffmpeg.run(
            [
                *input_args,
                "-i",
                str(source),
                "-t",
                f"{duration:.3f}",
                "-vf",
                ",".join(filters),
                "-an",
                *self._video_codec_args(),
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]
        )
        return output

    # Backward-compatible name for external integrations created before stock/local clips.
    def normalize_cloud_scene(
        self,
        scene: Scene,
        source: Path,
        output: Path,
        *,
        duration_seconds: float | None = None,
    ) -> Path:
        return self.normalize_video_scene(scene, source, output, duration_seconds=duration_seconds)

    def concatenate(
        self,
        scene_videos: list[Path],
        output: Path,
        scene_durations: list[float] | None = None,
    ) -> Path:
        if not scene_videos:
            raise ValueError("At least one scene video is required")
        transition = self.cfg.transition_seconds
        if scene_durations and len(scene_durations) != len(scene_videos):
            raise ValueError("scene_durations must match scene_videos")
        if scene_durations and len(scene_videos) > 1 and transition > 0:
            inputs = [value for path in scene_videos for value in ("-i", str(path))]
            filters = [
                f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS[v{index}]"
                for index in range(len(scene_videos))
            ]
            previous = "v0"
            elapsed = 0.0
            for index in range(1, len(scene_videos)):
                elapsed += scene_durations[index - 1]
                output_label = f"x{index}"
                filters.append(
                    f"[{previous}][v{index}]xfade=transition=fade:duration={transition:.3f}:"
                    f"offset={elapsed:.3f}[{output_label}]"
                )
                previous = output_label
            total_duration = sum(scene_durations)
            fade_out = max(0.0, total_duration - 0.4)
            filters.append(
                f"[{previous}]fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out:.3f}:d=0.4[video]"
            )
            self.ffmpeg.run(
                [
                    *inputs,
                    "-filter_complex",
                    ";".join(filters),
                    "-map",
                    "[video]",
                    *self._video_codec_args(),
                    "-pix_fmt",
                    "yuv420p",
                    str(output),
                ]
            )
            return output
        concat_file = output.with_suffix(".concat.txt")
        lines = []
        for path in scene_videos:
            safe = path.resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{safe}'")
        atomic_write(concat_file, "\n".join(lines) + "\n")
        self.ffmpeg.run(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output),
            ]
        )
        return output

    def finish(
        self,
        silent_video: Path,
        mixed_audio: Path,
        subtitles_ass: Path,
        output: Path,
    ) -> Path:
        filters = []
        if self.settings.subtitles.burn_in:
            filters = ["-vf", f"ass='{self.ffmpeg.filter_path(subtitles_ass)}'"]
        self.ffmpeg.run(
            [
                "-i",
                str(silent_video),
                "-i",
                str(mixed_audio),
                *filters,
                *self._video_codec_args(),
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-shortest",
                str(output),
            ]
        )
        return output
