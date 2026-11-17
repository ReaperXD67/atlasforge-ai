"""Render editable lyric cues over an authored, local image sequence."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from itertools import pairwise
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field, model_validator

from .lyric_cues import Cue, load_cues
from .stock_film import (
    FPS,
    HEIGHT,
    TIME_SCALE,
    WIDTH,
    audio_samples,
    digest,
    encoder_args,
    ffmpeg,
    probe,
)

PLATE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class Crop(BaseModel, extra="forbid", allow_inf_nan=False):
    zoom: float = Field(default=1.05, ge=1, le=2)
    x: float = Field(default=0.5, ge=0, le=1)
    y: float = Field(default=0.5, ge=0, le=1)


class Shot(BaseModel, extra="forbid", allow_inf_nan=False):
    at: float = Field(ge=0)
    image: str = Field(min_length=1)
    enter: Crop = Field(default_factory=Crop)
    leave: Crop = Field(default_factory=lambda: Crop(zoom=1.14))
    dissolve: float = Field(default=0.65, ge=0, le=3)


class Title(BaseModel, extra="forbid", allow_inf_nan=False):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1)


class Edit(BaseModel, extra="forbid", allow_inf_nan=False):
    shots: list[Shot] = Field(min_length=1)
    titles: list[Title] = Field(default_factory=list)
    accent_sections: list[str] = Field(default_factory=list)
    font_family: str = Field(default="Noto Serif CJK SC", pattern=r"^[^,\r\n{}\\]+$")
    fade_in: float = Field(default=1.2, ge=0, le=6)
    fade_out: float = Field(default=2.4, ge=0, le=6)

    @model_validator(mode="after")
    def check_sequence(self) -> Edit:
        frames = [round(shot.at * FPS) for shot in self.shots]
        if self.shots[0].at != 0 or any(a >= b for a, b in pairwise(frames)):
            raise ValueError("shots must start at zero and advance by at least one frame")
        if any(title.end <= title.start for title in self.titles):
            raise ValueError("titles need a positive duration")
        return self


def ass_time(seconds: float) -> str:
    minutes, tick = divmod(round(seconds * 100), 6000)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{tick // 100:02d}.{tick % 100:02d}"


def ass_text(value: str) -> str:
    # Escape the override delimiters and neutralize literal ASS line-break commands.
    return value.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N")


def subtitle_script(edit: Edit, cues: list[Cue]) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,{edit.font_family},63,&H00ECF2FC,&H00ECF2FC,&H500E1618,&H760D1417,0,0,0,0,100,100,3.0,0,1,1.6,3.0,2,170,170,184,1
Style: Refrain,{edit.font_family},68,&H00C5E2FF,&H00C5E2FF,&H4A101719,&H72121A1C,0,0,0,0,100,100,4.0,0,1,1.8,3.4,2,170,170,184,1
Style: Title,{edit.font_family},105,&H00D8E7F4,&H00D8E7F4,&H64090E11,&H76090E11,0,0,0,0,100,100,15,0,1,1.5,4,2,170,170,183,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    accents = set(edit.accent_sections)
    for cue in cues:
        style = "Refrain" if cue.section in accents else "Lyric"
        fade = min(210, round((cue.end - cue.start) * 240))
        motion = rf"{{\move(960,902,960,892,0,{fade})\fad({fade},{fade})\blur0.65}}"
        events.append(
            f"Dialogue: 0,{ass_time(cue.start)},{ass_time(cue.end)},{style},,0,0,0,,"
            f"{motion}{ass_text(cue.text)}"
        )
    for title in edit.titles:
        fade = min(1450, round((title.end - title.start) * 300))
        motion = rf"{{\move(960,860,960,844,0,{fade})\fad({fade},{fade})\blur0.7}}"
        events.append(
            f"Dialogue: 1,{ass_time(title.start)},{ass_time(title.end)},Title,,0,0,0,,"
            f"{motion}{ass_text(title.text)}"
        )
    return header + "\n".join(events) + "\n"


def montage(folder: Path, cues: list[Cue], duration: float, font_family: str) -> Edit:
    """Make a first cut from lyric entrances and an ordered folder of local artwork."""
    plates = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.casefold() in PLATE_EXTENSIONS),
        key=lambda p: (p.name.casefold(), p.name),
    )
    if not plates:
        raise ValueError(f"add a JPG, PNG or WebP background to {folder}")

    starts = [0.0]
    section = cues[0].section
    for cue in cues:
        change = cue.section != section
        elapsed = cue.start - starts[-1]
        if cue.start <= duration - 3.0 and elapsed >= (5.0 if change else 9.0):
            starts.append(cue.start)
            section = cue.section
    starts.append(duration)

    # Let the instrumental breaks breathe while maintaining a visual change over long gaps.
    paced = [0.0]
    for start, end in pairwise(starts):
        cuts = max(1, math.ceil((end - start) / 16.0))
        paced.extend(start + (end - start) * i / cuts for i in range(1, cuts + 1))
    shots = [
        Shot(
            at=start,
            image=str(plates[i % len(plates)]),
            enter=Crop(zoom=1.04 if i % 2 == 0 else 1.15, x=0.42),
            leave=Crop(zoom=1.15 if i % 2 == 0 else 1.04, x=0.58),
        )
        for i, start in enumerate(paced[:-1])
    ]
    return Edit(
        shots=shots,
        font_family=font_family,
        fade_in=min(1.2, paced[1] / 5),
        fade_out=min(2.0, (duration - shots[-1].at) / 4),
    )


def motion_graph(source: int, enter: Crop, leave: Crop, frames: int, label: str) -> str:
    phase = f"on/{max(1, frames - 1)}"
    ease = f"(({phase})*({phase})*(3-2*({phase})))"

    def move(start: float, end: float) -> str:
        return f"({start:.6f}+({end - start:.6f})*{ease})"

    zoom = move(enter.zoom, leave.zoom)
    x = move(enter.x, leave.x)
    y = move(enter.y, leave.y)
    return (
        f"[{source}:v]scale=3840:2160:force_original_aspect_ratio=increase:"
        "force_divisible_by=2:flags=lanczos,crop=3840:2160,format=yuv444p,"
        f"zoompan=z='{zoom}':x='(iw-iw/zoom)*{x}':y='(ih-ih/zoom)*{y}'"
        f":d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1[{label}]"
    )


def encode_shot(
    index: int,
    edit: Edit,
    edges: list[int],
    plates: list[Path],
    work: Path,
    encoder: str,
) -> None:
    shot = edit.shots[index]
    start, end = edges[index : index + 2]
    count = end - start
    incoming = round(shot.dissolve * FPS) if index else 0
    args = ["-i", str(plates[index])]
    filters = [motion_graph(0, shot.enter, shot.leave, count, "new")]
    view = "[new]"
    if incoming:
        previous = edit.shots[index - 1].leave
        args.extend(("-i", str(plates[index - 1])))
        filters.append(motion_graph(1, previous, previous, incoming + 1, "old"))
        filters.extend(
            (
                f"[old]format=yuva444p,fade=t=out:s=0:n={incoming}:alpha=1[tail]",
                "[new][tail]overlay=format=yuv444:eof_action=pass:repeatlast=0[dissolved]",
            )
        )
        view = "[dissolved]"
    finishing = ["format=yuv420p"]
    if index == 0 and edit.fade_in:
        finishing.append(f"fade=t=in:s=0:n={round(edit.fade_in * FPS)}")
    if index == len(plates) - 1 and edit.fade_out:
        ending = round(edit.fade_out * FPS)
        finishing.append(f"fade=t=out:s={count - ending - 1}:n={ending}")
    finishing.extend(
        (
            f"settb=1/{FPS}",
            f"setpts=PTS+{start}",
            "ass=lyrics.ass:fontsdir=fonts",
            "setpts=PTS-STARTPTS",
        )
    )
    filters.append(view + ",".join(finishing) + "[picture]")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-nostdin",
        "-y",
        "-filter_complex_threads",
        "2",
        *args,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[picture]",
        "-frames:v",
        str(count),
        *encoder_args(encoder),
        "-pix_fmt",
        "yuv420p",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-video_track_timescale",
        str(TIME_SCALE),
        f"shot-{index:03d}.mp4",
    ]
    subprocess.run(command, cwd=work, check=True)


def verify(output: Path, master: Path, frames: int) -> dict[str, object]:
    info = probe(output)
    video, audio = info["streams"]
    if (
        video["width"],
        video["height"],
        video["avg_frame_rate"],
        int(video["nb_frames"]),
        video["codec_name"],
        audio["codec_name"],
    ) != (WIDTH, HEIGHT, f"{FPS}/1", frames, "h264", "aac"):
        raise ValueError("export dimensions, duration or codecs differ from the edit")
    clock = json.loads(
        subprocess.check_output(
            [
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
            ]
        )
    )
    ticks = TIME_SCALE // FPS
    if video["time_base"] != f"1/{TIME_SCALE}" or sorted(
        p["pts"] for p in clock["packets"]
    ) != list(range(0, frames * ticks, ticks)):
        raise ValueError("export has a gap or drift in its picture timestamps")
    ffmpeg("-xerror", "-i", str(output), "-f", "null", "-")
    original, rendered = audio_samples(master), audio_samples(output)
    size = min(len(original), len(rendered))
    if abs(len(original) - len(rendered)) > 200:
        raise ValueError("export audio duration differs from the master")
    correlations = []
    for channel in range(2):
        source = original[:size, channel]
        target = rendered[:size, channel]
        power = np.linalg.norm(source)
        if power == 0:
            if np.max(np.abs(target)) > 0.001:
                raise ValueError("silent source channel has audible signal after encoding")
            correlations.append(None)
            continue
        similarity = float(np.dot(source, target) / (power * np.linalg.norm(target)))
        if not math.isfinite(similarity) or similarity < 0.98:
            raise ValueError("export audio differs from the master at zero offset")
        correlations.append(round(similarity, 6))
    return {
        "duration_seconds": float(info["format"]["duration"]),
        "master_seconds": float(probe(master)["format"]["duration"]),
        "picture": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "frames": frames,
        "full_decode": "passed",
        "frame_clock": "passed",
        "audio_similarity_left_right": correlations,
        "sha256": digest(output),
    }


def render(args: argparse.Namespace) -> dict[str, object]:
    spec = args.edit.resolve() if args.edit else None
    master = args.audio.resolve()
    output = args.output.resolve()
    if output.suffix.casefold() != ".mp4":
        raise ValueError("output must be an .mp4 file")
    if output in (master, spec, args.cues.resolve()):
        raise ValueError("choose an output path distinct from the inputs")
    master_info = probe(master)
    duration = float(master_info["format"]["duration"])
    cues = load_cues(args.cues, duration)
    if not any(s["codec_type"] == "audio" for s in master_info["streams"]):
        raise ValueError("audio input has no soundtrack")
    if spec:
        edit = Edit.model_validate_json(spec.read_text(encoding="utf-8-sig"))
        plates = [(spec.parent / shot.image).resolve() for shot in edit.shots]
    else:
        edit = montage(args.artwork.resolve(), cues, duration, args.font_family)
        plates = [Path(shot.image) for shot in edit.shots]
    for plate in plates:
        if not plate.is_file() or plate.suffix.casefold() not in PLATE_EXTENSIONS:
            raise ValueError(f"missing or unsupported image plate {plate}")
    frames = math.ceil(duration * FPS)
    edges = [round(shot.at * FPS) for shot in edit.shots] + [frames]
    lengths = [b - a for a, b in pairwise(edges)]
    if (
        edit.shots[-1].at >= duration
        or any(length <= 0 for length in lengths)
        or any(title.end > duration for title in edit.titles)
    ):
        raise ValueError("the edit runs past the soundtrack")
    entrances = [round(edit.fade_in * FPS)] + [round(s.dissolve * FPS) for s in edit.shots[1:]]
    entrances[-1] += round(edit.fade_out * FPS)
    if any(entrance >= length for entrance, length in zip(entrances, lengths, strict=True)):
        raise ValueError("a shot is too short for its transition")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lyric-film-", dir=output.parent) as temp:
        work = Path(temp)
        (work / "fonts").mkdir()
        if args.font:
            shutil.copyfile(args.font, work / "fonts" / args.font.name)
        (work / "lyrics.ass").write_text(subtitle_script(edit, cues), encoding="utf-8")
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            tasks = [
                executor.submit(encode_shot, i, edit, edges, plates, work, args.encoder)
                for i in range(len(plates))
            ]
            for i, task in enumerate(tasks, start=1):
                task.result()
                print(f"Rendered shot {i}/{len(plates)}", flush=True)
        concat = []
        for i, (start, end) in enumerate(pairwise(edges)):
            microseconds = round(end * 1_000_000 / FPS) - round(start * 1_000_000 / FPS)
            concat.extend((f"file 'shot-{i:03d}.mp4'", f"duration {microseconds / 1_000_000:.6f}"))
        (work / "shots.txt").write_text("\n".join(concat) + "\n", encoding="ascii")
        assembled = work / "assembled.mp4"
        ffmpeg(
            "-y",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            str(work / "shots.txt"),
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
            "-map_metadata",
            "-1",
            "-video_track_timescale",
            str(TIME_SCALE),
            "-movflags",
            "+faststart",
            str(assembled),
        )
        receipt = verify(assembled, master, frames)
        receipt.update({"shots": len(plates), "lyric_cues": len(cues)})
        assembled.replace(output)
    output.with_suffix(".verification.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    visual = parser.add_mutually_exclusive_group(required=True)
    visual.add_argument("--edit", type=Path, help="Authored shot list")
    visual.add_argument("--artwork", type=Path, help="Build a cut from a folder of numbered images")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--cues", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--font", type=Path, help="Local font matching the edit's font_family")
    parser.add_argument(
        "--font-family", default="Noto Serif CJK SC", help="Font family for --artwork"
    )
    parser.add_argument("--encoder", choices=("libx264", "h264_nvenc"), default="libx264")
    parser.add_argument("--workers", choices=range(1, 5), type=int, default=2)
    args = parser.parse_args()
    try:
        receipt = render(args)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Lyric film failed: {exc}\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
