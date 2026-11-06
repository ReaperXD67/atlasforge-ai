"""Compile, mix, build and optionally verify a new cinematic video delivery.

No stage publishes or schedules content. Rendering is opt-in and always uses a
fresh temporary MP4, so an older export cannot be mistaken for a successful run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import wave
from datetime import UTC, datetime
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import unquote, urlsplit

import portalocker

from daily_video_factory.cinematic_audio import mix_project_audio
from daily_video_factory.edit_plan import compile_project_edit_plan, validate_edit_plan_bundle

REPOSITORY = Path(__file__).resolve().parents[1]
REQUIRED_BUILD_FILES = {
    "index.html", "cinematic.css", "cinematic.js", "DIRECTION.json",
    "EDIT_PLAN.compiled.json", "AUDIO_MIX.json", "assets/vendor/cinematic_primitives.js",
    "assets/vendor/gsap.min.js",
}


class CinematicRunError(ValueError):
    """A stage failed, or its output is not a fresh verified delivery."""


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local(project: Path, name: str, *, exists: bool = True) -> Path:
    if (not name or "\\" in name or ":" in name or "\x00" in name
            or PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
            or ".." in PurePosixPath(name).parts):
        raise CinematicRunError("Use a project-relative path without parent traversal")
    target = (project / name).resolve()
    if not target.is_relative_to(project) or (exists and not target.is_file()):
        raise CinematicRunError(f"Missing or escaping project file: {name}")
    return target


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise CinematicRunError(f"Expected an object in {path.name}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class _References(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and (name in {"src", "poster", "data-composition-src"}
                          or (tag == "link" and name == "href")):
                self.references.append(value)


def _runtime_files(project: Path, start: str = "index.html") -> set[str]:
    """Include local HTML/CSS dependencies, including fonts omitted by a builder receipt."""
    pending = [start]
    found: set[str] = set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        file = _local(project, name)
        found.add(name)
        refs: list[str] = []
        if file.suffix.lower() in {".html", ".htm"}:
            parser = _References()
            parser.feed(file.read_text(encoding="utf-8"))
            refs = parser.references
        elif file.suffix.lower() == ".css":
            refs = re.findall(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", file.read_text(encoding="utf-8"))
        for reference in refs:
            if unquote(reference).startswith(("data:", "#")):
                continue
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc or parsed.query:
                raise CinematicRunError("Runtime media must be local and have no query string")
            relative = (Path(name).parent / unquote(parsed.path)).as_posix()
            _local(project, relative)
            pending.append(relative)
    return found


def verify_project_sources(project: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate edit, mix and build receipts and return every current runtime hash."""
    project = project.resolve()
    validate_edit_plan_bundle(project / "EDIT_PLAN.json")
    compiled = _read(project / "EDIT_PLAN.compiled.json")
    if compiled["fps"] != 30 or not 20 <= compiled["duration_seconds"] <= 60:
        raise CinematicRunError("This delivery workflow requires 30 fps and 20–60 seconds")
    direction = _read(project / "DIRECTION.json")
    master_name = direction.get("audio_master", "assets/audio/master.wav")
    master = _local(project, master_name)
    mix = _read(project / "AUDIO_MIX.json")
    if mix.get("compiled_plan_sha256") != _hash(project / "EDIT_PLAN.compiled.json"):
        raise CinematicRunError("Audio mix belongs to a different edit plan")
    if mix.get("master_sha256") != _hash(master):
        raise CinematicRunError("Audio master changed after mixing")
    with wave.open(str(master), "rb") as wav:
        rate, channels, samples = wav.getframerate(), wav.getnchannels(), wav.getnframes()
    expected_samples = round(compiled["duration_seconds"] * 48000)
    if rate != 48000 or channels != 2 or abs(samples - expected_samples) > 2:
        raise CinematicRunError("Audio master format/duration differs from the compiled film")
    if mix.get("samples") != samples or mix.get("sample_rate") != rate or mix.get("channels") != channels:
        raise CinematicRunError("Audio mix receipt does not describe the current WAV")
    build = _read(project / "CINEMATIC_BUILD.json")
    if any(build.get(key) != compiled[key] for key in ("project_id", "duration_frames", "fps")):
        raise CinematicRunError("Build receipt belongs to a different film")
    files = build.get("files")
    if not isinstance(files, dict) or not REQUIRED_BUILD_FILES.union({master_name}).issubset(files):
        raise CinematicRunError("Build receipt omits required composition sources")
    for name, digest in files.items():
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CinematicRunError("Build receipt contains an invalid fingerprint")
        if _hash(_local(project, name)) != digest:
            raise CinematicRunError(f"Build source changed: {name}")
    authored = _read(project / "EDIT_PLAN.json")
    names = set(files) | _runtime_files(project) | set(compiled["provenance"]["asset_sha256"])
    names |= {"EDIT_PLAN.json", "EDIT_PLAN.compiled.js", "EDIT_PLAN.audit.json", "CINEMATIC_BUILD.json",
              authored.get("timing_file", "timing.json"), "package.json", "hyperframes.json"}
    snapshot = {name: _hash(_local(project, name)) for name in sorted(names)}
    return compiled, snapshot


def assert_sources_unchanged(project: Path, before: dict[str, str]) -> None:
    _, after = verify_project_sources(project)
    if before != after:
        changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
        raise CinematicRunError("Sources changed during verification/render: " + ", ".join(changed[:5]))


def _tool(name: str) -> str:
    result = shutil.which(name)
    if not result:
        raise CinematicRunError(f"Required executable is unavailable: {name}")
    return result


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PRODUCER_BROWSER_GPU_MODE"] = "software"
    env["PRODUCER_LOW_MEMORY_MODE"] = "1"
    if os.name == "nt":
        for base in ("C:/Program Files", "C:/Program Files (x86)"):
            chrome = Path(base) / "Google/Chrome/Application/chrome.exe"
            if chrome.is_file():
                env["PRODUCER_HEADLESS_SHELL_PATH"] = str(chrome)
                env["HYPERFRAMES_BROWSER_PATH"] = str(chrome)
                break
    return env


def run_command(args: list[str], *, cwd: Path, log: Path, timeout: int = 10800) -> None:
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                env=_environment(), timeout=timeout, check=False)
    if result.returncode:
        raise CinematicRunError(f"Command failed with exit {result.returncode}; see {log.name}")


def _check_command(project: Path) -> list[str]:
    package = (project / "package.json").read_text(encoding="utf-8")
    found = re.search(r"hyperframes@(\d+\.\d+\.\d+)", package)
    if not found:
        raise CinematicRunError("Project package.json must pin a HyperFrames version")
    node = _tool("node")
    if os.name == "nt":
        launcher = Path(node).parent / "node_modules/npm/bin/npx-cli.js"
        if not launcher.is_file():
            raise CinematicRunError("Cannot locate npm's npx JavaScript launcher beside Node")
        prefix = [node, str(launcher)]
    else:
        prefix = [_tool("npx")]
    return [*prefix, "--yes", f"hyperframes@{found.group(1)}", "check", ".", "--samples", "17",
            "--snapshots", "--timeout", "120000", "--no-browser-gpu"]


def render_command(project: Path, temporary_output: Path) -> list[str]:
    if os.name != "nt":
        raise CinematicRunError("The existing software-render wrapper requires Windows")
    return [_tool("pwsh"), "-NoProfile", "-NonInteractive", "-File",
            str(REPOSITORY / "scripts/render_hyperframes_windows.ps1"), "-Project", str(project),
            "-Output", str(temporary_output), "-Quality", "delivery", "-MinDuration", "20",
            "-MaxDuration", "60", "-CheckFirst", "-CheckSamples", "17"]


def verify_rendered_media(video: Path, plan: dict[str, Any], *, min_seconds: float = 20,
                          max_seconds: float = 60) -> dict[str, Any]:
    """Probe real streams, count decoded video frames, then decode both streams completely."""
    if not video.is_file() or not video.stat().st_size:
        raise CinematicRunError("Renderer did not produce a nonempty MP4")
    probe = subprocess.run([_tool("ffprobe"), "-v", "error", "-count_frames", "-show_streams",
                            "-show_format", "-of", "json", str(video)], capture_output=True,
                           text=True, timeout=600, check=False)
    if probe.returncode:
        raise CinematicRunError("ffprobe could not read the rendered MP4")
    data = json.loads(probe.stdout)
    streams = data.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) != 1 or len(streams) != 2:
        raise CinematicRunError("Delivery needs exactly one video and one audio stream")
    v, a = videos[0], audios[0]
    duration = float(data["format"]["duration"])
    frames = int(v.get("nb_read_frames", "0"))
    rate = Fraction(v.get("avg_frame_rate", "0/1"))
    nominal = Fraction(v.get("r_frame_rate", "0/1"))
    if (v.get("codec_name") != "h264" or v.get("pix_fmt") != "yuv420p"
            or v.get("width") != plan["width"] or v.get("height") != plan["height"]
            or rate != plan["fps"] or nominal != plan["fps"] or frames != plan["duration_frames"]):
        raise CinematicRunError("Rendered video codec, dimensions, frame rate or decoded frame count is wrong")
    if a.get("codec_name") != "aac" or int(a.get("sample_rate", 0)) != 48000 or a.get("channels") != 2:
        raise CinematicRunError("Rendered audio must be AAC stereo at 48 kHz")
    if (not math.isfinite(duration) or not min_seconds <= duration <= max_seconds
            or abs(duration - plan["duration_seconds"]) > 2 / plan["fps"]):
        raise CinematicRunError("Rendered duration differs from the edit or delivery bounds")
    decoded = subprocess.run([_tool("ffmpeg"), "-v", "error", "-xerror", "-err_detect", "explode",
                              "-i", str(video), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
                             capture_output=True, timeout=600, check=False)
    if decoded.returncode:
        raise CinematicRunError("The rendered file failed a full video/audio decode")
    return {"bytes": video.stat().st_size, "sha256": _hash(video), "duration_seconds": duration,
            "decoded_video_frames": frames, "width": v["width"], "height": v["height"],
            "fps": str(rate), "video_codec": "h264", "pixel_format": "yuv420p",
            "audio_codec": "aac", "sample_rate": 48000, "channels": 2,
            "full_video_audio_decode_passed": True}


def run_project(project: Path, *, render: bool = False, check: bool = False,
                check_only: bool = False, output: str = "renders/final.mp4") -> dict[str, Any]:
    project = project.resolve()
    if not project.is_dir():
        raise CinematicRunError("Project directory does not exist")
    if render and check_only:
        raise CinematicRunError("--render cannot be combined with --check-only")
    target = _local(project, output, exists=False)
    if target.suffix.lower() != ".mp4" or not target.relative_to(project).parts[0] == "renders":
        raise CinematicRunError("Delivery output must be a .mp4 inside the project's renders directory")
    renders = project / "renders"
    renders.mkdir(exist_ok=True)
    report_path = project / "CINEMATIC_RUN.json"
    run_id = uuid.uuid4().hex
    logs = renders / f"run-{run_id}"
    report: dict[str, Any] = {"schema_version": 1, "run_id": run_id,
        "started_at": datetime.now(UTC).isoformat(), "status": "running", "stages": [],
        "render_requested": render, "rendered": False, "delivery_verified": False,
        "visual_review_verified": False, "voice_emotion_verified": False, "published": False,
        "mode": "check-only" if check_only else "build", "output": None}
    # This lock serializes this orchestrator; external editors remain covered by fingerprints.
    with portalocker.Lock(str(renders / "cinematic-run.lock"), timeout=0):
        logs.mkdir()
        _write(report_path, report)
        temporary = renders / f".cinematic-{run_id}.mp4"
        stage = "setup"

        def completed(name: str) -> None:
            report["stages"].append({"name": name, "status": "passed"})
            _write(report_path, report)
            print(f"[{name}] passed", flush=True)

        try:
            if not check_only:
                stage = "compile"
                compile_project_edit_plan(project / "EDIT_PLAN.json")
                completed(stage)
                stage = "mix"
                mix_project_audio(project)
                completed(stage)
                stage = "build"
                run_command([_tool("node"), str(REPOSITORY / "scripts/build_cinematic_short.mjs"), str(project)],
                            cwd=REPOSITORY, log=logs / "build.log")
                completed(stage)
            stage = "source-verification"
            plan, snapshot = verify_project_sources(project)
            report["project_id"] = plan["project_id"]
            report["source_files"] = snapshot
            report["authored_shot_count"] = len(plan["shots"])
            report["authored_caption_word_count"] = sum(len(c["words"]) for c in plan["captions"])
            report["review_state"] = _read(project / "DIRECTION.json").get("review_state", "unspecified")
            completed(stage)
            if check and not render:
                stage = "hyperframes-check"
                run_command(_check_command(project), cwd=project, log=logs / "check.log", timeout=1800)
                assert_sources_unchanged(project, snapshot)
                completed(stage)
            if render:
                stage = "render-with-check"
                run_command(render_command(project, temporary), cwd=REPOSITORY, log=logs / "render.log")
                assert_sources_unchanged(project, snapshot)
                completed(stage)
                stage = "media-verification"
                media = verify_rendered_media(temporary, plan)
                assert_sources_unchanged(project, snapshot)
                completed(stage)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, target)
                report.update(rendered=True, delivery_verified=True,
                              output={"file": target.relative_to(project).as_posix(), **media})
            stage = "final-source-verification"
            assert_sources_unchanged(project, snapshot)
            completed(stage)
            report["status"] = "verified_delivery" if render else "sources_verified"
        except BaseException as exc:
            # Keyboard interruption must also invalidate an earlier success report.
            report.update(status="failed", rendered=False, delivery_verified=False, output=None,
                          failed_stage=stage, error_type=type(exc).__name__, error=str(exc)[:1500])
            report["stages"].append({"name": stage, "status": "failed"})
            raise
        finally:
            report["finished_at"] = datetime.now(UTC).isoformat()
            _write(report_path, report)
            _write(logs / "report.json", report)
            if report["delivery_verified"]:
                _write(target.with_suffix(".report.json"), report)
            temporary.unlink(missing_ok=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--render", action="store_true", help="Check and render a fresh MP4, then probe/decode it")
    parser.add_argument("--check", action="store_true", help="Run HyperFrames browser checks (render already includes them)")
    parser.add_argument("--check-only", action="store_true", help="Verify existing edit/mix/build receipts without rebuilding")
    parser.add_argument("--output", default="renders/final.mp4", help="Project-relative .mp4 under renders/")
    args = parser.parse_args(argv)
    try:
        report = run_project(args.project, render=args.render, check=args.check,
                             check_only=args.check_only, output=args.output)
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Cinematic run failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "rendered": report["rendered"],
                      "delivery_verified": report["delivery_verified"], "output": report["output"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
