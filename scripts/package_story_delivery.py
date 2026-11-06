"""Package a verified new story and its portable prepared sources; no publishing."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import portalocker

from daily_video_factory.story_delivery import load_script, verify_current_render, verify_story_qa
from daily_video_factory.story_pipeline import (
    ROOT,
    PipelineError,
    StoryPipeline,
    local,
    read,
    sha,
    write,
)

PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+|/(?:Users|home)/)[A-Za-z0-9_.-]+[\\/][^\s\"'<>]*")
TEXT = {".json", ".md", ".txt", ".py", ".ps1", ".js", ".mjs", ".css", ".html", ".toml", ".yaml", ".yml", ".srt", ".svg"}


def prepared_code(root: Path, recipe: StoryPipeline) -> set[str]:
    names = {stage.entrypoint for stage in recipe.stages} | {
        "scripts/run_story_pipeline.py", "scripts/render_story_project.py", "scripts/review_story_frames.py",
        "scripts/verify_story_audio.py", "scripts/package_story_delivery.py", "scripts/run_cinematic_project.py",
        "scripts/package_cinematic_delivery.py", "scripts/compile_edit_plan.py", "scripts/mix_cinematic_audio.py",
        "scripts/render_hyperframes_windows.ps1", "scripts/inspect_voice_audition.py", "scripts/expressive_voice_worker.py",
    }
    for folder in ("scripts/lib", "scripts/templates"):
        names.update(p.relative_to(root).as_posix() for p in (root / folder).rglob("*")
                     if p.is_file() and p.suffix in {".js", ".mjs", ".css"})
    pending = list(names)
    while pending:
        name = pending.pop()
        if not name.endswith(".py"):
            continue
        module = name.removeprefix("src/").removesuffix(".py").replace("/", ".")
        package = module.removesuffix(".__init__") if name.endswith("/__init__.py") else module.rpartition(".")[0]
        for node in ast.walk(ast.parse(local(root, name).read_text(encoding="utf-8-sig"))):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = (importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                        if node.level else node.module or "")
                imports = [base, *(base + "." + alias.name for alias in node.names)]
            for imported in imports:
                if not imported.startswith("daily_video_factory"):
                    continue
                stem = "src/" + imported.replace(".", "/")
                candidates = [stem + ".py", stem + "/__init__.py"]
                parts = imported.split(".")
                candidates.extend("src/" + "/".join(parts[:i]) + "/__init__.py" for i in range(1, len(parts)))
                for candidate in candidates:
                    if (root / candidate).is_file() and candidate not in names:
                        names.add(candidate)
                        pending.append(candidate)
    return names


def export_payload(source: Path, *, exact: bool, secret_pattern: re.Pattern[str]) -> tuple[bytes, bool]:
    payload = source.read_bytes()
    if source.suffix.lower() not in TEXT and source.name != "LICENSE":
        if source.suffix.lower() not in {".mp4", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".webp", ".ttf", ".woff", ".woff2"}:
            raise PipelineError("An unsupported source file cannot enter the portable package")
        return payload, False
    text = payload.decode("utf-8-sig")
    if secret_pattern.search(text):
        raise PipelineError("Potential credentials or signed media URL in package input")
    if not PRIVATE_PATH.search(text):
        return payload, False
    if exact:
        raise PipelineError("An exact runtime source contains a private path; repair and rerender it")
    return PRIVATE_PATH.sub("[local-path-omitted]", text).encode("utf-8"), True


def package(project: Path, *, include_source: bool = True) -> dict[str, Any]:
    project = project.resolve()
    if not project.is_relative_to(ROOT / "videos"):
        raise PipelineError("Package a project inside this repository's videos directory")
    helpers = load_script("package_cinematic_delivery.py")
    with portalocker.Lock(str(project / "renders/cinematic-run.lock"), timeout=0):
        verified = verify_current_render(project, decode=True)
        qa = verify_story_qa(project, verified)
        recipe = StoryPipeline.model_validate(read(local(project, "PIPELINE.json")))
        if recipe.project_id != project.name:
            raise PipelineError("Package identity differs from its recipe")
        sources: dict[str, tuple[Path, bool]] = {
            "final.mp4": (verified["video"], True),
            "captions.srt": (local(project, "assets/audio/narration.srt"), True),
            "transcript.txt": (local(project, "script.txt"), True),
            "BRIEF.md": (local(project, recipe.brief), False),
            "UPLOAD_COPY.md": (local(project, "UPLOAD_COPY.md"), False),
            "CREDITS.md": (local(project, "CREDITS.md"), False),
            "provenance/final.report.json": (local(project, "renders/final.report.json"), False),
            "provenance/encoded-audio-verification.json": (local(project, "qa/audio/encoded-audio-verification.json"), False),
            "provenance/asr-evidence.json": (local(project, "qa/audio/audition-independent-evidence.json"), False),
            "provenance/frame-review.json": (local(project, "qa/frames/frame-review.json"), False),
        }
        for name in ("VOICE_DELIVERY.json", "AUDIO_MIX.json", "VISUAL_PROVENANCE.json", "DELIVERY_REVIEW.json",
                     "SOUND_PROVENANCE.json", "THREE_PROVENANCE.json", "brag-plan.md", "composition-brief.md",
                     "assets/audio/MUSIC_PROVENANCE.json", "assets/audio/FOLEY_PROVENANCE.json",
                     "assets/audio/narration.performance.json", "assets/audio/narration.asr-evidence.json",
                     "assets/audio/narration.direction-report.json", "assets/audio/voice-reference.provenance.json"):
            if (project / name).is_file():
                sources["provenance/" + Path(name).name] = (local(project, name), name in verified["snapshot"])
        for name in qa["frames"]["files"]:
            if name.endswith(".jpg"):
                sources["review/" + name] = (local(project, "qa/frames/" + name), True)
        support_hashes: dict[str, str] = {}
        if include_source:
            prefix = "sources/videos/" + project.name + "/"
            for name in verified["snapshot"]:
                sources[prefix + name] = (local(project, name), True)
            for name in (recipe.brief, "PIPELINE.json", "script.txt", "UPLOAD_COPY.md", "CREDITS.md", "VOICE_DELIVERY.json", "VOICE_PLAN.json",
                         "SOUND_PROVENANCE.json", "THREE_PROVENANCE.json", "brag-plan.md", "composition-brief.md",
                         "assets/audio/narration.srt", "assets/audio/narration.performance.json",
                         "assets/audio/narration.asr-evidence.json", "assets/audio/voice-reference.wav",
                         "assets/audio/voice-reference.provenance.json"):
                if (project / name).is_file():
                    sources[prefix + name] = (local(project, name), name in verified["snapshot"])
            voice_files = read(local(project, "VOICE_DELIVERY.json")).get("voice_files")
            if not isinstance(voice_files, dict) or not voice_files:
                raise PipelineError("Portable voice source package requires its bound voice_files receipt")
            for name, expected in voice_files.items():
                source = local(project, name)
                if sha(source) != expected:
                    raise PipelineError("A bound canonical voice file changed")
                sources[prefix + name] = (source, True)
            sources[prefix + "VOICE_PLAN.json"] = (local(project, "VOICE_PLAN.json"), True)
            # Follow local Python imports plus the renderer's explicit helper/template directories.
            # Publishing code, models and interpreter environments are unnecessary for a prepared rebuild.
            support_hashes = {name: sha(local(ROOT, name)) for name in prepared_code(ROOT, recipe)}
            for name in support_hashes:
                sources["sources/" + name] = (local(ROOT, name), True)
            for name in ("pyproject.toml", "LICENSE", "THIRD_PARTY_NOTICES.md", "docs/NEXT_STORY_PIPELINE.md"):
                sources["sources/" + name] = (local(ROOT, name), False)
            for stage in recipe.stages:
                for name in stage.repo_inputs:
                    sources["sources/" + name] = (local(ROOT, name), False)
                for name in stage.inputs:
                    # The package is a prepared source rebuild; don't embed QA crops or prior exports.
                    if not name.startswith(("renders/", "qa/")):
                        exact = sources.get(prefix + name, (None, False))[1] or name in verified["snapshot"]
                        sources[prefix + name] = (local(project, name), exact)
        initial = {name: sha(path) for name, (path, _) in sources.items()}
        target = project / "renders/delivery.zip"
        with tempfile.TemporaryDirectory(prefix="story-package-", dir=project / "renders") as folder:
            stage_root = Path(folder)
            records = []
            for name, (source, exact) in sources.items():
                payload, redacted = export_payload(source, exact=exact, secret_pattern=helpers.SECRET)
                destination = local(stage_root, name, exists=False)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
                records.append({"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                                "source_sha256": initial[name], "private_paths_redacted": redacted})
            readme = (
                f"# {project.name}\n\nPrepared film, exact captions, provenance and decoded review sheets.\n\n"
                f"Video SHA256: `{verified['video_sha256']}`. Technical decode, source identity and encoded-word checks passed. "
                "Decoded sheets require visual review; automated checks do not certify emotion or audience reach.\n\n"
                "This archive contains no model weights, environments, credentials or posting automation. "
                "The source tree is a prepared-assets rebuild; optional voice regeneration needs the separately installed pinned local model.\n"
            )
            (stage_root / "README.md").write_text(readme, encoding="utf-8")
            if include_source:
                rebuild = (
                    "# Prepared source rebuild\n\nUse Python3.11+, Node/npm, FFmpeg/ffprobe, Chrome and PowerShell on Windows. "
                    "From this sources directory create an environment and install the small pinned rebuild requirements.\n\n"
                    "```powershell\npython -m venv .venv\n.venv/Scripts/python.exe -m pip install -e .\n"
                    ".venv/Scripts/python.exe -m pip install -r requirements-rebuild.txt\n"
                    f".venv/Scripts/python.exe scripts/run_cinematic_project.py videos/{project.name} --check-only\n"
                    f".venv/Scripts/python.exe scripts/render_story_project.py videos/{project.name}\n```\n\n"
                    "The first check verifies already-prepared source hashes without generating voice or media. "
                    "The render command reuses that prepared composition. Do not run voice generation merely to rebuild the pixels.\n"
                )
                (stage_root / "sources/REBUILD.md").write_text(rebuild, encoding="utf-8")
                (stage_root / "sources/README.md").write_text(readme + "\nSee REBUILD.md for prepared source verification.\n", encoding="utf-8")
                requirements = [f"{name}=={importlib.metadata.version(name)}" for name in
                                ("numpy", "scipy", "soundfile", "pydantic", "portalocker", "pillow")]
                (stage_root / "sources/requirements-rebuild.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
            manifest = {"schema_version": 1, "project_id": project.name, "status": "verified_technical_export",
                        "video_sha256": verified["video_sha256"], "media": verified["report"]["output"],
                        "files": records, "includes_project_source": include_source, "published": False,
                        "visual_review_verified": False, "voice_emotion_verified": False}
            write(stage_root / "DELIVERY_MANIFEST.json", manifest)
            paths = sorted(p for p in stage_root.rglob("*") if p.is_file())
            (stage_root / "SHA256SUMS.txt").write_text("".join(f"{sha(p)}  {p.relative_to(stage_root).as_posix()}\n" for p in paths), encoding="utf-8")
            temporary = stage_root / "archive.zip"
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
                for path in sorted(p for p in stage_root.rglob("*") if p.is_file() and p != temporary):
                    info = zipfile.ZipInfo(path.relative_to(stage_root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, path.read_bytes(), compresslevel=1)
            if any(sha(path) != initial[name] for name, (path, _) in sources.items()):
                raise PipelineError("A package input changed during export")
            if support_hashes and any(sha(local(ROOT, name)) != value for name, value in support_hashes.items()):
                raise PipelineError("Implementation changed during source packaging")
            verify_current_render(project)
            os.replace(temporary, target)
        result = {"schema_version": 1, "project_id": project.name, "status": "verified_technical_export",
                  "archive": "renders/delivery.zip", "archive_sha256": sha(target), "archive_bytes": target.stat().st_size,
                  "video_sha256": verified["video_sha256"], "source_included": include_source,
                  "visual_review_verified": False, "published": False}
        write(project / "STORY_PACKAGE.json", result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--consumer-only", action="store_true")
    args = parser.parse_args()
    try:
        result = package(args.project, include_source=not args.consumer_only)
    except Exception:
        print("Story package rejected. Check current delivery, audio/frame QA, credits and portable source paths.")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
