"""Compare an encoded V3 film with native Chrome QA screenshots.

Read-only audit; no scene rebuilding, resizing, color fitting, or threshold fitting.
Requires existing NumPy, Pillow, FFmpeg and FFprobe. The expected screenshots are
captured by verify_ai_motion.mjs. A superseded stock export is a negative control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
FPS = 30
# Native pixels, below the logo and above the lyric region; no scaling.
BOX = (200, 260, 1720, 760)
WIDTH, HEIGHT = BOX[2] - BOX[0], BOX[3] - BOX[1]
MIN_SSIM = 0.97
MAX_MAE = 5.0
MIN_SAMPLES = 9
ORIGINAL_ASSETS = {"avenue", "dragon", "ribbon", "sunrise", "drums", "koi", "bridge"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(args, timeout=180):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.decode('utf8', errors='replace')[-1600:]}")
    return result.stdout, result.stderr.decode("utf8", errors="replace")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ffmpeg_path(explicit):
    if explicit:
        require(Path(explicit).is_file(), "Specified FFmpeg is missing.")
        return str(Path(explicit).resolve())
    existing = shutil.which("ffmpeg")
    if existing:
        return existing
    bundled = REPO / ".venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
    require(bundled.is_file(), "FFmpeg is required; provide --ffmpeg.")
    return str(bundled)


def select_samples(qa, data):
    scenes = {s["id"]: s for s in data["scenes"]}
    result = []
    for sample in qa["samples"]:
        t = sample["time"]
        frame = round(t * FPS)
        if abs(t - frame / FPS) > 1e-5:
            continue
        scene = scenes[sample["shot"]]
        # Keep at least .2s clear of either boundary, and all incoming blending.
        margin = max(.2, scene.get("transitionDuration", .2) + .1)
        if t < scene["start"] + margin or t > scene["end"] - .2:
            continue
        result.append({"time": frame / FPS, "qa_time": t, "frame": frame,
                       "shot": scene["id"], "asset": scene["asset"],
                       "section": scene["section"], "screenshot": sample["screenshot"],
                       "asset_generation": "original" if scene["asset"] in ORIGINAL_ASSETS else "new"})
    require(len(result) >= MIN_SAMPLES, f"Only {len(result)} exact-clock non-transition QA samples; need {MIN_SAMPLES}.")
    require({s["asset_generation"] for s in result} == {"original", "new"}, "Samples must cover original and new AI worlds.")
    require(len({s["section"] for s in result}) >= 5, "Samples must span at least five song chapters.")
    return result


def metadata(video, ffprobe):
    raw, _ = run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)])
    meta = json.loads(raw)
    stream = next(s for s in meta["streams"] if s["codec_type"] == "video")
    require((stream["width"], stream["height"]) == (1920, 1080), "Export must be native 1920x1080.")
    require(Fraction(stream["avg_frame_rate"]) == FPS, "Export clock must be exactly 30 fps.")
    return {"width": stream["width"], "height": stream["height"], "fps": stream["avg_frame_rate"],
            "duration": float(meta["format"]["duration"]), "frames": int(stream.get("nb_frames", 0))}


def extract(video, frame, offsets, ffmpeg):
    first = frame + min(offsets)
    require(first >= 0, "Cannot seek before frame zero.")
    count = max(offsets) - min(offsets) + 1
    raw, _ = run([ffmpeg, "-v", "error", "-ss", f"{first / FPS:.9f}", "-i", str(video),
                  "-map", "0:v:0", "-an", "-vf", f"crop={WIDTH}:{HEIGHT}:{BOX[0]}:{BOX[1]}",
                  "-frames:v", str(count), "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    require(len(raw) == count * WIDTH * HEIGHT * 3, "Frame extraction returned the wrong pixel count.")
    images = np.frombuffer(raw, np.uint8).reshape(count, HEIGHT, WIDTH, 3)
    return {offset: images[offset - min(offsets)] for offset in offsets}


def compare(actual, expected, actual_path, expected_path, ffmpeg):
    Image.fromarray(actual).save(actual_path)
    # FFmpeg's native SSIM over three full-resolution RGB planes; no resampling.
    _, log = run([ffmpeg, "-hide_banner", "-v", "info", "-i", str(actual_path), "-i", str(expected_path),
                  "-filter_complex", "[0:v]format=gbrp[a];[1:v]format=gbrp[b];[a][b]ssim", "-f", "null", "-"])
    match = re.search(r"All:([0-9.]+)", log)
    require(match, "FFmpeg did not report SSIM.")
    ssim = float(match[1])
    channels = {channel: float(value) for channel, value in re.findall(r"(R|G|B):([0-9.]+)", log)}
    mae = float(np.abs(actual.astype(np.float32) - expected.astype(np.float32)).mean())
    luma_paths = []
    for rgb, original_path in [(actual, actual_path), (expected, expected_path)]:
        # Separate diagnostic only: native full-range BT709 weighted luma. This
        # does not replace or relax the original three-plane RGB acceptance gate.
        luma = np.round(rgb.astype(np.float32) @ np.array([.2126, .7152, .0722])).clip(0, 255).astype(np.uint8)
        luma_path = original_path.with_name(original_path.stem + "-luma709.png")
        Image.fromarray(luma).save(luma_path)
        luma_paths.append(luma_path)
    _, luma_log = run([ffmpeg, "-hide_banner", "-v", "info", "-i", str(luma_paths[0]), "-i", str(luma_paths[1]),
                       "-lavfi", "ssim", "-f", "null", "-"])
    luma_match = re.search(r"All:([0-9.]+)", luma_log)
    require(luma_match, "FFmpeg did not report diagnostic luma SSIM.")
    return {"ssim": ssim, "rgb_mae_0_255": mae,
            "passed": ssim >= MIN_SSIM and mae <= MAX_MAE,
            "per_channel_rgb_ssim": channels, "diagnostic_luma709_ssim": float(luma_match[1]),
            "actual_crop": str(actual_path.resolve())}


def audit(video, samples, qa_dir, output, ffmpeg, offsets):
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for sample in samples:
        source = qa_dir / sample["screenshot"]
        with Image.open(source) as im:
            require(im.size == (1920, 1080), "Expected screenshot must be native 1920x1080.")
            expected = np.array(im.convert("RGB").crop(BOX))
        expected_path = output / f"{sample['shot']}-{sample['frame']}-expected.png"
        Image.fromarray(expected).save(expected_path)
        frames = extract(video, sample["frame"], offsets, ffmpeg)
        comparisons = []
        for offset in offsets:
            actual_path = output / f"{sample['shot']}-{sample['frame']}-actual-{offset:+d}.png"
            measurement = compare(frames[offset], expected, actual_path, expected_path, ffmpeg)
            comparisons.append({"frame_offset": offset, "encoded_frame": sample["frame"] + offset, **measurement})
        # Always prefer exact time. A nearby match is admissible only when enabled,
        # and every candidate/offset remains in the report.
        accepted = next((c for c in comparisons if c["passed"]), None)
        best = accepted or max(comparisons, key=lambda c: c["ssim"])
        row = {**sample, "passed": accepted is not None, "best": best, "candidates": comparisons,
               "expected_screenshot": str(source.resolve()), "expected_sha256": sha256(source),
               "expected_crop": str(expected_path.resolve())}
        rows.append(row)
        print(f"{video.name} {sample['time']:.3f}s {sample['asset']}: SSIM={best['ssim']:.6f} MAE={best['rgb_mae_0_255']:.3f} offset={best['frame_offset']:+d} pass={row['passed']}", flush=True)
    return {"passed": all(r["passed"] for r in rows), "sample_count": len(rows), "samples": rows,
            "minimum_ssim": min(r["best"]["ssim"] for r in rows),
            "maximum_rgb_mae": max(r["best"]["rgb_mae_0_255"] for r in rows),
            "diagnostic_luma709": {
                "minimum_ssim": min(r["best"]["diagnostic_luma709_ssim"] for r in rows),
                "maximum_ssim": max(r["best"]["diagnostic_luma709_ssim"] for r in rows),
                "all_meet_original_ssim_and_mae_thresholds": all(r["best"]["diagnostic_luma709_ssim"] >= MIN_SSIM and r["best"]["rgb_mae_0_255"] <= MAX_MAE for r in rows),
                "note": "Separate luma diagnostic; never overrides the full-RGB gate or overall passed value."},
            "nonzero_frame_offsets": [r["time"] for r in rows if r["best"]["frame_offset"] != 0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--qa", type=Path, default=REPO / "output/bosston-ai-v3/qa/ai-motion-qa.json")
    parser.add_argument("--data", type=Path, default=ROOT / "film-data.js")
    parser.add_argument("--negative-control", type=Path, default=ROOT / "renders/BOSSTON-Pragon-Good-Fortune-Cinematic.mp4")
    parser.add_argument("--report", type=Path, default=REPO / "output/bosston-ai-v3/ai-binding.json")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    parser.add_argument("--allow-one-frame-offset", action="store_true", help="Try exact frame, then -1/+1; report every offset. Default exact frame only.")
    parser.add_argument("--list-samples", action="store_true", help="List selected expected samples without reading an export.")
    args = parser.parse_args()
    qa = load_json(args.qa)
    require(qa["passed"], "Expected browser QA did not pass.")
    source = args.data.read_text(encoding="utf-8-sig")
    data = json.loads(source.split("=", 1)[1].strip().rstrip(";"))
    require(data["mediaMode"] == "ai-depth-cinema" and data["revision"] == 3, "Expected data is not V3 AI cinema.")
    samples = select_samples(qa, data)
    if args.list_samples:
        print(json.dumps(samples, indent=2))
        return 0
    report = {"passed": False, "verified_at_utc": datetime.now(UTC).isoformat(),
              "video": str(args.video.resolve()), "thresholds": {"minimum_ssim": MIN_SSIM, "maximum_rgb_mae_0_255": MAX_MAE},
              "native_crop_xyxy": BOX, "fps": FPS, "qa_report_sha256": sha256(args.qa), "film_data_sha256": sha256(args.data),
              "method": "Exact-clock non-transition native Chrome screenshots vs native decoded export; FFmpeg RGB SSIM plus NumPy RGB MAE. No resizing, color fitting, masks or alignment optimization.",
              "limits": "Sampled AI picture binding, not every-frame proof, lyric audit or independent motion/audio listening. Color conversion and lossy encoding remain part of comparison."}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        require(args.video.is_file(), "Encoded film does not exist yet.")
        require(args.negative_control.is_file(), "Superseded stock negative control is required.")
        require(args.video.resolve() != args.negative_control.resolve(), "Negative control must differ from target export.")
        ffmpeg = ffmpeg_path(args.ffmpeg)
        offsets = [0, -1, 1] if args.allow_one_frame_offset else [0]
        report["allowed_frame_offsets"] = offsets
        report["metadata"] = metadata(args.video, args.ffprobe)
        report["video_sha256"] = sha256(args.video)
        report["binding"] = audit(args.video, samples, args.qa.parent, args.report.parent / "ai-binding-frames", ffmpeg, offsets)
        # Three same-clock samples from early, middle and late chapters must all
        # reject the old stock picture against the same immutable thresholds.
        controls = [samples[1], samples[len(samples) // 2], samples[-2]]
        negative = audit(args.negative_control, controls, args.qa.parent, args.report.parent / "ai-binding-negative", ffmpeg, [0])
        negative.update({"path": str(args.negative_control.resolve()), "sha256": sha256(args.negative_control),
                         "rejected": all(not s["passed"] for s in negative["samples"]),
                         "luma_rejected": all(s["best"]["diagnostic_luma709_ssim"] < MIN_SSIM or s["best"]["rgb_mae_0_255"] > MAX_MAE for s in negative["samples"])})
        report["negative_control"] = negative
        report["luma_correspondence_passed"] = (
            report["binding"]["diagnostic_luma709"]["all_meet_original_ssim_and_mae_thresholds"]
            and not report["binding"]["nonzero_frame_offsets"] and negative["luma_rejected"]
        )
        report["luma_correspondence"] = {
            "minimum_ssim": MIN_SSIM, "maximum_rgb_mae_0_255": MAX_MAE,
            "exact_frame_only": True, "negative_controls": len(controls),
            "method": "Native full-range BT709 weighted luma SSIM >= .97 and original RGB MAE <= 5; each same-clock superseded-stock control must reject.",
            "interpretation": "Separate structural/source-correspondence result. 4:2:0 chroma conversion changes fine saturated RGB edges; even lossless yuv420 round-trip can fail a full-RGB .97 comparison. Luma preserves the structure comparison while unchanged RGB MAE bounds color error. This does not override the original RGB passed result."
        }
        report["passed"] = report["binding"]["passed"] and negative["rejected"]
    except Exception as exc:
        report["error"] = str(exc)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"passed": report["passed"], "report": str(args.report.resolve()), "error": report.get("error")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
