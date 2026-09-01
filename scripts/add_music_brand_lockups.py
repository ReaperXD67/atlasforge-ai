"""Add reusable opening and closing brand lockups to a finished music film.

The treatment is intentionally camera-locked: only the graphic layers animate.  This keeps
the footage stable while allowing a vocal-hit wordmark and a premium partner end card.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _resolve_ffmpeg_executable(candidate: str | Path) -> str:
    requested = str(candidate)
    executable = shutil.which(requested) or requested
    try:
        subprocess.run(
            [executable, "-version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return executable
    except (OSError, subprocess.CalledProcessError):
        if requested.lower() != "ffmpeg":
            raise
        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise RuntimeError(
                "The system FFmpeg executable is unavailable and imageio-ffmpeg is not installed."
            ) from exc
        return imageio_ffmpeg.get_ffmpeg_exe()


def _probe(
    path: Path,
    *,
    ffmpeg_executable: str | Path = "ffmpeg",
    ffprobe_executable: str | Path | None = None,
) -> dict[str, float | int]:
    probe = str(ffprobe_executable) if ffprobe_executable else shutil.which("ffprobe")
    if probe:
        try:
            result = subprocess.run(
                [
                    probe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,r_frame_rate:format=duration",
                    "-of",
                    "json",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            stream = payload["streams"][0]
            numerator, denominator = stream["r_frame_rate"].split("/", maxsplit=1)
            return {
                "width": int(stream["width"]),
                "height": int(stream["height"]),
                "fps": float(numerator) / float(denominator),
                "duration": float(payload["format"]["duration"]),
            }
        except (OSError, subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError):
            # Some managed Windows hosts block the system ffprobe binary while allowing the
            # project's frozen FFmpeg runtime.  Fall back to FFmpeg's deterministic header.
            pass

    result = subprocess.run(
        [str(ffmpeg_executable), "-hide_banner", "-i", str(path)],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    header = result.stderr
    duration_match = re.search(r"Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)", header)
    video_line = next((line for line in header.splitlines() if "Video:" in line), "")
    size_match = re.search(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", video_line)
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s+fps", video_line)
    if not duration_match or not size_match or not fps_match:
        raise RuntimeError(f"Could not probe media header for {path}")
    hours, minutes, seconds = duration_match.groups()
    return {
        "width": int(size_match.group(1)),
        "height": int(size_match.group(2)),
        "fps": float(fps_match.group(1)),
        "duration": int(hours) * 3600 + int(minutes) * 60 + float(seconds),
    }


def _filter_path(path: Path) -> str:
    # FFmpeg's filter parser treats the Windows drive colon as syntax even when invoked
    # without a shell.  Forward slashes plus an escaped colon are portable here.
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _drawtext_text(value: str) -> str:
    return (
        value.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(":", r"\:")
        .replace("%", r"\%")
    )


def _build_filter(
    *,
    width: int,
    height: int,
    fps: float,
    font_path: Path,
    opening_text: str,
    opening_duration: float,
    endcard_duration: float,
    opening_logo_input: int | None = None,
    closing_poster_input: int | None = None,
    closing_poster_start: float | None = None,
    closing_poster_end: float | None = None,
) -> str:
    font = _filter_path(font_path)
    word = _drawtext_text(opening_text.upper())
    font_size = round(min(width, height) * 0.255)
    ptc_logo_width = round(width * 0.50)
    opening_logo_width = round(width * 0.62)
    ending_logo_input = 2 if opening_logo_input is not None else 1
    endcard_frames = max(1, round(endcard_duration * fps))
    endcard_source_duration = (endcard_frames + 1) / fps

    # The wordmark is already strongly visible on frame zero because the vocal starts at
    # 00:00.000.  Cyan/red ghosts converge during the first 150 ms, then the white face
    # holds cleanly before all graphic layers leave without touching the camera transform.
    alpha = (
        "if(lt(t\\,0.08)\\,0.72+3.5*t\\,"
        f"if(lt(t\\,{opening_duration - 0.28:.3f})\\,1\\,"
        f"if(lt(t\\,{opening_duration:.3f})\\,"
        f"({opening_duration:.3f}-t)/0.28\\,0)))"
    )
    common = (
        f"fontfile='{font}':text='{word}':fontsize={font_size}:"
        "y=(h-text_h)/2-54:"
        f"enable='between(t,0,{opening_duration:.3f})'"
    )
    ghost_alpha = f"0.58*({alpha})"

    main_filters = [
        f"[0:v]fps=fps={fps:.6f}:eof_action=pass,"
        "settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p",
    ]
    if opening_logo_input is None:
        main_filters.extend(
            [
                # Fast chromatic pre-echoes make the logo feel tied to the shouted consonant.
                (
                    f"drawtext={common}:x=(w-text_w)/2-max(9\\,42-230*t):"
                    f"fontcolor=0x31E7FF:borderw=3:bordercolor=0x31E7FF@0.34:alpha='{ghost_alpha}'"
                ),
                (
                    f"drawtext={common}:x=(w-text_w)/2+max(9\\,42-230*t):"
                    f"fontcolor=0xFF315D:borderw=3:bordercolor=0xFF315D@0.30:alpha='{ghost_alpha}'"
                ),
                (
                    f"drawtext={common}:x=(w-text_w)/2:fontcolor=0xF8F5EE:"
                    "borderw=5:bordercolor=0x05070A@0.98:shadowx=0:shadowy=12:"
                    f"shadowcolor=0x000000@0.82:alpha='{alpha}'"
                ),
            ]
        )
    main_filters.extend(
        [
            # Thin motorsport rails provide impact without creating a full-screen flash.
        (
            "drawbox=x=iw*0.17:y=ih*0.675:w=iw*0.21:h=4:color=0x31E7FF@0.86:t=fill:"
            f"enable='between(t,0.025,{opening_duration - 0.08:.3f})'"
        ),
        (
            "drawbox=x=iw*0.62:y=ih*0.675:w=iw*0.21:h=4:color=0xFF315D@0.82:t=fill:"
            f"enable='between(t,0.025,{opening_duration - 0.08:.3f})'"
        ),
        ]
    )
    chains = [",".join(main_filters) + "[baseplate]"]
    main_plate = "baseplate"
    if closing_poster_input is not None:
        if closing_poster_start is None or closing_poster_end is None:
            raise ValueError("Closing-poster timing is required when a poster input is supplied.")
        closing_duration = closing_poster_end - closing_poster_start
        if closing_duration <= 0:
            raise ValueError("Closing-poster end must be after its start.")
        fade_duration = min(1.2, closing_duration)
        fade_start = max(0.0, closing_duration - fade_duration)
        chains.extend(
            [
                (
                    f"[{closing_poster_input}:v]trim=duration={closing_duration:.3f},"
                    "setpts=PTS-STARTPTS,"
                    f"scale={width}:{height}:flags=lanczos,format=yuv420p,"
                    f"fade=t=out:st={fade_start:.3f}:d={fade_duration:.3f},"
                    f"setpts=PTS+{closing_poster_start:.3f}/TB[closingposter]"
                ),
                (
                    f"[{main_plate}][closingposter]overlay=x=0:y=0:repeatlast=0:"
                    "eof_action=pass:format=auto[posterplate]"
                ),
            ]
        )
        main_plate = "posterplate"
    if opening_logo_input is not None:
        # The client-supplied transparent wordmark is the typography source of truth.  The
        # derived layers change only color/opacity, never the silhouette or proportions.
        chains.extend(
            [
                (
                    f"[{opening_logo_input}:v]trim=duration={opening_duration:.3f},"
                    f"setpts=PTS-STARTPTS,scale={opening_logo_width}:-1:flags=lanczos,"
                    "format=rgba,"
                    f"fade=t=out:st={opening_duration - 0.28:.3f}:d=0.28:alpha=1,"
                    "split=4[pragonwhite][pragoncyanbase][pragonredbase][pragonshadowbase]"
                ),
                (
                    "[pragoncyanbase]lutrgb=r=0:g='val*0.90':b=val,"
                    "colorchannelmixer=aa=0.40[pragoncyan]"
                ),
                (
                    "[pragonredbase]lutrgb=r=val:g='val*0.16':b='val*0.30',"
                    "colorchannelmixer=aa=0.36[pragonred]"
                ),
                (
                    "[pragonshadowbase]lutrgb=r=0:g=0:b=0,"
                    "colorchannelmixer=aa=0.74,gblur=sigma=7[pragonshadow]"
                ),
                (
                    f"[{main_plate}][pragonshadow]overlay=x='(W-w)/2':"
                    "y='(H-h)/2-58':format=auto:eof_action=pass[p1]"
                ),
                (
                    "[p1][pragoncyan]overlay=x='(W-w)/2-max(7\\,34-180*t)':"
                    "y='(H-h)/2-66':format=auto:eof_action=pass[p2]"
                ),
                (
                    "[p2][pragonred]overlay=x='(W-w)/2+max(7\\,34-180*t)':"
                    "y='(H-h)/2-66':format=auto:eof_action=pass[p3]"
                ),
                (
                    "[p3][pragonwhite]overlay=x='(W-w)/2':y='(H-h)/2-66':"
                    "format=auto:eof_action=pass,format=yuv420p[main]"
                ),
            ]
        )
    else:
        chains.append(f"[{main_plate}]null[main]")
    chains.extend(
        [
        # Remove the supplied artwork's opaque black field, preserving the artist's white
        # linework exactly.  The three copies create a restrained chromatic edge-light.
        (
            f"[{ending_logo_input}:v]trim=duration={endcard_duration:.3f},setpts=PTS-STARTPTS,"
            f"scale={ptc_logo_width}:-1:flags=lanczos,format=rgba,"
            "colorkey=0x000000:0.055:0.085,"
            "fade=t=in:st=0.12:d=0.48:alpha=1,"
            f"fade=t=out:st={endcard_duration - 0.42:.3f}:d=0.40:alpha=1,"
            "split=3[ptcwhite][ptccyanbase][ptcredbase]"
        ),
        "[ptccyanbase]lutrgb=r=0:g=val:b=val,colorchannelmixer=aa=0.22[ptccyan]",
        "[ptcredbase]lutrgb=r=val:g='val*0.16':b='val*0.30',colorchannelmixer=aa=0.20[ptcred]",
        (
            f"color=c=0x010305:s={width}x{height}:r={fps:.6f}:"
            f"d={endcard_source_duration:.6f},trim=end_frame={endcard_frames},"
            "setpts=PTS-STARTPTS,format=rgba,vignette=angle=PI/5,"
            "drawbox=x=iw*0.19:y=ih*0.91:w=iw*0.18:h=3:color=0x31E7FF@0.68:t=fill:"
            f"enable='between(t,0.42,{endcard_duration - 0.28:.3f})',"
            "drawbox=x=iw*0.63:y=ih*0.91:w=iw*0.18:h=3:color=0xFF315D@0.64:t=fill:"
            f"enable='between(t,0.42,{endcard_duration - 0.28:.3f})'[endbase]"
        ),
        (
            "[endbase][ptccyan]overlay=x='(W-w)/2-5':"
            "y='(H-h)/2-12+24*max(0\\,1-t/0.55)':format=auto:eof_action=pass[e1]"
        ),
        (
            "[e1][ptcred]overlay=x='(W-w)/2+5':"
            "y='(H-h)/2-12+24*max(0\\,1-t/0.55)':format=auto:eof_action=pass[e2]"
        ),
        (
            "[e2][ptcwhite]overlay=x='(W-w)/2':"
            "y='(H-h)/2-12+24*max(0\\,1-t/0.55)':format=auto:eof_action=pass,"
            "format=yuv420p,settb=AVTB[endcard]"
        ),
        f"[main][endcard]concat=n=2:v=1:a=0,"
        f"fps=fps={fps:.6f}:eof_action=pass,settb=AVTB[outv]",
        ]
    )
    return ";".join(chains)


def add_brand_lockups(
    *,
    input_video: Path,
    ending_logo: Path,
    output_video: Path,
    font_path: Path,
    opening_logo: Path | None = None,
    closing_poster: Path | None = None,
    closing_poster_start: float | None = None,
    closing_poster_end: float | None = None,
    opening_text: str = "PRAGON",
    opening_duration: float = 1.30,
    endcard_duration: float = 3.60,
    crf: int = 13,
    preset: str = "medium",
    ffmpeg_executable: str | Path = "ffmpeg",
    ffprobe_executable: str | Path | None = None,
) -> Path:
    ffmpeg_executable = _resolve_ffmpeg_executable(ffmpeg_executable)
    input_video = input_video.resolve()
    ending_logo = ending_logo.resolve()
    output_video = output_video.resolve()
    font_path = font_path.resolve()
    opening_logo = opening_logo.resolve() if opening_logo else None
    closing_poster = closing_poster.resolve() if closing_poster else None
    required_paths = [input_video, ending_logo]
    required_paths.append(opening_logo if opening_logo else font_path)
    if closing_poster:
        required_paths.append(closing_poster)
    for required in required_paths:
        if not required.exists():
            raise FileNotFoundError(required)
    if input_video == output_video:
        raise ValueError("Render to a new path, inspect it, then promote it to the canonical master.")

    media = _probe(
        input_video,
        ffmpeg_executable=ffmpeg_executable,
        ffprobe_executable=ffprobe_executable,
    )
    fps = float(media["fps"])
    if closing_poster and (
        closing_poster_start is None
        or closing_poster_end is None
        or closing_poster_start < 0
        or closing_poster_end > float(media["duration"]) + (1 / fps)
    ):
        raise ValueError("Closing-poster timing must fall within the input video.")
    opening_logo_input = 1 if opening_logo else None
    ending_logo_input = 2 if opening_logo else 1
    closing_poster_input = ending_logo_input + 1 if closing_poster else None
    filter_graph = _build_filter(
        width=int(media["width"]),
        height=int(media["height"]),
        fps=fps,
        font_path=font_path,
        opening_text=opening_text,
        opening_duration=opening_duration,
        endcard_duration=endcard_duration,
        opening_logo_input=opening_logo_input,
        closing_poster_input=closing_poster_input,
        closing_poster_start=closing_poster_start,
        closing_poster_end=closing_poster_end,
    )
    output_video.parent.mkdir(parents=True, exist_ok=True)
    filter_path = output_video.with_suffix(".brand-lockups.fffilter")
    filter_path.write_text(filter_graph, encoding="utf-8")

    command = [
        str(ffmpeg_executable),
        "-hide_banner",
        "-y",
        "-i",
        str(input_video),
    ]
    image_paths = ([opening_logo] if opening_logo else []) + [ending_logo]
    if closing_poster:
        image_paths.append(closing_poster)
    for image_path in image_paths:
        command.extend(
            ["-loop", "1", "-framerate", f"{fps:.6f}", "-i", str(image_path)]
        )
    command.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "[outv]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            f"{fps:.6f}",
            "-fps_mode",
            "cfr",
            "-video_track_timescale",
            str(round(fps * 1000)),
            "-c:a",
            "copy",
            "-map_metadata",
            "0",
            "-metadata",
            "title=PRAGON - Sepang Music Film",
            "-movflags",
            "+faststart",
            str(output_video),
        ]
    )
    _run(command)

    result = _probe(
        output_video,
        ffmpeg_executable=ffmpeg_executable,
        ffprobe_executable=ffprobe_executable,
    )
    expected_duration = float(media["duration"]) + endcard_duration
    if abs(float(result["duration"]) - expected_duration) > max(0.05, 1.5 / fps):
        raise RuntimeError(
            f"Unexpected branded duration {result['duration']}; expected {expected_duration:.3f}."
        )
    return output_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--ending-logo", type=Path, required=True)
    parser.add_argument("--opening-logo", type=Path)
    parser.add_argument("--closing-poster", type=Path)
    parser.add_argument("--closing-poster-start", type=float)
    parser.add_argument("--closing-poster-end", type=float)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--font",
        type=Path,
        default=Path("assets/fonts/BarlowCondensed-Black.ttf"),
    )
    parser.add_argument("--opening-text", default="PRAGON")
    parser.add_argument("--opening-duration", type=float, default=1.30)
    parser.add_argument("--endcard-duration", type=float, default=3.60)
    parser.add_argument("--crf", type=int, default=13)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--ffmpeg-exe", default="ffmpeg")
    parser.add_argument("--ffprobe-exe")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = add_brand_lockups(
        input_video=args.input,
        ending_logo=args.ending_logo,
        output_video=args.output,
        font_path=args.font,
        opening_logo=args.opening_logo,
        closing_poster=args.closing_poster,
        closing_poster_start=args.closing_poster_start,
        closing_poster_end=args.closing_poster_end,
        opening_text=args.opening_text,
        opening_duration=args.opening_duration,
        endcard_duration=args.endcard_duration,
        crf=args.crf,
        preset=args.preset,
        ffmpeg_executable=args.ffmpeg_exe,
        ffprobe_executable=args.ffprobe_exe,
    )
    print(output)


if __name__ == "__main__":
    main()
