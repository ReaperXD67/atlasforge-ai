from __future__ import annotations

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
        x_expr = (
            f"(iw-iw/zoom)*(0.25+0.5*{progress})"
            if direction > 0
            else f"(iw-iw/zoom)*(0.75-0.5*{progress})"
        )
        y_expr = f"(ih-ih/zoom)*(0.45+0.1*sin(PI*on/{frames - 1}))"
        source_width = round(self.cfg.width * 1.25)
        source_height = round(self.cfg.height * 1.25)
        video_filter = (
            f"scale={source_width}:{source_height}:force_original_aspect_ratio=increase,"
            f"crop={source_width}:{source_height},"
            f"zoompan=z='1+0.075*{progress}':x='{x_expr}':y='{y_expr}':"
            f"d={frames}:s={self.cfg.width}x{self.cfg.height}:fps={self.cfg.fps},"
            "format=yuv420p"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        self.ffmpeg.run(
            [
                "-loop", "1",
                "-i", str(image),
                "-t", f"{duration:.3f}",
                "-vf", video_filter,
                "-an",
                *self._video_codec_args(),
                "-pix_fmt", "yuv420p",
                str(output),
            ]
        )
        return output

    def normalize_cloud_scene(
        self,
        scene: Scene,
        source: Path,
        output: Path,
        *,
        duration_seconds: float | None = None,
    ) -> Path:
        duration = duration_seconds or scene.duration_seconds
        video_filter = (
            f"scale={self.cfg.width}:{self.cfg.height}:force_original_aspect_ratio=increase,"
            f"crop={self.cfg.width}:{self.cfg.height},fps={self.cfg.fps},format=yuv420p"
        )
        self.ffmpeg.run(
            [
                "-stream_loop", "-1",
                "-i", str(source),
                "-t", f"{duration:.3f}",
                "-vf", video_filter,
                "-an",
                *self._video_codec_args(),
                "-pix_fmt", "yuv420p",
                str(output),
            ]
        )
        return output

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
                f"[{previous}]fade=t=in:st=0:d=0.25,"
                f"fade=t=out:st={fade_out:.3f}:d=0.4[video]"
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
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
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
                "-i", str(silent_video),
                "-i", str(mixed_audio),
                *filters,
                *self._video_codec_args(),
                "-c:a", "aac",
                "-b:a", "256k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-shortest",
                str(output),
            ]
        )
        return output
