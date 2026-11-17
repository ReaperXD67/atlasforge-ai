"""Build time-continuous snowfall inside moving picture masks."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from pydantic import Field

Coord = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
SnowPolygon = Annotated[list[tuple[Coord, Coord]], Field(min_length=3)]
Crop = tuple[float, float, float]

WIDTH, HEIGHT = 640, 360
SNOW_COLOR = (232, 246, 255)


def snow_mask(windows: list[SnowPolygon]) -> Image.Image:
    mask = Image.new("L", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(mask)
    for window in windows:
        draw.polygon([(x * WIDTH, y * HEIGHT) for x, y in window], fill=255)
    # Soften inside the pane while reserving a pixel against resampling over the frame.
    inset = mask.filter(ImageFilter.MinFilter(5))
    return ImageChops.multiply(inset, inset.filter(ImageFilter.GaussianBlur(1)))


def camera_crop(enter: Crop, leave: Crop, frame: int, frames: int) -> Crop:
    phase = frame / max(1, frames - 1)
    eased = phase * phase * (3 - 2 * phase)
    ez, ex, ey = enter
    lz, lx, ly = leave
    return ez + (lz - ez) * eased, ex + (lx - ex) * eased, ey + (ly - ey) * eased


def crop_mask(mask: Image.Image, crop: Crop) -> Image.Image:
    zoom, x, y = crop
    inverse = 1 / zoom
    ox = (1 - inverse) * WIDTH * x
    oy = (1 - inverse) * HEIGHT * y
    return mask.transform(
        mask.size,
        Image.Transform.AFFINE,
        (inverse, 0, ox, 0, inverse, oy),
        Image.Resampling.BILINEAR,
    )


@dataclass(frozen=True)
class SnowLayer:
    mask: Image.Image
    intensity: float
    enter: Crop
    leave: Crop


class Snowfall:
    def __init__(self) -> None:
        rng = np.random.default_rng(0xD1B1E)
        # x, y, drift, fall, phase, radius and opacity. Faster flakes carry the near layer.
        self.far = rng.uniform(
            (0, 0, -0.018, 0.04, 0, 0.42, 90),
            (1, 1, 0.025, 0.10, 6.28, 1.0, 178),
            size=(172, 7),
        )
        self.near = rng.uniform(
            (0, 0, -0.052, 0.12, 0, 0.95, 120),
            (1, 1, 0.062, 0.23, 6.28, 2.05, 226),
            size=(48, 7),
        )

    def alpha(self, t: float, intensity: float, crop: Crop, mask: Image.Image) -> Image.Image:
        alpha = Image.new("L", (WIDTH, HEIGHT))
        if intensity <= 0:
            return alpha
        draw = ImageDraw.Draw(alpha)
        zoom, focal_x, focal_y = crop
        density = intensity**0.5
        particles = np.vstack(
            (
                self.far[: round(len(self.far) * density)],
                self.near[: round(len(self.near) * density)],
            )
        )
        x, y, drift, fall, phase, radius, opacity = particles.T
        x = ((x + drift * t + 0.018 * np.sin(phase + 1.25 * t)) % 1) * zoom - focal_x * (zoom - 1)
        y = ((y + fall * t) % 1) * zoom - focal_y * (zoom - 1)
        for px, py, size, light in zip(x * WIDTH, y * HEIGHT, radius * zoom, opacity, strict=True):
            if -size < px < WIDTH + size and -size < py < HEIGHT + size:
                draw.ellipse(
                    (px - size, py - size, px + size, py + size),
                    fill=round(light * (0.48 + 0.52 * intensity)),
                )
        return ImageChops.multiply(
            alpha.filter(ImageFilter.GaussianBlur(0.5)), crop_mask(mask, crop)
        )


def snow_frame(
    particles: Snowfall,
    current: SnowLayer | None,
    previous: SnowLayer | None,
    frame: int,
    frames: int,
    t: float,
    dissolve: int,
) -> Image.Image:
    pixels = Image.new("RGBA", (WIDTH, HEIGHT), (*SNOW_COLOR, 0))
    mix = min(1.0, frame / dissolve) if dissolve else 1.0
    if current is None or mix == 0:
        top = pixels.getchannel("A")
    else:
        crop = camera_crop(current.enter, current.leave, frame, frames)
        top = particles.alpha(t, current.intensity, crop, current.mask)
        if mix < 1:
            top = top.point([round(value * mix) for value in range(256)])
    if previous is not None and mix < 1:
        tail = particles.alpha(t, previous.intensity, previous.leave, previous.mask)
        tail = tail.point([round(value * (1 - mix)) for value in range(256)])
        top = ImageChops.add(top, tail)
    pixels.putalpha(top)
    return pixels


def build_snow_clip(
    output: Path,
    *,
    current: SnowLayer | None,
    previous: SnowLayer | None,
    start: int,
    frames: int,
    fps: int,
    dissolve: int,
) -> None:
    """Stream RGBA frames into a compact alpha video consumed by the normal shot render."""
    count = frames if current is not None else dissolve
    particles = Snowfall()
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgba",
        "-video_size",
        f"{WIDTH}x{HEIGHT}",
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "qtrle",
        "-pix_fmt",
        "argb",
        "-threads",
        "1",
        str(output),
    ]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        assert process.stdin is not None
        assert process.stderr is not None
        try:
            for frame in range(count):
                picture = snow_frame(
                    particles, current, previous, frame, frames, (start + frame) / fps, dissolve
                )
                process.stdin.write(picture.tobytes())
            process.stdin.close()
        except BrokenPipeError:
            pass
        error = process.stderr.read().decode(errors="replace").strip()
        if process.wait() != 0:
            raise RuntimeError(f"could not encode snowfall for {output.name}: {error}")
