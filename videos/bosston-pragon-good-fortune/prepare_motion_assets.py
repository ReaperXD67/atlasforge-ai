"""Stage the nine admitted motion sources as silent, cropped, graded 1080p30 clips.

Run from the repository root with the prepared local source ledger::

    .venv/Scripts/python.exe videos/bosston-pragon-good-fortune/prepare_motion_assets.py

The original source hashes, selected windows, exact filters and output hashes are
recorded in motion-assets.json. Frame-rate conversion duplicates/drops frames;
no optical-flow or generated intermediate motion is used.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DEFAULT_LEDGER = REPO / "output/bosston-revision/motion-ledger.json"
ID_MAP = {"night-drums": "live-drums", "sunrise": "cloud-sunrise"}
FPS = 30
ENCODER_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
GRADE = "eq=contrast=1.035:brightness=0.004:gamma=1.02:saturation=1.045,colorbalance=rh=0.018:gh=0.006:bh=-0.010:rm=0.006:bm=-0.005"
ENCODER = [
    "-c:v",
    "h264_nvenc",
    "-preset",
    "p5",
    "-rc",
    "vbr",
    "-cq",
    "18",
    "-b:v",
    "8M",
    "-maxrate",
    "12M",
    "-bufsize",
    "24M",
    "-g",
    "60",
    "-profile:v",
    "high",
    "-pix_fmt",
    "yuv420p",
    "-color_range",
    "tv",
    "-colorspace",
    "bt709",
    "-color_primaries",
    "bt709",
    "-color_trc",
    "bt709",
]


def run(*args: str) -> bytes:
    result = subprocess.run(args, check=False, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result.stdout


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def probe(path: Path) -> dict:
    return json.loads(
        run("ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path))
    )


def even(value: float) -> int:
    return max(2, int(value) // 2 * 2)


def crop_filters(source: dict, video: dict) -> tuple[list[str], dict]:
    width, height = video["width"], video["height"]
    filters = []
    crop = source.get("required_crop")
    initial = None
    if crop:
        left, top = (
            even(width * crop["x0"]) if crop["x0"] else 0,
            even(height * crop["y0"]) if crop["y0"] else 0,
        )
        cropped_w = even(width * (crop["x1"] - crop["x0"]))
        cropped_h = even(height * (crop["y1"] - crop["y0"]))
        assert left + cropped_w <= width and top + cropped_h <= height
        filters.append(f"crop={cropped_w}:{cropped_h}:{left}:{top}")
        initial = {"x": left, "y": top, "width": cropped_w, "height": cropped_h}
        width, height = cropped_w, cropped_h
    if width / height > 16 / 9:
        final_w, final_h = even(height * 16 / 9), height
    else:
        final_w, final_h = width, even(width * 9 / 16)
    left, top = (
        even((width - final_w) / 2) if width != final_w else 0,
        even((height - final_h) / 2) if height != final_h else 0,
    )
    if final_w != width or final_h != height:
        filters.append(f"crop={final_w}:{final_h}:{left}:{top}")
    filters.extend(
        [
            "scale=1920:1080:flags=lanczos:out_range=tv",
            "setsar=1",
            "fps=30",
            GRADE,
            "format=yuv420p",
        ]
    )
    return filters, {
        "required_crop_pixels": initial,
        "final_aspect_crop": {"x": left, "y": top, "width": final_w, "height": final_h},
    }


def motion_metrics(path: Path) -> dict:
    data = run(
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-an",
        "-vf",
        "fps=3,scale=160:90",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "-",
    )
    frames = np.frombuffer(data, dtype=np.uint8).reshape(-1, 90, 160, 3).astype(np.float32)
    assert len(frames) >= 2
    differences = np.mean(np.abs(np.diff(frames, axis=0)), axis=(1, 2, 3))
    return {
        "sample_fps": 3,
        "frames": len(frames),
        "mean_absolute_difference_0_255": round(float(differences.mean()), 4),
        "median_absolute_difference_0_255": round(float(np.median(differences)), 4),
        "near_static_pair_fraction_below_0_2": round(float(np.mean(differences < 0.2)), 4),
        "interpretation": "Temporal pixel differences support real movement; source contact review determines subject action.",
    }


def stage_variant(source: dict, destination: Path, window: dict, asset_id: str) -> dict:
    source_path = Path(source["local_path"])
    assert digest(source_path) == source["sha256"], f"Changed admitted source: {asset_id}"
    metadata = probe(source_path)
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert video["width"] >= 1920 and video["height"] >= 1080, asset_id
    frame_count = math.floor((window["end"] - window["start"]) * FPS + 1e-6)
    duration = frame_count / FPS
    assert 0 <= window["start"] < window["start"] + duration <= source["duration"] + 1e-6
    filters, crop = crop_filters(source, video)
    filter_text = ",".join(filters)
    target = destination / f"{asset_id}.mp4"
    temporary = destination / f"{asset_id}.preparing.mp4"
    assert target.resolve().is_relative_to(destination.resolve())
    command = [
        ENCODER_FFMPEG,
        "-y",
        "-hide_banner",
        "-v",
        "error",
        "-threads",
        "2",
        "-ss",
        f"{window['start']:.6f}",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        filter_text,
        "-frames:v",
        str(frame_count),
        "-fps_mode",
        "cfr",
        *ENCODER,
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    run(*command)
    result = probe(temporary)
    assert not any(s["codec_type"] == "audio" for s in result["streams"])
    output_video = next(s for s in result["streams"] if s["codec_type"] == "video")
    assert (output_video["width"], output_video["height"], output_video["avg_frame_rate"]) == (
        1920,
        1080,
        "30/1",
    )
    assert output_video["codec_name"] == "h264" and output_video["pix_fmt"] == "yuv420p"
    assert int(output_video["nb_frames"]) == frame_count
    assert abs(float(result["format"]["duration"]) - duration) < 0.04
    run("ffmpeg", "-v", "error", "-xerror", "-i", str(temporary), "-f", "null", "-")
    temporary.replace(target)
    record = {
        "path": target.relative_to(ROOT).as_posix(),
        "duration": duration,
        "width": 1920,
        "height": 1080,
        "fps": FPS,
        "frames": frame_count,
        "source_id": source["asset_id"],
        "source_key": source["id"],
        "source_page": source["source_page"],
        "creator": source["creator"],
        "creator_url": source["creator_url"],
        "license": source["license"],
        "license_url": source["license_url"],
        "source_cdn_url": source["source_cdn_url"],
        "source_sha256": source["sha256"],
        "sha256": digest(target),
        "source_window": {"start": window["start"], "end": window["start"] + duration},
        "source_fps": video["avg_frame_rate"],
        "source_width": video["width"],
        "source_height": video["height"],
        "role": source["role"],
        "crop": crop,
        "filter": filter_text,
        "encoder_args": ENCODER,
        "encoder_binary": ENCODER_FFMPEG,
        "color_space": "bt709",
        "source_audio_removed": True,
        "full_decode": "passed",
        "motion_metrics": motion_metrics(target),
        "admission_notes": source["admission_notes"],
        "interpolation": "fps duplicate/drop only; no optical-flow synthesis",
    }
    target.with_suffix(".license.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Staged {asset_id}: {duration:.3f}s / {frame_count} frames / full decode passed",
        flush=True,
    )
    return record


def stage(source: dict, destination: Path) -> tuple[str, dict]:
    asset_id = ID_MAP.get(source["id"], source["id"])
    windows = source["safe_windows"]
    primary_index = max(range(len(windows)), key=lambda i: windows[i]["end"] - windows[i]["start"])
    variants = []
    for i, window in enumerate(windows):
        name = asset_id if i == primary_index else f"{asset_id}-s{i + 1:02d}"
        variants.append(stage_variant(source, destination, window, name))
    primary = dict(variants[primary_index])
    primary["variants"] = variants
    return asset_id, primary


def contacts(clips: dict, output: Path) -> list[str]:
    output.mkdir(parents=True, exist_ok=True)
    pages = []
    items = [
        (f"{asset_id} / {i + 1}", variant)
        for asset_id, clip in clips.items()
        for i, variant in enumerate(clip["variants"])
    ]
    for offset in range(0, len(items), 3):
        batch = items[offset : offset + 3]
        sheet = Image.new("RGB", (1536, len(batch) * 470), (9, 9, 13))
        draw = ImageDraw.Draw(sheet)
        for row, (asset_id, clip) in enumerate(batch):
            for column, fraction in enumerate((0.25, 0.75)):
                t = clip["duration"] * fraction
                raw = run(
                    "ffmpeg",
                    "-v",
                    "error",
                    "-ss",
                    str(t),
                    "-i",
                    str(ROOT / clip["path"]),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=768:432",
                    "-f",
                    "image2pipe",
                    "-c:v",
                    "png",
                    "-",
                )
                with Image.open(io.BytesIO(raw)) as still:
                    sheet.paste(still.convert("RGB"), (column * 768, row * 470))
                draw.text(
                    (column * 768 + 8, row * 470 + 438),
                    f"{asset_id} | staged {t:.3f}s | warm grade / crop",
                    fill="#ffe2aa",
                )
                draw.text(
                    (column * 768 + 8, row * 470 + 453),
                    f"source {clip['source_id']} | motion MAE {clip['motion_metrics']['mean_absolute_difference_0_255']}",
                    fill="white",
                )
        target = output / f"staged-motion-{offset // 3 + 1:02d}.jpg"
        sheet.save(target, quality=94, subsampling=0)
        pages.append(str(target.resolve()))
    return pages


def apply_usable_ranges(clips: dict) -> None:
    """Preserve the tighter, reviewed framing limits without re-encoding media."""
    for asset_id, clip in clips.items():
        for variant in clip["variants"]:
            usable = {"start": 0.1, "end": round(variant["duration"] - 0.1, 6)}
            source_start = variant["source_window"]["start"]
            if asset_id == "white-lion" and math.isclose(source_start, 19.0, abs_tol=1e-6):
                usable["start"] = 3.0
            if asset_id == "gold-fireworks" and math.isclose(source_start, 15.5, abs_tol=1e-6):
                usable["end"] = 4.8
            assert 0 <= usable["start"] < usable["end"] <= variant["duration"]
            variant["usable_range"] = usable
            (ROOT / variant["path"]).with_suffix(".license.json").write_text(
                json.dumps(variant, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        primary = next(v for v in clip["variants"] if v["path"] == clip["path"])
        clip["usable_range"] = dict(primary["usable_range"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    sources = [c for c in ledger["clips"] if c["admitted"]]
    assert len(sources) == 9, "The reviewed motion selection must contain nine admitted clips."
    destination = ROOT / "assets/footage"
    destination.mkdir(parents=True, exist_ok=True)
    clips = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(stage, source, destination) for source in sources]):
            asset_id, record = future.result()
            clips[asset_id] = record
    clips = dict(sorted(clips.items()))
    pages = contacts(clips, args.ledger.parent / "review/staged")
    output = {
        "schema_version": 1,
        "clips": clips,
        "source_ledger_sha256": digest(args.ledger),
        "source_audio": "removed from every staged clip",
        "grade": GRADE,
        "variant_count": sum(len(c["variants"]) for c in clips.values()),
        "encoder_version": run(ENCODER_FFMPEG, "-version").decode("utf-8").splitlines()[0],
        "encoder_compatibility": "Installed FFmpeg 7.1 supports NVIDIA driver 592.82. System FFmpeg 9.0 NVENC requires a newer driver; no driver or policy changes were made.",
        "review_contact_sheets": pages,
        "staged_visual_review": "pending",
    }
    apply_usable_ranges(clips)
    pending_manifest = ROOT / "motion-assets.pending.json"
    pending_manifest.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pending_manifest.replace(ROOT / "motion-assets.json")
    credits = [
        "# Motion footage credits",
        "",
        "Footage provided by [Pexels](https://www.pexels.com/) under the [Pexels License](https://www.pexels.com/license/). Source audio is discarded; the supplied song is the soundtrack.",
        "",
        "| Staged asset | Creator | Source | Selected source window |",
        "| --- | --- | --- | --- |",
    ]
    for asset_id, clip in clips.items():
        ranges = ", ".join(
            f"{v['source_window']['start']:.3f}–{v['source_window']['end']:.3f}s"
            for v in clip["variants"]
        )
        credits.append(
            f"| {asset_id} | [{clip['creator']}]({clip['creator_url']}) | [{clip['source_id']}]({clip['source_page']}) | {ranges} |"
        )
    (ROOT / "STOCK_CREDITS.md").write_text("\n".join(credits) + "\n", encoding="utf-8")
    print(
        f"Ready: {len(clips)} silent motion clips, 1920 × 1080 at 30 fps; {len(pages)} review sheets."
    )


if __name__ == "__main__":
    main()
