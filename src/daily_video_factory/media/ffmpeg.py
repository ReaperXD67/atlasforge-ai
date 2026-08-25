from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from ..exceptions import ConfigurationError, ProviderFailed
from ..logging import get_logger


class FFmpeg:
    def __init__(self, executable: str | None = None, ffprobe: str | None = None) -> None:
        self.executable = executable or os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg") or ""
        self.ffprobe = ffprobe or os.getenv("FFPROBE_PATH") or shutil.which("ffprobe") or ""
        self.log = get_logger(component="ffmpeg")
        self._encoder_probe_cache: dict[str, bool] = {}

    @property
    def available(self) -> bool:
        return bool(self.executable and self.ffprobe)

    def require(self) -> None:
        if not self.available:
            raise ConfigurationError(
                "FFmpeg and ffprobe are required. Install FFmpeg or set FFMPEG_PATH and FFPROBE_PATH."
            )

    def run(self, args: list[str], timeout_seconds: int = 3600) -> subprocess.CompletedProcess[str]:
        self.require()
        command = [self.executable, "-hide_banner", "-nostdin", "-y", *args]
        self.log.debug("ffmpeg_command", command=command)
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode:
            tail = completed.stderr[-3000:]
            raise ProviderFailed(f"FFmpeg failed ({completed.returncode}): {tail}")
        return completed

    def duration(self, path: Path) -> float:
        self.require()
        completed = subprocess.run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode:
            raise ProviderFailed(f"ffprobe failed for {path}: {completed.stderr[-1000:]}")
        return float(json.loads(completed.stdout)["format"]["duration"])

    def video_motion_profile(
        self,
        path: Path,
        *,
        sample_fps: int = 4,
        width: int = 160,
        height: int = 90,
    ) -> list[float]:
        """Measure frame-to-frame visual change cheaply without adding OpenCV."""
        self.require()
        try:
            completed = subprocess.run(
                [
                    self.executable,
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-i",
                    str(path),
                    "-an",
                    "-vf",
                    f"fps={sample_fps},scale={width}:{height}:flags=fast_bilinear,format=gray",
                    "-pix_fmt",
                    "gray",
                    "-f",
                    "rawvideo",
                    "pipe:1",
                ],
                capture_output=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        frame_size = width * height
        if completed.returncode or len(completed.stdout) < frame_size * 2:
            return []
        import numpy as np

        raw = np.frombuffer(completed.stdout, dtype=np.uint8)
        frame_count = raw.size // frame_size
        frames = raw[: frame_count * frame_size].reshape(frame_count, frame_size).astype(np.int16)
        differences = np.mean(np.abs(np.diff(frames, axis=0)), axis=1) / 255
        return [0.0, *[float(value) for value in differences]]

    def video_scene_boundaries(self, path: Path, *, threshold: float = 0.38) -> list[float]:
        """Return hard-cut timestamps so an extracted window does not straddle two source shots."""
        self.require()
        try:
            completed = subprocess.run(
                [
                    self.executable,
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "info",
                    "-i",
                    str(path),
                    "-an",
                    "-vf",
                    f"select=gt(scene\\,{threshold:.3f}),showinfo",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if completed.returncode:
            return []
        return [
            float(value)
            for value in re.findall(r"\bpts_time:([0-9]+(?:\.[0-9]+)?)", completed.stderr)
        ]

    def has_encoder(self, encoder: str) -> bool:
        if not self.executable:
            return False
        completed = subprocess.run(
            [self.executable, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return completed.returncode == 0 and encoder in completed.stdout

    def can_encode(self, encoder: str) -> bool:
        """Probe an encoder with a real frame; a listed NVENC encoder may still lack driver support."""
        if encoder in self._encoder_probe_cache:
            return self._encoder_probe_cache[encoder]
        if not self.executable or not self.has_encoder(encoder):
            self._encoder_probe_cache[encoder] = False
            return False
        try:
            completed = subprocess.run(
                [
                    self.executable,
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=256x256:r=1",
                    "-frames:v",
                    "1",
                    "-c:v",
                    encoder,
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            self._encoder_probe_cache[encoder] = False
            return False
        result = completed.returncode == 0
        self._encoder_probe_cache[encoder] = result
        return result

    @staticmethod
    def filter_path(path: Path) -> str:
        value = path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
        return value
