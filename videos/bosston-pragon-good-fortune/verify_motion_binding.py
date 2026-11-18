"""Sample encoded motion against the selected staged footage and source clock.

Run after the full film exists. This samples one shot per source, tolerates two
staged frames of seeking/rounding error, and models the master's breathing zoom.
It is a sampled source-binding check, not proof of every frame or exact timing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
BAND = "crop=1520:350:200:250,scale=760:175:flags=bilinear"


def run(*args):
    result = subprocess.run(args, capture_output=True, check=True)
    return result.stdout, result.stderr.decode("utf-8", errors="replace")


def sample_shots(plan):
    chosen = {}
    for shot in plan:
        t = round((shot["start"] + shot["end"]) * 15) / 30
        if shot.get("media") == "video" and 6 < t < 174:
            chosen.setdefault(shot["video"], (shot, t))
    return list(chosen.values())


def frames(path, start, count, filters):
    raw, _ = run(
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        f"{start:.9f}",
        "-i",
        str(path),
        "-an",
        "-vf",
        filters,
        "-frames:v",
        str(count),
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "-",
    )
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 175, 760, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "renders/Cinematic-motion-binding.json"
    )
    args = parser.parse_args()
    plan_path = ROOT / "scene-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    samples = sample_shots(plan)
    assert len(samples) >= 8, "Expected at least eight distinct motion sources."
    directory = args.report.parent / "motion-binding"
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    for shot, t in samples:
        progress = (t - shot["start"]) / (shot["end"] - shot["start"])
        zoom = 1.008 + progress * 0.014
        source_time = shot["source_at"] + (t - shot["start"]) * shot["rate"]
        first = max(0, round(source_time * 30) - 2)
        width, height = round(1920 * zoom / 2) * 2, round(1080 * zoom / 2) * 2
        expected_filter = (
            f"scale={width}:{height}:flags=bilinear,crop=1920:1080:(iw-1920)/2:(ih-1080)/2,{BAND}"
        )
        actual = frames(args.video, t, 1, BAND)[0]
        expected_frames = frames(ROOT / shot["src"], first / 30, 5, expected_filter)
        actual_path = directory / f"{shot['id']}-encoded.png"
        Image.fromarray(actual).save(actual_path)
        comparisons = []
        for index, expected in enumerate(expected_frames):
            expected_path = directory / f"{shot['id']}-expected-{index}.png"
            Image.fromarray(expected).save(expected_path)
            _, log = run(
                "ffmpeg",
                "-hide_banner",
                "-v",
                "info",
                "-i",
                str(actual_path),
                "-i",
                str(expected_path),
                "-lavfi",
                "ssim",
                "-f",
                "null",
                "-",
            )
            found = re.search(r"All:([0-9.]+)", log)
            assert found, "FFmpeg did not report SSIM."
            delta = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
            foreground = np.maximum(actual.mean(axis=2), expected.mean(axis=2)) > 40
            comparisons.append(
                {
                    "source_time": (first + index) / 30,
                    "ssim": float(found[1]),
                    "mae_rgb_0_255": float(delta.mean()),
                    "foreground_mae_0_255": float(delta[foreground].mean())
                    if foreground.any()
                    else 0,
                    "expected_crop": str(expected_path.resolve()),
                }
            )
        best = max(comparisons, key=lambda c: c["ssim"])
        passed = (
            best["ssim"] >= 0.70
            and best["mae_rgb_0_255"] <= 35
            and best["foreground_mae_0_255"] <= 45
        )
        results.append(
            {
                "shot": shot["id"],
                "source": shot["video"],
                "encoded_time": t,
                "expected_source_time": source_time,
                "zoom": zoom,
                "passed": passed,
                "encoded_crop": str(actual_path.resolve()),
                "best": best,
                "candidates": comparisons,
            }
        )
        print(
            f"{shot['id']} {shot['video']}: SSIM {best['ssim']:.4f}, MAE {best['mae_rgb_0_255']:.2f}, passed={passed}",
            flush=True,
        )
    report = {
        "passed": all(r["passed"] for r in results),
        "sample_count": len(results),
        "samples": results,
        "method": "One central-band sample per source, CSS centered breathing zoom, +/-2 staged-frame search, native FFmpeg SSIM and RGB MAE.",
        "limits": "Sampled source-binding check only. Similar backgrounds can match at nearby times; this does not prove every frame or exact temporal equivalence.",
        "thresholds": {"minimum_ssim": 0.70, "maximum_rgb_mae": 35, "maximum_foreground_mae": 45},
        "scene_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
