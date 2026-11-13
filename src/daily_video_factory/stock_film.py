"""Render an authored, stock-only music film against an immutable audio master."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field, model_validator

from daily_video_factory.stock_film_assets import stage_assets

WIDTH, HEIGHT, ACTIVE, FPS = 1920, 1080, 804, 24
TIME_SCALE = 24000
GRADES = {
    "midnight": "eq=contrast=1.04:brightness=-0.018:saturation=0.85,colorbalance=rs=-.035:bs=.045:bm=.025:pl=1",
    "amber": "eq=contrast=1.025:saturation=0.88,colorbalance=rm=.024:bh=-.027:pl=1",
    "silver": "eq=contrast=1.035:saturation=0.70,colorbalance=rs=-.017:bs=.028:bh=.013:pl=1",
    "blue": "eq=contrast=1.045:saturation=0.91,colorbalance=rs=-.026:bs=.052:bm=.031:pl=1",
    "dawn": "eq=contrast=1.025:saturation=0.89,colorbalance=rm=.027:bh=-.028:rh=.024:pl=1",
    "neutral": "null",
}


class Shot(BaseModel, extra="forbid", allow_inf_nan=False):
    asset: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    source_in: float = Field(default=0, ge=0)
    speed: float = Field(default=1, ge=0.35, le=2)
    focal_x: float = Field(default=0.5, ge=0, le=1)
    focal_y: float = Field(default=0.5, ge=0, le=1)
    grade: str = "neutral"
    fade_in: int = Field(default=0, ge=0)
    fade_out: int = Field(default=0, ge=0)
    title: Literal["opening", "closing"] | None = None
    note: str = ""

    @property
    def frames(self) -> int:
        return self.end - self.start


class Film(BaseModel, extra="forbid"):
    title: str = Field(min_length=1, max_length=38)
    frames: int = Field(gt=0)
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assets: dict[str, dict]
    shots: list[Shot] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_edit(self) -> Film:
        next_start = 0
        for shot in self.shots:
            if shot.start != next_start or shot.frames <= 0:
                raise ValueError(f"shot at {shot.start} must tile the timeline at {next_start}")
            if shot.asset not in self.assets or shot.grade not in GRADES:
                raise ValueError(f"unknown asset or grade on shot at {shot.start}")
            if shot.fade_in + shot.fade_out >= shot.frames:
                raise ValueError(f"fades consume the shot at {shot.start}")
            next_start = shot.end
        if next_start != self.frames:
            raise ValueError(f"timeline ends at {next_start}, expected {self.frames}")
        if set(self.assets) != {shot.asset for shot in self.shots}:
            raise ValueError("asset manifest contains unused footage")
        return self


def run(*args: str, input_data: bytes | None = None) -> bytes:
    process = subprocess.run(args, capture_output=True, input=input_data, check=False)
    if process.returncode:
        raise RuntimeError(f"{args[0]}: {process.stderr.decode(errors='replace').strip()}")
    return process.stdout


def ffmpeg(*args: str) -> bytes:
    return run("ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", *args)


def probe(path: Path) -> dict:
    return json.loads(
        run("ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path))
    )


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def font_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    return (
        root / "videos/for-my-sweetheart/assets/fonts/CormorantGaramond.ttf",
        root / "assets/fonts/Barlow-Regular.ttf",
    )


def title_plate(title: str, kind: str, path: Path) -> None:
    """A small optical title treatment, rasterized once from repository-owned typography."""
    serif, sans = font_paths()
    im = Image.new("RGBA", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(im)
    large = ImageFont.truetype(str(serif), 104 if kind == "opening" else 76)
    small = ImageFont.truetype(str(sans), 19)
    y = 521 if kind == "opening" else 712
    ink = (240, 236, 226, 255)
    draw.text((WIDTH // 2 + 1, y + 2), title, font=large, fill=(0, 5, 12, 200), anchor="mm")
    draw.text((WIDTH // 2, y), title, font=large, fill=ink, anchor="mm")
    if kind == "opening":
        label = "A  M U S I C  F I L M"
        draw.text((WIDTH // 2, y + 74), label, font=small, fill=(205, 220, 230, 250), anchor="mm")
    im.save(path)


def shot_filter(shot: Shot, *, titled: bool) -> str:
    filters = [
        f"setpts=(PTS-STARTPTS)/{shot.speed:.6f}",
        f"fps={FPS}",
        f"scale={WIDTH}:{ACTIVE}:force_original_aspect_ratio=increase:force_divisible_by=2:flags=lanczos",
        f"crop={WIDTH}:{ACTIVE}:trunc((iw-ow)*{shot.focal_x:.5f}/2)*2:trunc((ih-oh)*{shot.focal_y:.5f}/2)*2",
        "setsar=1",
        GRADES[shot.grade],
        f"pad={WIDTH}:{HEIGHT}:0:(oh-ih)/2:black",
        "format=yuv420p",
    ]
    if shot.fade_in:
        filters.append(f"fade=t=in:s=0:n={shot.fade_in}")
    if shot.fade_out:
        filters.append(f"fade=t=out:s={shot.frames - shot.fade_out - 1}:n={shot.fade_out}")
    chain = "[0:v]" + ",".join(filters)
    if titled:
        in_frames = min(24, shot.frames // 4)
        out_frames = min(36, shot.frames // 3)
        chain += (
            f"[plate];[1:v]format=rgba,fade=t=in:s=4:n={in_frames}:alpha=1,"
            f"fade=t=out:s={shot.frames - out_frames - 1}:n={out_frames}:alpha=1[title];"
            "[plate][title]overlay=shortest=1"
        )
    return chain + "[cut]"


def encoder_args(encoder: str) -> tuple[str, ...]:
    if encoder == "h264_nvenc":
        return (
            "-c:v",
            encoder,
            "-preset",
            "p6",
            "-tune",
            "hq",
            "-rc",
            "vbr",
            "-cq",
            "18",
            "-b:v",
            "0",
        )
    return ("-c:v", "libx264", "-preset", "fast", "-crf", "17", "-threads", "4")


def validate_sources(film: Film, sources: dict[str, Path], master: Path) -> None:
    master_info = probe(master)
    audio_streams = [s for s in master_info["streams"] if s["codec_type"] == "audio"]
    seconds = float(master_info["format"]["duration"])
    if len(audio_streams) != 1 or not 0 <= film.frames / FPS - seconds < 1 / FPS:
        raise ValueError(
            "song must contain one audio stream and end within the final picture frame"
        )
    durations = {}
    for asset, path in sources.items():
        info = probe(path)
        video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        if not video or video.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
            raise ValueError(f"expected a standard-dynamic-range video for {asset}")
        durations[asset] = float(video.get("duration", info["format"]["duration"]))
    for shot in film.shots:
        if shot.source_in + shot.frames / FPS * shot.speed > durations[shot.asset]:
            raise ValueError(f"shot at {shot.start} exceeds footage for {shot.asset}")


def render_shot(
    shot: Shot,
    source: Path,
    source_hash: str,
    title: Path | None,
    cache: Path,
    encoder: str,
    tool_version: str,
) -> Path:
    graph = shot_filter(shot, titled=title is not None)
    key = hashlib.sha256(
        repr(
            (
                source_hash,
                shot.source_in,
                shot.frames,
                graph,
                encoder_args(encoder),
                tool_version,
                digest(title) if title else None,
            )
        ).encode()
    ).hexdigest()
    segment = cache / f"{key}.mp4"
    if segment.is_file():
        try:
            if int(probe(segment)["streams"][0]["nb_frames"]) == shot.frames:
                return segment
        except (RuntimeError, KeyError, ValueError, IndexError):
            pass
    temporary = cache / f"{key}.{os.getpid()}.{shot.start}.tmp.mp4"
    try:
        extras = ("-loop", "1", "-framerate", str(FPS), "-i", str(title)) if title else ()
        ffmpeg(
            "-y",
            "-filter_complex_threads",
            "2",
            "-threads",
            "2",
            "-ss",
            str(shot.source_in),
            "-i",
            str(source),
            *extras,
            "-filter_complex",
            graph,
            "-map",
            "[cut]",
            "-an",
            "-sn",
            "-frames:v",
            str(shot.frames),
            *encoder_args(encoder),
            "-g",
            "48",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-video_track_timescale",
            str(TIME_SCALE),
            str(temporary),
        )
        if int(probe(temporary)["streams"][0]["nb_frames"]) != shot.frames:
            raise ValueError(
                f"source {shot.asset} did not yield {shot.frames} frames at cut {shot.start}"
            )
        temporary.replace(segment)
    finally:
        temporary.unlink(missing_ok=True)
    return segment


def audio_samples(path: Path) -> np.ndarray:
    return np.frombuffer(
        ffmpeg("-i", str(path), "-map", "0:a:0", "-ac", "2", "-ar", "8000", "-f", "f32le", "-"),
        dtype="<f4",
    ).reshape(-1, 2)


def verify(film: Film, master: Path, output: Path) -> dict:
    info = probe(output)
    video, audio = info["streams"]
    if (
        video["codec_name"],
        video["width"],
        video["height"],
        video["pix_fmt"],
        video["avg_frame_rate"],
        int(video["nb_frames"]),
    ) != ("h264", WIDTH, HEIGHT, "yuv420p", f"{FPS}/1", film.frames):
        raise ValueError("output video stream does not match the timeline")
    if (audio["codec_name"], audio["channels"], audio["sample_rate"]) != ("aac", 2, "48000"):
        raise ValueError("expected 48 kHz stereo AAC")
    clock = json.loads(
        run(
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_packets",
            "-show_entries",
            "packet=pts",
            "-of",
            "json",
            str(output),
        )
    )
    if video["time_base"] != f"1/{TIME_SCALE}" or sorted(
        p["pts"] for p in clock["packets"]
    ) != list(range(0, film.frames * (TIME_SCALE // FPS), TIME_SCALE // FPS)):
        raise ValueError("output contains a gap or drift in the picture timestamps")
    ffmpeg("-xerror", "-i", str(output), "-f", "null", "-")
    original, delivered = audio_samples(master), audio_samples(output)
    if len(delivered) < len(original) - 160 or len(delivered) > len(original) + 160:
        raise ValueError("soundtrack duration drift")
    length = min(len(original), len(delivered))
    correlations = [
        float(np.corrcoef(original[:length, c], delivered[:length, c])[0, 1]) for c in range(2)
    ]
    if not all(np.isfinite(value) and value >= 0.98 for value in correlations):
        raise ValueError(f"soundtrack differs from the master at zero time offset: {correlations}")
    return {
        "title": film.title,
        "duration_seconds": float(info["format"]["duration"]),
        "width": WIDTH,
        "height": HEIGHT,
        "active_picture_height": ACTIVE,
        "fps": FPS,
        "frames": film.frames,
        "shots": len(film.shots),
        "stock_sources": len(film.assets),
        "full_decode": "passed",
        "frame_clock": "passed",
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "audio_correlation_left_right": [round(c, 6) for c in correlations],
        "master_sha256": film.audio_sha256,
        "film_sha256": digest(output),
        "size_bytes": output.stat().st_size,
    }


def concat_duration(shot: Shot) -> str:
    # FFmpeg stores concat durations in whole microseconds. Round absolute edges
    # first, so the fractions cannot accumulate into a timestamp error.
    first, last = (round(frame * 1_000_000 / FPS) for frame in (shot.start, shot.end))
    seconds, microseconds = divmod(last - first, 1_000_000)
    return f"{seconds}.{microseconds:06d}"


def render(film: Film, master: Path, work: Path, output: Path, encoder: str, workers: int) -> dict:
    if output.resolve() == master.resolve() or output.suffix.lower() != ".mp4":
        raise ValueError("output must be a separate .mp4 file")
    if digest(master) != film.audio_sha256:
        raise ValueError("song master does not match the timeline SHA-256")
    sources = stage_assets(film.assets, work / "sources")
    validate_sources(film, sources, master)
    cache = work / "segments"
    cache.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    titles = {}
    for kind in {shot.title for shot in film.shots if shot.title}:
        plate = cache / f"{kind}-{os.getpid()}.png"
        title_plate(film.title, kind, plate)
        titles[kind] = plate
    tool_version = ffmpeg("-version").decode().splitlines()[0]

    def encode(shot: Shot) -> Path:
        return render_shot(
            shot,
            sources[shot.asset],
            film.assets[shot.asset]["sha256"],
            titles.get(shot.title),
            cache,
            encoder,
            tool_version,
        )

    temporary = output.with_name(f".{output.stem}.{os.getpid()}.tmp.mp4")
    concat = cache / f"timeline-{os.getpid()}.ffconcat"
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            segments = list(pool.map(encode, film.shots))
        # Segment basenames are content hashes. Relative paths keep concat's safe mode on.
        # Explicit durations prevent container millisecond rounding from drifting each cut.
        concat.write_text(
            "ffconcat version 1.0\n"
            + "".join(
                f"file {path.name}\nduration {concat_duration(shot)}\n"
                for shot, path in zip(film.shots, segments, strict=True)
            ),
            encoding="ascii",
        )
        ffmpeg(
            "-y",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            str(concat),
            "-i",
            str(master),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            "-metadata",
            f"title={film.title}",
            str(temporary),
        )
        report = verify(film, master, temporary)
        temporary.replace(output)
        return report
    finally:
        temporary.unlink(missing_ok=True)
        concat.unlink(missing_ok=True)
        for plate in titles.values():
            plate.unlink(missing_ok=True)


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("plan", type=Path)
    cli.add_argument("--audio", type=Path, required=True)
    cli.add_argument("--work", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--encoder", choices=("libx264", "h264_nvenc"), default="libx264")
    cli.add_argument("--workers", type=int, choices=range(1, 5), default=2)
    args = cli.parse_args()
    try:
        film = Film.model_validate_json(args.plan.read_bytes())
        report = render(film, args.audio, args.work, args.output, args.encoder, args.workers)
        report_json = json.dumps(report, indent=2) + "\n"
        args.output.with_suffix(".verification.json").write_text(report_json, encoding="utf-8")
        print(report_json, end="")
    except (OSError, ValueError, RuntimeError) as exc:
        cli.exit(1, f"Stock film failed: {exc}\n")


if __name__ == "__main__":
    main()
