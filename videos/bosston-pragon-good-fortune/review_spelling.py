"""Extract nine native-resolution Bosston lyric proofs from a completed MP4.

Run from the repository root after rendering finishes::

    .venv/Scripts/python.exe videos/bosston-pragon-good-fortune/review_spelling.py \
        videos/bosston-pragon-good-fortune/renders/final.mp4 --output output/spelling-qa

Only the chosen output directory is written. The source captions and video are
read only. The receipt records exact decoded frame times; visual review of the
spelling remains a separate human check.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FPS = 30
CROP = {"x": 190, "y": 830, "width": 1540, "height": 120}
WRONG_BRAND = re.compile(r"(?<![A-Za-z])boston(?![A-Za-z])", re.IGNORECASE)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, check=False, timeout=timeout)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace")[-1800:]
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {detail.strip()}")
    return result


def cue_plan(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    cues = payload.get("cues", payload.get("captions")) if isinstance(payload, dict) else payload
    require(isinstance(cues, list), "captions.json must contain a cue array")
    selected = []
    for index, cue in enumerate(cues):
        text = cue["text"]
        require(not WRONG_BRAND.search(text), f"Wrong spelling in source cue {index}: {text}")
        if "Bosston" not in text:
            continue
        start, end = float(cue["start"]), float(cue["end"])
        require(
            math.isfinite(start) and math.isfinite(end) and 0 <= start < end,
            f"Invalid timing in cue {index}",
        )
        frame = math.floor((start + end) / 2 * FPS)
        sample_time = frame / FPS
        require(start < sample_time < end, f"No interior midpoint frame for cue {index}")
        selected.append(
            {
                "cue_index": index,
                "cue_number": index + 1,
                "start": start,
                "end": end,
                "expected_text": text,
                "frame": frame,
                "planned_time": sample_time,
                "interior_frame_bounds": [math.floor(start * FPS) + 1, math.ceil(end * FPS) - 1],
                "distance_from_start_seconds": sample_time - start,
                "distance_to_end_seconds": end - sample_time,
            }
        )
    require(len(selected) == 9, f"Expected nine Bosston lyric cues; received {len(selected)}")
    require(
        [c["frame"] for c in selected] == sorted({c["frame"] for c in selected}),
        "Spelling sample frames must be unique and ordered",
    )
    return selected


def extract(video: Path, output: Path) -> dict:
    require(video.is_file(), f"Completed video does not exist: {video}")
    caption_path = ROOT / "captions.json"
    caption_hash = sha256(caption_path)
    selected = cue_plan(caption_path)
    metadata = json.loads(
        run(
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)
        ).stdout
    )
    stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    require(
        (stream["width"], stream["height"]) == (1920, 1080),
        "Expected a 1920 x 1080 video; native crop coordinates would otherwise be wrong",
    )
    require(
        Fraction(stream["avg_frame_rate"]) == FPS and Fraction(stream["r_frame_rate"]) == FPS,
        "Exact frame-number sampling requires the film's 30 fps export",
    )
    duration = float(metadata["format"]["duration"])
    require(abs(duration - 185) < 0.04, "Expected the completed 185-second film")
    require(
        abs(float(stream.get("start_time", 0))) < 1 / FPS, "Unexpected nonzero video start time"
    )
    video_hash = sha256(video)
    video_stat = (video.stat().st_size, video.stat().st_mtime_ns)
    output.mkdir(parents=True, exist_ok=True)

    # One sequential decode selects original frame numbers; no time-seek rounding.
    select = "+".join(f"eq(n\\,{cue['frame']})" for cue in selected)
    crop = f"crop={CROP['width']}:{CROP['height']}:{CROP['x']}:{CROP['y']}"
    decoded = run(
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-v",
        "info",
        "-y",
        "-threads",
        "2",
        "-filter_threads",
        "1",
        "-i",
        str(video),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        f"select={select},{crop},showinfo",
        "-frames:v",
        "9",
        "-fps_mode",
        "vfr",
        "-threads",
        "1",
        "-start_number",
        "1",
        str(output / "decoded-%02d.png"),
    )
    log = decoded.stderr.decode("utf-8", errors="replace")
    timestamps = re.findall(
        r"Parsed_showinfo_\d+[^\r\n]*\bn:\s*\d+[^\r\n]*\bpts_time:([\d.eE+-]+)", log
    )
    require(len(timestamps) == 9, f"Expected nine decoded frame timestamps; got {len(timestamps)}")

    header, row_height = 84, 166
    board = Image.new("RGB", (1580, header + row_height * len(selected)), "#101115")
    draw = ImageDraw.Draw(board)
    font_path = ROOT / "assets/fonts/NotoSerifCJKsc-Regular.otf"
    title_font = ImageFont.truetype(str(font_path), 27)
    label_font = ImageFont.truetype(str(font_path), 22)
    draw.text(
        (20, 8),
        "Encoded Bosston spelling — all nine lyric appearances",
        font=title_font,
        fill="#ffe0a0",
    )
    draw.text(
        (20, 48), f"{video.name}  |  SHA-256 {video_hash[:24]}…", font=label_font, fill="#aeb2bd"
    )
    for number, (cue, timestamp) in enumerate(zip(selected, timestamps, strict=True), start=1):
        actual_time = float(timestamp)
        require(
            abs(actual_time - cue["planned_time"]) < 0.001,
            f"Decoded timestamp differs from selected frame for cue {cue['cue_index']}",
        )
        require(
            cue["start"] < actual_time < cue["end"],
            f"Decoded frame escaped cue bounds for cue {cue['cue_index']}",
        )
        temporary = output / f"decoded-{number:02d}.png"
        with Image.open(io.BytesIO(temporary.read_bytes())) as decoded_image:
            image = decoded_image.convert("RGB")
        require(image.size == (CROP["width"], CROP["height"]), "Unexpected native crop size")
        strip = output / f"{number:02d}-cue-{cue['cue_index']:03d}-frame-{cue['frame']:04d}.png"
        image.save(strip)
        temporary.unlink()
        cue.update(
            {
                "actual_time": actual_time,
                "decoded_strip": str(strip),
                "decoded_strip_sha256": sha256(strip),
                "timing_within_cue": True,
            }
        )
        y = header + (number - 1) * row_height
        board.paste(image, (20, y))
        draw.text(
            (20, y + 123),
            f"{number:02d}  {actual_time:07.3f}s  |  EXPECTED: {cue['expected_text']}",
            font=label_font,
            fill="#ddd6c8",
        )
        draw.line((20, y + row_height - 4, 1560, y + row_height - 4), fill="#30333b")

    require(
        video_stat == (video.stat().st_size, video.stat().st_mtime_ns),
        "Video changed during extraction; rerun after rendering completes",
    )
    require(
        sha256(video) == video_hash and sha256(caption_path) == caption_hash,
        "Video or captions changed during extraction",
    )
    board_path = output / "all-nine-bosston-strips.png"
    board.save(board_path)
    return {
        "video": str(video),
        "video_sha256": video_hash,
        "video_size_bytes": video_stat[0],
        "video_duration_seconds": duration,
        "caption_path": str(caption_path),
        "caption_sha256": caption_hash,
        "fps": FPS,
        "crop": CROP,
        "method": "One FFmpeg decode selects exact original frame numbers; native-size lyric crops, no text overlay on crops",
        "selected_cues": selected,
        "contact_sheet": str(board_path),
        "contact_sheet_sha256": sha256(board_path),
        "visual_review": "pending; source spelling and extraction do not establish encoded spelling without inspecting the nine crops",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Completed 1920 x 1080, 30 fps, 185-second MP4")
    parser.add_argument(
        "--output", type=Path, required=True, help="Directory for nine strips, sheet and JSON"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    data = extract(args.video.resolve(), output)
    target = output / "encoded-spelling-evidence.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "extracted_cues": len(data["selected_cues"]),
                "manifest": str(target),
                "contact_sheet": data["contact_sheet"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
