"""Prepare or run a pinned, isolated two-second Windows capture comparison.

Preparation starts no browser. Run only after the production render has finished::

    python videos/bosston-pragon-good-fortune/benchmark_capture.py --warm-packages
    python videos/bosston-pragon-good-fortune/benchmark_capture.py --run

Outputs stay under output/bosston-capture-benchmark; production files are read only.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SOURCE = Path(__file__).resolve().parent
WORKSPACE = SOURCE.parent.parent
DEFAULT_OUTPUT = WORKSPACE / "output/bosston-capture-benchmark"
VERSIONS = (("baseline", "0.8.152", False), ("candidate", "0.9.65", True))
OFFSET, DURATION, FPS = 2.0, 2.0, 30
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(*args: str, timeout: int = 600, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: " + result.stderr.decode("utf-8", errors="replace")[-1600:])
    return result


def npx() -> str:
    executable = shutil.which("npx.cmd" if os.name == "nt" else "npx")
    require(executable is not None, "npx is not on PATH")
    return str(executable)


def write_new_or_identical(path: Path, content: str) -> None:
    """Never replace a previously prepared fixture with different bytes."""
    if path.exists():
        require(path.read_text(encoding="utf-8") == content,
                f"Existing fixture differs: {path}. Choose a fresh --output directory.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def stage_asset(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        require(digest(source) == digest(destination), f"Staged asset differs: {destination}")
        return "existing-identical"
    # Only immutable image/font/library inputs are hardlinked. No staged composition
    # or script shares writable bytes with production. Never chmod a hardlinked file.
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def staged_html(original: str, selected: list[dict[str, Any]]) -> str:
    original = re.sub(r'<div\b[^>]*\bid="lyric-\d+"[^>]*>.*?</div>\s*', "", original)
    original = re.sub(r'<audio\b[^>]*>.*?</audio>\s*', "", original, flags=re.DOTALL)
    original = original.replace('data-duration="185"', 'data-duration="2"', 1)
    for title_id in ("opening-title", "closing-title"):
        pattern = rf'(<div\b[^>]*\bid="{title_id}"[^>]*>)'

        def shift_title(match: re.Match[str]) -> str:
            tag = re.sub(r'data-start="[^"]*"', 'data-start="0"', match[0])
            return re.sub(r'data-duration="[^"]*"', 'data-duration="2"', tag)

        original, count = re.subn(pattern, shift_title, original)
        require(count == 1, f"Expected the production {title_id} element")
    cues = []
    for index, cue in enumerate(selected):
        start, end = max(0.0, cue["start"] - OFFSET), min(DURATION, cue["end"] - OFFSET)
        cues.append(f'<div id="lyric-{index:03}" class="clip lyric" data-start="{start:.6f}" '
                    f'data-duration="{end - start:.6f}" data-track-index="8" '
                    'data-track-kind="captions"><span class="lyric-inner">'
                    f'{html.escape(cue["text"])}</span></div>')
    require('<div class="matte top"' in original, "Production matte anchor changed")
    original = original.replace('<div class="matte top"', "\n".join(cues) + '\n<div class="matte top"', 1)
    original = original.replace('<script src="cinema.js">',
                                f'<script>window.BOSSTON_TIME_OFFSET={OFFSET};</script>\n'
                                '<script src="cinema.js">', 1)
    original, count = re.subn(r'tl\.to\(clock,\{time:185,duration:185,',
                              'tl.to(clock,{time:2,duration:2,', original)
    require(count == 1, "Production GSAP clock changed")
    original = original.replace('window.renderLyricsAt(clock.time);',
                                f'window.renderLyricsAt(clock.time+{OFFSET});')
    original = original.replace('window.renderLyricsAt(0);', f'window.renderLyricsAt({OFFSET});')
    original = original.replace("<title>", "<title>Isolated capture benchmark — ", 1)
    require('data-duration="185"' not in original, "A full-song clip remains in benchmark HTML")
    return original


def prepare(output: Path, warm_packages: bool) -> dict[str, Any]:
    fixture = output / "fixture"
    fixture.mkdir(parents=True, exist_ok=True)
    original = (SOURCE / "index.html").read_text(encoding="utf-8")
    data = json.loads((SOURCE / "film-data.js").read_text(encoding="utf-8")
                      .partition("=")[2].strip().removesuffix(";"))
    selected = [cue for cue in data["captions"] if cue["start"] < OFFSET + DURATION and cue["end"] > OFFSET]
    require(bool(selected), "Chosen production range has no lyric entrance")
    data["captions"] = selected
    source_hashes = {name: digest(SOURCE / name)
                     for name in ("index.html", "cinema.js", "captions.js", "film-data.js")}
    for name in ("cinema.js", "captions.js"):
        write_new_or_identical(fixture / name, (SOURCE / name).read_text(encoding="utf-8"))
    write_new_or_identical(fixture / "index.html", staged_html(original, selected))
    write_new_or_identical(fixture / "film-data.js", "window.FILM_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
    config = {"authoringSkill": "music-to-video", "paths": {"assets": "assets", "blocks": "compositions"}}
    write_new_or_identical(fixture / "hyperframes.json", json.dumps(config, indent=2) + "\n")
    write_new_or_identical(fixture / "package.json", '{"private":true,"type":"module"}\n')
    inputs = [SOURCE / "assets/gsap.min.js"]
    inputs.extend(p for p in (SOURCE / "assets/generated").rglob("*") if p.is_file())
    inputs.extend(p for p in (SOURCE / "assets/fonts").rglob("*") if p.is_file())
    assets = []
    for source in sorted(inputs):
        relative = source.relative_to(SOURCE)
        method = stage_asset(source, fixture / relative)
        assets.append({"file": relative.as_posix(), "sha256": digest(source), "staging": method})
    fixture_hashes = {p.relative_to(fixture).as_posix(): digest(p) for p in sorted(fixture.rglob("*")) if p.is_file()}
    plan = {
        "prepared_at_utc": datetime.now(UTC).isoformat(), "browser_started": False,
        "source_project": str(SOURCE), "fixture": str(fixture),
        "original_timeline_range": [OFFSET, OFFSET + DURATION], "duration_seconds": DURATION,
        "expected_frames": 60, "canvas": [1920, 1080], "fps": FPS,
        "capture_only": True, "audio": "omitted equally from both variants",
        "selected_captions": [{"text": cue["text"], "start": cue["start"], "end": cue["end"]} for cue in selected],
        "production_source_sha256": source_hashes, "asset_inputs": assets,
        "fixture_sha256": fixture_hashes,
        "variants": [{"name": name, "package": f"hyperframes@{version}", "version": version,
                      "fast_capture_requested": fast, "requested_workers": 1}
                     for name, version, fast in VERSIONS],
        "timing_scope": "CLI invocation including startup, capture and encoding; package warm-up excluded",
        "acceptance": "60 fully decoded 1920x1080 30fps frames, meaningful image and paired visual inspection",
    }
    if warm_packages:
        package_versions = []
        for name, version, _ in VERSIONS:
            begun = time.perf_counter()
            result = command(npx(), "--yes", f"hyperframes@{version}", "--version", cwd=fixture, timeout=600)
            text = (result.stdout + result.stderr).decode("utf-8", errors="replace")
            (output / f"{name}-version.log").write_text(text, encoding="utf-8")
            require(version in text, f"CLI did not report expected version {version}")
            package_versions.append({"requested": f"hyperframes@{version}", "reported_output": text.strip(),
                                     "warmup_seconds": round(time.perf_counter() - begun, 3)})
        plan["package_version_checks"] = package_versions
    write_json(output / "prepared-plan.json", plan)
    print(f"Prepared identical 2s / 60-frame fixture for {OFFSET:g}–{OFFSET + DURATION:g}s. No browser started.\n"
          f"Plan: {output / 'prepared-plan.json'}")
    return plan


def verify_short_video(video: Path, directory: Path) -> dict[str, Any]:
    probe = json.loads(command("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
                               "-of", "json", str(video)).stdout)
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    require((stream["width"], stream["height"]) == (1920, 1080), "Unexpected benchmark resolution")
    require(Fraction(stream["avg_frame_rate"]) == FPS, "Unexpected benchmark frame rate")
    require(int(stream["nb_read_frames"]) == 60, "Benchmark did not decode to exactly 60 frames")
    require(abs(float(probe["format"]["duration"]) - DURATION) <= 1 / FPS, "Unexpected benchmark duration")
    command("ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-")
    frames = []
    for number in (0, 30, 59):
        raw = command("ffmpeg", "-hide_banner", "-v", "error", "-ss", f"{number / FPS:.9f}",
                      "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-").stdout
        frame_path = directory / f"frame-{number:02}.png"
        frame_path.write_bytes(raw)
        with Image.open(io.BytesIO(raw)) as frame:
            pixels = np.asarray(frame.convert("RGB"), dtype=np.float32)
        luma = pixels @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        spatial_std, lit = float(luma.std()), float(np.mean(luma > 12))
        require(spatial_std > 8 and lit > 0.03, f"Benchmark frame {number} looks blank or flat")
        frames.append({"frame": number, "path": str(frame_path), "luma_stddev": round(spatial_std, 4),
                       "fraction_luma_above_12": round(lit, 6)})
    return {"passed": True, "decoded_frames": 60, "width": 1920, "height": 1080, "fps": FPS,
            "duration_seconds": float(probe["format"]["duration"]), "full_decode": "passed",
            "video_codec": stream["codec_name"], "pixel_format": stream["pix_fmt"],
            "video_sha256": digest(video), "size_bytes": video.stat().st_size, "sample_frames": frames}


def backend_evidence(text: str) -> dict[str, Any]:
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).replace("\r", "\n")
    lines = [line.strip() for line in clean.splitlines()
             if re.search(r"draw.?element|screenshot|capture.?mode|capture.?backend|fallback|worker", line, re.I)]
    unique = list(dict.fromkeys(lines))
    # Preserve raw evidence; merely requesting fast capture is not proof it engaged.
    explicit = re.findall(r'''["']?(?:captureMode|captureBackend|capture_mode)["']?\s*[:=]\s*["']?([\w-]+)''', clean)
    return {"explicit_mode_values": list(dict.fromkeys(explicit)), "relevant_log_lines": unique[:60],
            "note": "Inspect logs to confirm the selected route; requested flags alone do not establish it."}


def compare_frames(results: list[dict[str, Any]], directory: Path) -> dict[str, Any]:
    pairs, metrics = [], []
    font = ImageFont.truetype(str(SOURCE / "assets/fonts/NotoSerifCJKsc-Regular.otf"), 22)
    for left, right in zip(results[0]["verification"]["sample_frames"],
                           results[1]["verification"]["sample_frames"], strict=True):
        with Image.open(left["path"]) as a, Image.open(right["path"]) as b:
            first, second = a.convert("RGB"), b.convert("RGB")
            delta = np.asarray(first, dtype=np.float32) - np.asarray(second, dtype=np.float32)
            mse = float(np.mean(delta ** 2))
            metrics.append({"frame": left["frame"], "mean_absolute_rgb_difference": float(np.abs(delta).mean()),
                            "psnr_db": round(10 * math.log10(255 ** 2 / mse), 5) if mse > 0 else None,
                            "pixel_identical": mse == 0})
            pair = Image.new("RGB", (1920, 588), "#101016")
            pair.paste(first.resize((960, 540)), (0, 48))
            pair.paste(second.resize((960, 540)), (960, 48))
            draw = ImageDraw.Draw(pair)
            draw.text((12, 9), f"0.8.152 screenshot — frame {left['frame']}", font=font, fill="white")
            draw.text((972, 9), f"0.9.65 requested fast capture — frame {right['frame']}", font=font, fill="white")
            path = directory / f"comparison-frame-{left['frame']:02}.jpg"
            pair.save(path, quality=95, subsampling=0)
            pairs.append(str(path))
    return {"paired_images": pairs, "metrics": metrics, "human_visual_review": "pending",
            "warning": "Lossy encodes can differ; these metrics alone do not establish visual parity."}


def run_benchmark(output: Path) -> dict[str, Any]:
    plan_path = output / "prepared-plan.json"
    require(plan_path.is_file(), "Run preparation first")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    fixture = Path(plan["fixture"])
    for relative, expected in plan["fixture_sha256"].items():
        require(digest(fixture / relative) == expected, f"Prepared fixture changed: {relative}")
    run_dir = output / "runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S-%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    require(CHROME.is_file(), "Expected installed Chrome executable is missing")
    env.update({"PRODUCER_HEADLESS_SHELL_PATH": str(CHROME), "HYPERFRAMES_BROWSER_PATH": str(CHROME),
                "PRODUCER_LOW_MEMORY_MODE": "0", "PRODUCER_BROWSER_GPU_MODE": "hardware"})
    results = []
    for name, version, fast in VERSIONS:
        variant = run_dir / name
        variant.mkdir()
        for path in fixture.rglob("*"):
            if not path.is_file():
                continue
            target = variant / path.relative_to(fixture)
            if "assets" in path.relative_to(fixture).parts:
                stage_asset(path, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        video = variant / "benchmark.mp4"
        env["PRODUCER_EXPERIMENTAL_FAST_CAPTURE"] = str(fast).lower()
        argv = [npx(), "--yes", f"hyperframes@{version}", "render", ".", "--output", str(video),
                "--quality", "delivery", "--fps", "30", "--workers", "1", "--no-low-memory-mode",
                "--browser-gpu", "--gpu", f"--experimental-fast-capture={str(fast).lower()}"]
        log_path = variant / "render.log"
        begun = time.perf_counter()
        with log_path.open("wb") as log:
            process = subprocess.run(argv, cwd=variant, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     check=False, timeout=600)
        elapsed = time.perf_counter() - begun
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        record = {"name": name, "package": f"hyperframes@{version}", "command": argv,
                  "fast_capture_requested": fast, "requested_workers": 1,
                  "wall_seconds": round(elapsed, 4), "exit_code": process.returncode,
                  "log": str(log_path), "backend": backend_evidence(log_text)}
        if process.returncode == 0 and video.is_file():
            try:
                record["verification"] = verify_short_video(video, variant)
            except (ValueError, RuntimeError, OSError, KeyError) as exc:
                record["verification"] = {"passed": False, "error": str(exc)}
        else:
            record["verification"] = {"passed": False, "error": "CLI failed or export missing"}
        results.append(record)
        write_json(run_dir / "benchmark-results.json", {"plan": plan, "results": results})
        print(f"{name}: exit {process.returncode}, wall {elapsed:.2f}s, verified {record['verification']['passed']}")
    receipt = {"plan": plan, "results": results, "run_directory": str(run_dir),
               "all_outputs_valid": all(r["verification"]["passed"] for r in results),
               "timing_scope": plan["timing_scope"], "production_unchanged": True}
    for name, expected in plan["production_source_sha256"].items():
        if digest(SOURCE / name) != expected:
            receipt["production_unchanged"] = False
    if receipt["all_outputs_valid"]:
        receipt["comparison"] = compare_frames(results, run_dir)
        receipt["candidate_wall_speed_ratio"] = round(results[0]["wall_seconds"] / results[1]["wall_seconds"], 4)
    write_json(run_dir / "benchmark-results.json", receipt)
    write_json(output / "latest-results.json", receipt)
    print(f"Benchmark evidence: {run_dir / 'benchmark-results.json'}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--warm-packages", action="store_true", help="Cache exact npm versions via --version; no browser")
    parser.add_argument("--run", action="store_true", help="Launch browsers; use only after production render finishes")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(WORKSPACE / "output"), "Benchmark output must stay within workspace/output")
    if args.run:
        return 0 if run_benchmark(output)["all_outputs_valid"] else 1
    prepare(output, args.warm_packages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
