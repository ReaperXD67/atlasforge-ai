"""Build a contact sheet from the finished film, with one midpoint per shot."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from daily_video_factory.stock_film import FPS, Film, Shot, ffmpeg, font_paths, probe

THUMBNAIL = (328, 184)
COLUMNS, GAP, MARGIN, HEADER, LABEL = 5, 18, 45, 170, 34


def timecode(frame: int) -> str:
    minutes, seconds = divmod(round(frame * 1000 / FPS), 60_000)
    return f"{minutes:02d}:{seconds / 1000:06.3f}"


def midpoint(shot: Shot) -> int:
    return (shot.start + shot.end - 1) // 2


def grab_frame(movie: Path, frame: int) -> Image.Image:
    # Seek slightly before the frame boundary so timestamp rounding cannot skip it.
    seek = max(0, (frame - 0.25) / FPS)
    width, height = THUMBNAIL
    picture = ffmpeg(
        "-ss",
        f"{seek:.6f}",
        "-threads",
        "1",
        "-i",
        str(movie),
        "-map",
        "0:v:0",
        "-filter_threads",
        "1",
        "-vf",
        f"scale={width}:{height}:flags=lanczos",
        "-frames:v",
        "1",
        "-threads",
        "1",
        "-c:v",
        "png",
        "-f",
        "image2pipe",
        "-",
    )
    with Image.open(BytesIO(picture)) as image:
        return image.convert("RGB")


def contact_sheet(film: Film, movie: Path) -> Image.Image:
    video = next((s for s in probe(movie)["streams"] if s["codec_type"] == "video"), None)
    if not video or video.get("avg_frame_rate") != f"{FPS}/1":
        raise ValueError(f"expected a {FPS} fps export")
    if video.get("nb_frames") != str(film.frames):
        raise ValueError("the movie frame count does not match the edit")

    thumb_width, thumb_height = THUMBNAIL
    rows = (len(film.shots) + COLUMNS - 1) // COLUMNS
    pitch = thumb_height + LABEL + GAP
    width = MARGIN * 2 + COLUMNS * thumb_width + (COLUMNS - 1) * GAP
    height = HEADER + rows * pitch - GAP + MARGIN
    sheet = Image.new("RGB", (width, height), "#111823")
    draw = ImageDraw.Draw(sheet)
    serif, sans = font_paths()
    title_font = ImageFont.truetype(str(serif), 65)
    heading_font = ImageFont.truetype(str(sans), 21)
    label_font = ImageFont.truetype(str(sans), 18)
    draw.text((MARGIN, 29), "EDITORIAL CONTACT SHEET", font=heading_font, fill="#98b0c9")
    draw.text((MARGIN, 55), film.title, font=title_font, fill="#f4eee0")
    draw.text(
        (width - MARGIN, 114),
        f"{len(film.shots)} SHOTS   /   {FPS} FPS   /   {timecode(film.frames)}",
        font=heading_font,
        fill="#cbd6e5",
        anchor="ra",
    )
    draw.line((MARGIN, 145, width - MARGIN, 145), fill="#405367", width=1)

    marks = [midpoint(shot) for shot in film.shots]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for index, frame in enumerate(pool.map(lambda mark: grab_frame(movie, mark), marks)):
            row, column = divmod(index, COLUMNS)
            x = MARGIN + column * (thumb_width + GAP)
            y = HEADER + row * pitch
            sheet.paste(frame, (x, y))
            draw.rectangle(
                (x, y + thumb_height, x + thumb_width - 1, y + thumb_height + LABEL - 1),
                fill="#203043",
            )
            draw.text(
                (x + 10, y + thumb_height + LABEL // 2),
                f"{index + 1:02d}   /   {timecode(marks[index])}",
                font=label_font,
                fill="#f4eee0",
                anchor="lm",
            )
            draw.text(
                (x + thumb_width - 10, y + thumb_height + LABEL // 2),
                film.shots[index].grade.upper(),
                font=label_font,
                fill="#aebfd2",
                anchor="rm",
            )

    return sheet


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("edit", type=Path)
    cli.add_argument("movie", type=Path)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        if args.output.suffix.lower() not in {".jpg", ".jpeg"}:
            raise ValueError("the contact sheet output must be a .jpg or .jpeg file")
        film = Film.model_validate_json(args.edit.read_bytes())
        sheet = contact_sheet(film, args.movie)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.output, "JPEG", quality=93, subsampling=0, optimize=True)
    except (OSError, ValueError, RuntimeError) as exc:
        cli.exit(1, f"Contact sheet failed: {exc}\n")


if __name__ == "__main__":
    main()
