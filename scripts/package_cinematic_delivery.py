"""Package a current verified cinematic export; never render, regenerate or publish."""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import portalocker

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID = "biznex-second-question"
DEFAULT_PROJECT = ROOT / "videos" / PROJECT_ID
_SPEC = importlib.util.spec_from_file_location("cinematic_delivery_runner", ROOT / "scripts/run_cinematic_project.py")
assert _SPEC is not None and _SPEC.loader is not None
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)

PROVENANCE = (
    "VISUAL_PROVENANCE.json", "MOTION_PROVENANCE.json", "AUDIO_MIX.json", "VOICE_DELIVERY.json",
    "DELIVERY_REVIEW.json",
    "assets/audio/MUSIC_PROVENANCE.json", "assets/audio/FOLEY_PROVENANCE.json",
    "assets/audio/narration.performance.json", "assets/audio/narration.direction-report.json",
    "assets/audio/narration.asr-evidence.json", "assets/audio/narration.caption-verification.json",
)
SUPPORT = (
    "scripts/run_cinematic_project.py", "scripts/build_cinematic_short.mjs",
    "scripts/compile_edit_plan.py", "scripts/mix_cinematic_audio.py",
    "scripts/render_hyperframes_windows.ps1", "scripts/lib/cinematic_primitives.js",
    "scripts/lib/cinematic_build.mjs",
    "scripts/templates/cinematic/cinematic.css", "scripts/templates/cinematic/cinematic.js",
    "src/daily_video_factory/__init__.py", "src/daily_video_factory/edit_plan.py",
    "src/daily_video_factory/cinematic_audio.py", "src/daily_video_factory/expressive_voice.py",
    "scripts/expressive_voice_worker.py", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "docs/CINEMATIC_PROJECT_WORKFLOW.md", "docs/CINEMATIC_EDIT_PLANS.md",
    "docs/CINEMATIC_ACCEPTANCE.md", "docs/CINEMATIC_DELIVERY.md",
    "docs/EXPRESSIVE_VOICE.md", "docs/VOICE_DIRECTION.md",
    "docs/licenses/HYPERFRAMES-APACHE-2.0.txt",
    "docs/assets/readme/second-question-poster.jpg",
    "config/editing/edit-plan.schema.json", "config/editing/second-question.example.json",
)
TEXT_SUFFIXES = {".json", ".md", ".txt", ".py", ".ps1", ".js", ".css", ".html"}
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+|/Users/|/home/)[^\s\"'<>]+", re.I)
SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"[\"'](?:access_token|refresh_token|client_secret|password)[\"']\s*:\s*[\"'][^\"']+[\"']|"
    r"\bsk-[A-Za-z0-9_-]{20,}|(?:X-Amz-Signature|X-Goog-Signature|access_token)=[^\s&\"']+",
    re.I,
)


class PackageError(ValueError):
    pass


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def local(base: Path, name: str) -> Path:
    parts = Path(name).parts
    if any(part.lower() in {".git", ".env", ".venv", "secrets", "node_modules", "models"} for part in parts):
        raise PackageError("An export input names a private or unneeded runtime directory.")
    return runner._local(base.resolve(), name)


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+(?:['’]\w+)*", text.replace("’", "'").lower())


def _seconds(text: str) -> float:
    h, m, s, ms = (int(value) for value in re.split(r"[:,]", text))
    if m >= 60 or s >= 60:
        raise PackageError("Invalid caption timestamp.")
    return h * 3600 + m * 60 + s + ms / 1000


def verify_captions(project: Path, plan: dict[str, Any]) -> Path:
    authored = read_json(local(project, "EDIT_PLAN.json"))
    if authored.get("timing_file") != "timing.json":
        raise PackageError("Select the canonical expressive timing.json before packaging.")
    timing = read_json(local(project, "timing.json"))
    if timing.get("voice_variant") != "expressive":
        raise PackageError("This delivery requires the selected expressive voice, not development timing.")
    srt = local(project, "assets/audio/narration.srt")
    cues = []
    for block in re.split(r"\n\s*\n", srt.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        match = re.fullmatch(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", lines[1] if len(lines) > 2 else "")
        if not match or not lines[0].isdigit():
            raise PackageError("The complete canonical SRT is malformed.")
        cues.append({"start": _seconds(match[1]), "end": _seconds(match[2]), "text": " ".join(lines[2:])})
    expected = timing.get("captions", [])
    script = _tokens(local(project, "script.txt").read_text(encoding="utf-8"))
    if (not script or _tokens(" ".join(c["text"] for c in cues)) != script
            or _tokens(" ".join(w["text"] for w in timing.get("words", []))) != script
            or len(cues) != len(expected)):
        raise PackageError("SRT, selected timing and approved script do not contain the same complete words.")
    previous = 0.0
    for cue, anchor in zip(cues, expected, strict=True):
        if (not 0 <= cue["start"] < cue["end"] <= plan["duration_seconds"] + 0.002
                or cue["start"] < previous - 0.002 or _tokens(cue["text"]) != _tokens(anchor["text"])
                or abs(cue["start"] - anchor["start"]) > 0.002
                or abs(cue["end"] - anchor["end"]) > 0.002):
            raise PackageError("SRT timing differs from the selected expressive caption evidence.")
        previous = cue["end"]
    voice = local(project, "assets/audio/narration.wav")
    voice_rows = [row for row in read_json(local(project, "AUDIO_MIX.json")).get("sources", []) if row.get("role") == "voice"]
    if len(voice_rows) != 1 or voice_rows[0].get("sha256") != runner._hash(voice):
        raise PackageError("Canonical narration is not the exact voice used by the verified mix.")
    return srt


def verify_delivery(project: Path) -> dict[str, Any]:
    report_path = project / "renders/final.report.json"
    if not report_path.is_file():
        raise PackageError("Not ready: renders/final.report.json is missing; render and verify the final first.")
    report = read_json(report_path)
    if (report.get("schema_version") != 1 or report.get("project_id") != PROJECT_ID
            or report.get("status") != "verified_delivery" or report.get("rendered") is not True
            or report.get("delivery_verified") is not True):
        raise PackageError("Not ready: the final sidecar does not record a verified delivery.")
    stages = {item.get("name") for item in report.get("stages", []) if item.get("status") == "passed"}
    if not {"render-with-check", "media-verification", "final-source-verification"}.issubset(stages):
        raise PackageError("The delivery report omits required completed checks.")
    plan, snapshot = runner.verify_project_sources(project)
    if plan.get("project_id") != PROJECT_ID or snapshot != report.get("source_files"):
        raise PackageError("Current project sources differ from the final render report.")
    if report.get("output", {}).get("file") != "renders/final.mp4":
        raise PackageError("The report does not describe the expected final.mp4.")
    video = local(project, "renders/final.mp4")
    if runner._hash(video) != report["output"].get("sha256"):
        raise PackageError("Final video bytes differ from the verified report.")
    media = runner.verify_rendered_media(video, plan)
    if any(report["output"].get(key) != value for key, value in media.items()):
        raise PackageError("Current video properties differ from the final render report.")
    captions = verify_captions(project, plan)
    return {"report": report, "report_sha256": runner._hash(report_path), "snapshot": snapshot,
            "media": media, "captions": captions, "plan": plan}


def export_text(source: Path, *, exact: bool) -> tuple[bytes, bool]:
    data = source.read_bytes()
    if source.suffix.lower() not in TEXT_SUFFIXES and source.name != "LICENSE":
        return data, False
    text = data.decode("utf-8-sig")
    if SECRET.search(text):
        raise PackageError("Potential credential or signed URL in an export input; nothing was packaged.")
    if not PRIVATE_PATH.search(text):
        return data, False
    if exact:
        raise PackageError("A fingerprinted runtime input contains a private absolute path; make it portable and rerender.")
    return PRIVATE_PATH.sub("[local-path-omitted]", text).encode("utf-8"), True


def inputs(project: Path, root: Path, verified: dict[str, Any], include_source: bool) -> dict[str, tuple[Path, bool]]:
    result = {"final.mp4": (local(project, "renders/final.mp4"), True),
              "thumbnail.jpg": (local(root, "docs/assets/readme/second-question-poster.jpg"), True),
              "captions.srt": (verified["captions"], True),
              "UPLOAD_COPY.md": (local(project, "UPLOAD_COPY.md"), False),
              "transcript.txt": (local(project, "script.txt"), True),
              "provenance/final.report.json": (local(project, "renders/final.report.json"), True),
              "provenance/timing.json": (local(project, "timing.json"), True)}
    if (project / "REVIEW.md").is_file():
        result["REVIEW.md"] = (local(project, "REVIEW.md"), False)
    for name in PROVENANCE:
        result[f"provenance/{Path(name).name}"] = (local(project, name), name in verified["snapshot"])
    for name in ("assets/audio/voice-reference.provenance.json", "assets/audio/voice-reference.license.json"):
        if (project / name).is_file():
            result[f"provenance/{Path(name).name}"] = (local(project, name), False)
    audition = project / "assets/audio/audition"
    if not (audition / "ab-comparison.wav").is_file():
        audition = root / "output/expressive-voice/af-heart-audition"
    if (audition / "ab-comparison.wav").is_file():
        for name in ("ab-comparison.wav", "ab-comparison-order.json", "audition-report.json", "audition-independent-evidence.json"):
            result[f"voice-comparison/{name}"] = (local(audition, name), False)
    if not include_source:
        return result
    names = set(verified["snapshot"]) | set(PROVENANCE) | {
        "README.md", "BRIEF.md", "SPEC.md", "STORYLINES.md", "PROMPTS.md", "script.txt",
        "create_edit.py", "UPLOAD_COPY.md", "assets/audio/narration.srt",
        "assets/audio/narration.wav", "assets/audio/voice-reference.wav",
        "assets/fonts/Montserrat-OFL.txt", "assets/audio/KENNEY-LICENSE.txt",
    }
    for asset in read_json(local(project, "VISUAL_PROVENANCE.json")).get("assets", []):
        names.add(asset["path"])
    names |= {path.relative_to(project).as_posix() for path in (project / "assets/audio").glob("voice-reference*.json")}
    prefix = f"sources/videos/{PROJECT_ID}"
    if (project / "REVIEW.md").is_file():
        names.add("REVIEW.md")
    for name in sorted(names):
        if "baseline" in name.lower() or "download" in Path(name).stem.lower():
            raise PackageError("The selected runtime still requires a baseline or duplicate download asset.")
        result[f"{prefix}/{name}"] = (local(project, name), name in verified["snapshot"])
    for name in SUPPORT:
        result[f"sources/{name}"] = (local(root, name), True)
    for source in (root / "config/expressive-voice").glob("*"):
        if source.is_file() and source.name != "af-heart-audition.json" and source.suffix in {".json", ".txt"}:
            name = source.relative_to(root).as_posix()
            result[f"sources/{name}"] = (local(root, name), True)
    return result


def _zip(directory: Path, archive: Path) -> None:
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            entry = zipfile.ZipInfo(path.relative_to(directory).as_posix(), (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            with path.open("rb") as incoming, bundle.open(entry, "w", force_zip64=True) as outgoing:
                shutil.copyfileobj(incoming, outgoing)


def package_delivery(project: Path = DEFAULT_PROJECT, *, root: Path = ROOT,
                     include_source: bool = False, check_only: bool = False) -> dict[str, Any]:
    root, project = root.resolve(), project.resolve()
    if not project.is_relative_to(root) or not project.is_dir():
        raise PackageError("Project must be inside the current repository.")
    if not (project / "renders/final.report.json").is_file():
        raise PackageError("Not ready: render and verify the final expressive film first.")
    with portalocker.Lock(str(project / "renders/cinematic-run.lock"), timeout=0):
        verified = verify_delivery(project)
        selected = inputs(project, root, verified, include_source)
        fingerprints = {name: runner._hash(source) for name, (source, _) in selected.items()}
        for source, exact in selected.values():
            export_text(source, exact=exact)
        if check_only:
            return {"status": "ready", "video_sha256": verified["media"]["sha256"],
                    "files_selected": len(selected), "includes_project_source": include_source,
                    "packaged": False, "published": False}
        parent = (root / "output/deliveries").resolve()
        if not parent.is_relative_to(root / "output"):
            raise PackageError("Export directory escapes repository output.")
        parent.mkdir(parents=True, exist_ok=True)
        destination, archive = parent / PROJECT_ID, parent / f"{PROJECT_ID}.zip"
        if destination.exists() or archive.exists():
            raise PackageError("Delivery exists; preserve or move it before a new export.")
        with tempfile.TemporaryDirectory(prefix=".cinematic-package-", dir=parent) as temporary:
            stage = Path(temporary) / PROJECT_ID
            stage.mkdir()
            records = []
            for name, (source, exact) in selected.items():
                data, sanitized = export_text(source, exact=exact)
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                records.append({"path": name, "bytes": len(data), "sha256": runner._hash(target),
                                "source_sha256": fingerprints[name], "private_paths_redacted": sanitized})
            (stage / "README.md").write_text(
                "# The Second Question — BizNex\n\n"
                "Verified local cinematic export with complete speech-aligned captions. Read UPLOAD_COPY.md "
                "for platform copy, fictional/AI disclosure and required credits. No publication is performed.\n\n"
                "Music: 'Hiraeth' by Scott Buckley, CC BY 4.0. https://www.scottbuckley.com.au/library/hiraeth/ "
                "License: https://creativecommons.org/licenses/by/4.0/ . Edited excerpt, fades and ducking. "
                "Kenney interface sounds and Ylmir rain: CC0; see provenance. Generated visuals and synthetic voice.\n\n"
                "voice-comparison/ contains an optional audition, not the final film narration. Its order JSON "
                "identifies neutral and directed takes. ASR/numerical evidence does not certify emotional fidelity.\n\n"
                "DELIVERY_MANIFEST.json and SHA256SUMS.txt record this export. Provenance private machine paths "
                "may be redacted in copies; immutable runtime inputs are preserved exactly.\n" +
                ("\nThe sources/ folder rebuilds from prepared local assets; see sources/REBUILD.md. "
                 "It excludes model weights, environments, baseline audio, caches and duplicate downloads.\n" if include_source else ""),
                encoding="utf-8")
            if include_source:
                requirements = "\n".join(f"{name}=={importlib.metadata.version(name)}" for name in
                                         ("numpy", "pydantic", "portalocker", "imageio-ffmpeg")) + "\n"
                (stage / "sources/requirements-rebuild.txt").write_text(requirements, encoding="utf-8")
                (stage / "sources/REBUILD.md").write_text(
                    "# Rebuild from prepared assets\n\nUse Python 3.11/3.12, Node/npm, FFmpeg/ffprobe, "
                    "PowerShell7 and Chrome. Run inside this sources/ directory on Windows.\n\n"
                    "```powershell\npython -m venv .venv\n.venv/Scripts/python.exe -m pip install -r requirements-rebuild.txt\n"
                    "$env:PYTHONPATH = (Join-Path (Get-Location) 'src')\n"
                    ".venv/Scripts/python.exe scripts/run_cinematic_project.py videos/biznex-second-question --check-only\n"
                    ".venv/Scripts/python.exe scripts/run_cinematic_project.py videos/biznex-second-question --render\n```\n\n"
                    "The first check preserves authored bytes; render recompiles/mixes/builds the prepared assets. "
                    "HyperFrames is version-pinned; npm may fetch that CLI. No model download, voice regeneration or "
                    "account access is required to render. Review the resulting film; exact encoded bytes may differ "
                    "with software/hardware versions. Source hashes describe the supplied prepared film.\n\n"
                    "The optional voice reference and model lock/provenance support a separately installed voice "
                    "runtime; that environment and weights are not included. See docs/EXPRESSIVE_VOICE.md. "
                    "Do not run a baseline command from historical development notes. Preserve all credits and licenses.\n",
                    encoding="utf-8")
            runner.assert_sources_unchanged(project, verified["snapshot"])
            if runner._hash(project / "renders/final.report.json") != verified["report_sha256"]:
                raise PackageError("Final report changed during packaging.")
            if any(runner._hash(source) != fingerprints[name] for name, (source, _) in selected.items()):
                raise PackageError("An input changed during packaging; no export was installed.")
            manifest = {"schema_version": 1, "project_id": PROJECT_ID, "status": "verified_export",
                        "media": verified["media"], "render_report_sha256": verified["report_sha256"],
                        "source_files": verified["snapshot"], "files": records,
                        "includes_project_source": include_source, "published_by_packager": False,
                        "visual_review_verified": False, "voice_emotion_verified": False}
            (stage / "DELIVERY_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            hashes = [f"{runner._hash(p)}  {p.relative_to(stage).as_posix()}" for p in sorted(stage.rglob("*")) if p.is_file()]
            (stage / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
            temporary_zip = Path(temporary) / archive.name
            _zip(stage, temporary_zip)
            stage.rename(destination)
            temporary_zip.rename(archive)
        digest = runner._hash(archive)
        archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        return {"status": "packaged", "archive": str(archive), "sha256": digest,
                "bytes": archive.stat().st_size, "includes_project_source": include_source, "published": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--project-source", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate readiness without creating an export.")
    args = parser.parse_args()
    try:
        result = package_delivery(args.project, include_source=args.project_source, check_only=args.check)
    except PackageError as exc:
        print(json.dumps({"status": "not_ready", "packaged": False, "reason": str(exc)}), file=sys.stderr)
        return 2
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, portalocker.exceptions.LockException):
        print(json.dumps({"status": "not_ready", "packaged": False,
                          "reason": "Current source, caption, media or export checks failed; no delivery was approved."}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
