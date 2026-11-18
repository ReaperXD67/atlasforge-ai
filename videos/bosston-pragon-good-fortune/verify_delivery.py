r"""Verify the 185-second film and optionally sample every shot from its actual export.

Usage (from the repository root)::

    .\.venv\Scripts\python.exe videos/bosston-pragon-good-fortune/verify_delivery.py \
        videos/bosston-pragon-good-fortune/renders/final.mp4 --report auto --contact-sheet

The receipt records technical checks, not a claim of subjective visual quality.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import unicodedata
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DURATION = 185.0
FPS = 30
FRAMES = 5550
SAMPLE_RATE = 48000
REQUIRED_SOURCES = (
    "index.html", "index.html.in", "master.js", "captions.js", "film-data.js", "motion-assets.json",
    "prepare.py", "captions.json", "lyrics.txt", "scene-plan.json", "audiomap.json",
    "hyperframes.json", "assets/bgm.wav", "assets/gsap.min.js",
    "assets/generated/bosston-pragon.png", "assets/fonts/NotoSerifCJKsc-Regular.otf",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def run(*args: str, timeout: int = 600) -> bytes:
    result = subprocess.run(args, capture_output=True, check=False, timeout=timeout)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace")[-1800:]
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {detail.strip()}")
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_lyric(text: str) -> str:
    """Ignore punctuation/spacing; preserve the spelling and order of every token."""
    return "".join(
        char for char in unicodedata.normalize("NFKC", text)
        if not char.isspace() and unicodedata.category(char)[0] not in {"P", "Z"}
    )


def supplied_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip().rstrip("\\").strip()
        if not line or re.fullmatch(r"(?:\[.*\]|【.*】)", line):
            continue
        line = re.sub(r"^(?:男声|女声|合唱|全体合唱|齐声|男|女|合)\s*[：:]\s*", "", line)
        lines.append(line)
    require(bool(lines), "lyrics.txt contains no sung lines")
    return lines


def captions(path: Path) -> list[dict[str, Any]]:
    payload = json_file(path)
    records = payload.get("cues", payload.get("captions")) if isinstance(payload, dict) else payload
    require(isinstance(records, list) and bool(records), "captions.json needs a nonempty cue array")
    previous_end = 0.0
    for index, cue in enumerate(records):
        require(isinstance(cue, dict), f"Cue {index + 1} is not an object")
        require(isinstance(cue.get("text"), str) and bool(cue["text"].strip()),
                f"Cue {index + 1} needs lyric text")
        start, end = cue.get("start"), cue.get("end")
        require(all(isinstance(t, (int, float)) and not isinstance(t, bool)
                    and math.isfinite(t) for t in (start, end)),
                f"Cue {index + 1} needs finite numeric start/end times")
        require(0 <= start < end <= DURATION,
                f"Cue {index + 1} is outside 0 <= start < end <= {DURATION}")
        require(start >= previous_end - 0.000001, f"Cue {index + 1} overlaps the preceding cue")
        previous_end = end
    return records


def verify_lyrics(cues: list[dict[str, Any]], lyric_path: Path) -> dict[str, Any]:
    lines = supplied_lines(lyric_path)
    # Both the canonical text and the captions could otherwise share the same
    # typo and pass the completeness comparison below.
    wrong_brand = re.compile(r"(?<![A-Za-z])boston(?![A-Za-z])", re.IGNORECASE)
    for source, texts in (
        ("canonical lyrics", lines),
        ("caption text", [cue["text"] for cue in cues]),
        ("caption word text", [word["text"] for cue in cues for word in cue.get("words", [])]),
    ):
        require(not any(wrong_brand.search(text) for text in texts),
                f"Incorrect brand spelling in {source}: use Bosston (double s).")
    expected = normalize_lyric("".join(lines))
    observed = normalize_lyric("".join(cue["text"] for cue in cues))
    if expected != observed:
        mismatch = next((n for n, (a, b) in enumerate(zip(expected, observed, strict=False)) if a != b),
                        min(len(expected), len(observed)))
        raise ValueError(
            f"Caption text differs from lyrics.txt at normalized character {mismatch}: "
            f"expected {expected[max(0, mismatch - 8):mismatch + 24]!r}, "
            f"received {observed[max(0, mismatch - 8):mismatch + 24]!r}"
        )
    return {"supplied_lines": len(lines), "subtitle_cues": len(cues),
            "normalized_characters": len(expected), "text_completeness": "passed",
            "brand_spelling": "Bosston", "brand_spelling_check": "passed",
            "normalization": "NFKC; punctuation and whitespace removed; case preserved",
            "cue_bounds_and_order": "passed"}


def decoded_stereo(path: Path) -> np.ndarray:
    raw = run("ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(path),
              "-map", "0:a:0", "-vn", "-ac", "2", "-ar", str(SAMPLE_RATE),
              "-f", "f32le", "-")
    values = np.frombuffer(raw, dtype="<f4")
    require(values.size % 2 == 0 and values.size > 0, f"Invalid decoded stereo audio: {path}")
    return values.reshape((-1, 2))


def source_hashes() -> dict[str, str]:
    for name in REQUIRED_SOURCES:
        require((ROOT / name).is_file(), f"Missing critical source file: {name}")
    sources = set(ROOT.glob("*.py")) | set(ROOT.glob("*.js")) | set(ROOT.glob("*.html"))
    sources |= set(ROOT.glob("*.json")) | {ROOT / "lyrics.txt"}
    for directory in ("assets", "compositions"):
        sources |= {p for p in (ROOT / directory).rglob("*") if p.is_file()
                    and p.suffix.lower() not in {".log", ".tmp", ".pyc"}}
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(sources)}


def verify(video_path: Path, master_path: Path) -> dict[str, Any]:
    require(video_path.is_file(), f"Missing export: {video_path}")
    require(master_path.is_file(), f"Missing audio master: {master_path}")
    metadata = json.loads(run("ffprobe", "-v", "error", "-show_streams", "-show_format",
                              "-of", "json", str(video_path)))
    videos = [s for s in metadata["streams"] if s.get("codec_type") == "video"]
    audios = [s for s in metadata["streams"] if s.get("codec_type") == "audio"]
    require(len(videos) == len(audios) == 1, "Delivery needs exactly one video and one audio stream")
    picture, sound = videos[0], audios[0]
    require((picture.get("width"), picture.get("height")) == (1920, 1080), "Expected 1920 x 1080")
    require(picture.get("codec_name") == "h264", "Expected H.264 video")
    require(picture.get("pix_fmt") == "yuv420p", "Expected yuv420p pixels")
    for key in ("avg_frame_rate", "r_frame_rate"):
        require(Fraction(picture.get(key, "0/1")) == FPS, f"Expected 30 fps ({key})")
    require(sound.get("codec_name") == "aac", "Expected AAC audio")
    require(sound.get("channels") == 2, "Expected stereo audio")
    require(int(sound.get("sample_rate", 0)) == SAMPLE_RATE, "Expected 48 kHz audio")
    duration = float(metadata["format"]["duration"])
    require(abs(duration - DURATION) <= 1 / FPS, f"Expected 185 seconds, received {duration}")
    require(abs(float(picture.get("start_time", 0))) <= 0.000001, "Video does not start at zero")
    require(abs(float(sound.get("start_time", 0))) <= 0.000001, "Audio does not start at zero")
    progress = run("ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(video_path),
                   "-map", "0:v:0", "-map", "0:a:0", "-progress", "pipe:1", "-nostats",
                   "-f", "null", "-", timeout=1200).decode("utf-8", errors="replace")
    frame_counts = re.findall(r"^frame=(\d+)\s*$", progress, flags=re.MULTILINE)
    require(bool(frame_counts) and "progress=end" in progress, "Full decode did not complete")
    decoded_frames = int(frame_counts[-1])
    require(decoded_frames == FRAMES, f"Expected 5550 decoded frames, received {decoded_frames}")
    original, encoded = decoded_stereo(master_path), decoded_stereo(video_path)
    require(len(original) == round(DURATION * SAMPLE_RATE), "Master is not exactly 185 seconds")
    require(abs(len(encoded) - len(original)) <= 1024,
            f"Decoded audio differs by {len(encoded) - len(original)} samples")
    count = min(len(original), len(encoded))
    correlations = []
    for channel in range(2):
        correlation = float(np.corrcoef(original[:count, channel], encoded[:count, channel])[0, 1])
        require(math.isfinite(correlation) and correlation >= 0.98,
                f"Zero-offset audio correlation failed on channel {channel + 1}: {correlation}")
        correlations.append(round(correlation, 8))
    cues = captions(ROOT / "captions.json")
    lyric_checks = verify_lyrics(cues, ROOT / "lyrics.txt")
    film_data = json.loads((ROOT / "film-data.js").read_text(encoding="utf-8-sig")
                           .partition("=")[2].strip().removesuffix(";"))
    require(film_data.get("captions") == cues, "film-data.js does not match current captions.json")
    require(film_data.get("scenes") == json_file(ROOT / "scene-plan.json"),
            "film-data.js does not match current scene-plan.json")
    markup = (ROOT / "index.html").read_text(encoding="utf-8-sig")
    lyric_elements = re.findall(r'''\bid\s*=\s*["']lyric-\d+["']''', markup)
    require(len(lyric_elements) == len(cues), "index.html lyric elements do not match current cues")
    shots = shot_records(ROOT / "scene-plan.json")
    hashes = source_hashes()
    return {
        "passed": True, "verified_at_utc": datetime.now(UTC).isoformat(),
        "video": str(video_path.resolve()), "size_bytes": video_path.stat().st_size,
        "sha256": sha256(video_path), "duration_seconds": duration,
        "width": 1920, "height": 1080, "fps": FPS, "decoded_frames": decoded_frames,
        "video_codec": "h264", "pixel_format": "yuv420p", "audio_codec": "aac",
        "audio_channels": 2, "audio_sample_rate": SAMPLE_RATE, "full_decode": "passed",
        "master_audio": {"path": str(master_path.resolve()), "sha256": sha256(master_path),
                         "decoded_samples_per_channel": len(original)},
        "audio_comparison": {"offset_samples": 0, "compared_samples_per_channel": count,
                             "decoded_export_samples_per_channel": len(encoded),
                             "per_channel_correlation": correlations, "minimum_required": 0.98},
        "lyrics": lyric_checks, "source_bindings": "current cues, scenes and lyric elements match",
        "shot_count": len(shots), "source_sha256": hashes,
    }


def shot_records(path: Path) -> list[dict[str, Any]]:
    payload = json_file(path)
    records = payload.get("shots", payload.get("scenes")) if isinstance(payload, dict) else payload
    require(isinstance(records, list) and bool(records), "scene-plan.json needs shots or scenes")
    shots = []
    for index, record in enumerate(records):
        require(isinstance(record, dict), f"Shot {index + 1} is not an object")
        start = record.get("start", record.get("at", record.get("start_seconds")))
        end = record.get("end", record.get("end_seconds"))
        if end is None and start is not None:
            length = record.get("duration", record.get("duration_seconds"))
            if length is not None:
                end = start + length
        require(all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end)),
                f"Shot {index + 1} needs numeric start/end or start/duration")
        require(0 <= start < end <= DURATION + 0.000001, f"Shot {index + 1} has invalid bounds")
        shots.append({"index": index + 1, "start": start, "end": end,
                      "label": str(record.get("id", record.get("title", record.get("name", index + 1))))})
    require(abs(shots[0]["start"]) <= 0.000001 and abs(shots[-1]["end"] - DURATION) <= 0.000001,
            "Shot plan must cover the complete recording from zero to 185 seconds")
    require(all(abs(first["end"] - second["start"]) <= 0.000001
                for first, second in zip(shots, shots[1:], strict=False)),
            "Shot plan has gaps, overlaps or out-of-order shots")
    return shots


def wrapped(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont,
            width: int, limit: int = 2) -> list[str]:
    lines, current = [], ""
    for char in text:
        if draw.textlength(current + char, font=font) > width:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def contact_sheets(video_path: Path, directory: Path) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    shots, cues = shot_records(ROOT / "scene-plan.json"), captions(ROOT / "captions.json")
    font_path = ROOT / "assets/fonts/NotoSerifCJKsc-Regular.otf"
    font = ImageFont.truetype(str(font_path), 18)
    small = ImageFont.truetype(str(font_path), 16)
    samples, pages, seen = [], [], set()
    columns, per_page, tile_w, tile_h = 4, 16, 480, 350
    for offset in range(0, len(shots), per_page):
        batch = shots[offset:offset + per_page]
        rows = math.ceil(len(batch) / columns)
        sheet = Image.new("RGB", (columns * tile_w, rows * tile_h + 46), "#101016")
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 9), f"BOSSTON | Pragon — encoded export — shots {offset + 1}–{offset + len(batch)}",
                  font=font, fill="#f5d788")
        for slot, shot in enumerate(batch):
            frame_number = min(FRAMES - 1, math.floor((shot["start"] + shot["end"]) * FPS / 2))
            at = frame_number / FPS
            raw = run("ffmpeg", "-hide_banner", "-v", "error", "-ss", f"{at:.9f}",
                      "-i", str(video_path), "-map", "0:v:0", "-frames:v", "1", "-vf",
                      "scale=480:270", "-f", "image2pipe", "-c:v", "png", "-")
            with Image.open(io.BytesIO(raw)) as still:
                x, y = (slot % columns) * tile_w, 46 + (slot // columns) * tile_h
                sheet.paste(still.convert("RGB"), (x, y))
            selected = [i for i, cue in enumerate(cues) if cue["start"] <= at < cue["end"]]
            seen.update(selected)
            caption_text = " / ".join(cues[i]["text"] for i in selected) or "[instrumental / between lyrics]"
            draw.text((x + 8, y + 273), f"{shot['index']:02d}  {at:07.3f}s  {shot['label'][:28]}",
                      font=small, fill="#f5d788")
            for line_index, line in enumerate(wrapped(caption_text, draw, font, tile_w - 16)):
                draw.text((x + 8, y + 297 + line_index * 23), line, font=font, fill="white")
            samples.append({**shot, "sample_frame": frame_number, "sample_time": round(at, 6),
                            "active_caption_indices": selected, "caption_text": caption_text})
        target = directory / f"contact-sheet-{len(pages) + 1:02d}.jpg"
        sheet.save(target, quality=93, subsampling=0)
        pages.append(str(target.resolve()))
    result = {"contact_sheets": pages, "sampled_shots": len(samples),
              "total_caption_cues": len(cues), "sampled_caption_cues": len(seen),
              "coverage": "one decoded frame at each shot midpoint; sampled visual QA only",
              "samples": samples}
    (directory / "contact-sheet-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--master", type=Path, default=ROOT / "assets/bgm.wav")
    parser.add_argument("--report", default="auto", help="JSON path or auto (beside the MP4)")
    parser.add_argument("--contact-sheet", nargs="?", const="auto", metavar="DIRECTORY",
                        help="Also sample every shot; default directory is renders/review")
    args = parser.parse_args()
    report = args.video.with_suffix(".verification.json") if args.report == "auto" else Path(args.report)
    require(report.resolve() not in {args.video.resolve(), args.master.resolve()},
            "Report path must differ from the video and master")
    try:
        result = verify(args.video, args.master)
        if args.contact_sheet:
            directory = args.video.parent / "review" if args.contact_sheet == "auto" else Path(args.contact_sheet)
            result["visual_review_materials"] = contact_sheets(args.video, directory)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as exc:
        result = {"passed": False, "video": str(args.video.resolve()), "error": str(exc),
                  "verified_at_utc": datetime.now(UTC).isoformat()}
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Verification failed: {exc}\nReceipt: {report}", file=sys.stderr)
        return 1
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    correlations = result["audio_comparison"]["per_channel_correlation"]
    print(f"Verified 185s / 5550 frames / 1080p30; stereo correlation {correlations}; "
          f"{result['lyrics']['subtitle_cues']} complete lyric cues.\nReceipt: {report}")
    if args.contact_sheet:
        print(f"Review sheets: {len(result['visual_review_materials']['contact_sheets'])}; "
              f"shots sampled: {result['visual_review_materials']['sampled_shots']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
