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
        self.encoder = self.cfg.codec if ffmpeg.has_encoder(self.cfg.codec) else self.cfg.fallback_codec

    def _video_codec_args(self) -> list[str]:
        if self.encoder.endswith("_nvenc"):
            return ["-c:v", self.encoder, "-preset", self.cfg.preset, "-cq", str(self.cfg.crf)]
        return ["-c:v", self.encoder, "-preset", "medium", "-crf", str(self.cfg.crf)]

    def render_scene(self, scene: Scene, image: Path, output: Path) -> Path:
        frames = max(1, round(scene.duration_seconds * self.cfg.fps))
        fade_out = max(0.1, scene.duration_seconds - 0.25)
        direction = 1 if scene.index % 2 else -1
        x_expr = "iw/2-(iw/zoom/2)" if direction > 0 else "iw/2-(iw/zoom/2)-20*sin(on/90)"
        video_filter = (
            f"scale={self.cfg.width * 2}:{self.cfg.height * 2}:force_original_aspect_ratio=increase,"
            f"crop={self.cfg.width * 2}:{self.cfg.height * 2},"
            f"zoompan=z='min(zoom+0.00045,1.08)':x='{x_expr}':"
            f"y='ih/2-(ih/zoom/2)':d={frames}:s={self.cfg.width}x{self.cfg.height}:fps={self.cfg.fps},"
            "format=yuv420p,"
            f"fade=t=in:st=0:d=0.18,fade=t=out:st={fade_out:.3f}:d=0.25"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        self.ffmpeg.run(
            [
                "-loop", "1",
                "-i", str(image),
                "-t", f"{scene.duration_seconds:.3f}",
                "-vf", video_filter,
                "-an",
                *self._video_codec_args(),
                "-pix_fmt", "yuv420p",
                str(output),
            ]
        )
        return output

    def normalize_cloud_scene(self, scene: Scene, source: Path, output: Path) -> Path:
        fade_out = max(0.1, scene.duration_seconds - 0.25)
        video_filter = (
            f"scale={self.cfg.width}:{self.cfg.height}:force_original_aspect_ratio=increase,"
            f"crop={self.cfg.width}:{self.cfg.height},fps={self.cfg.fps},format=yuv420p,"
            f"fade=t=in:st=0:d=0.18,fade=t=out:st={fade_out:.3f}:d=0.25"
        )
        self.ffmpeg.run(
            [
                "-stream_loop", "-1",
                "-i", str(source),
                "-t", f"{scene.duration_seconds:.3f}",
                "-vf", video_filter,
                "-an",
                *self._video_codec_args(),
                "-pix_fmt", "yuv420p",
                str(output),
            ]
        )
        return output

    def concatenate(self, scene_videos: list[Path], output: Path) -> Path:
        if not scene_videos:
            raise ValueError("At least one scene video is required")
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

