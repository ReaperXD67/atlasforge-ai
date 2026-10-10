from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from PIL import Image

from .shorts_delivery import (
    validate_short_delivery,
    validate_shorts_upload_package,
    validate_voice_manifest,
)

APPROVED_VOICE = "af_heart"
_EXCLUDED_DIRECTORIES = {
    ".hyperframes",
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".production-cache",
    ".waveform-cache",
    "renders",
    "snapshots",
}
_SOURCE_EXTENSIONS = {
    ".html",
    ".htm",
    ".css",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".lock",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".avif",
    ".bmp",
    ".tif",
    ".tiff",
    ".wav",
    ".mp3",
    ".aac",
    ".m4a",
    ".ogg",
    ".opus",
    ".flac",
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".srt",
    ".vtt",
    ".glb",
    ".gltf",
    ".obj",
    ".mtl",
    ".bin",
    ".ktx",
    ".ktx2",
    ".hdr",
    ".exr",
    ".lottie",
    ".wasm",
    ".webmanifest",
}


class ShortsBatchError(ValueError):
    """Raised when a batch manifest or its local render setup is invalid."""


@dataclass(frozen=True)
class ShortsBatchEpisode:
    id: str
    project: Path
    output: Path
    thumbnail: Path
    upload_package: Path
    voice_manifest: Path

    @property
    def raw_output(self) -> Path:
        return _relative_path(self.project, "renders/unmastered.mp4", "raw output")

    @property
    def mastered_output(self) -> Path:
        return _relative_path(
            self.project, f"renders/.batch-mastered-{self.id}.mp4", "mastering output"
        )


@dataclass(frozen=True)
class ShortsBatchManifest:
    path: Path
    repository_root: Path
    batch_id: str
    expected_voice: str
    episodes: tuple[ShortsBatchEpisode, ...]

    @property
    def report_path(self) -> Path:
        return _relative_path(self.path.parent, "BATCH_REPORT.json", "batch report")


def _relative_path(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ShortsBatchError(f"{label} must be a non-empty relative path")
    windows_path = PureWindowsPath(value)
    if Path(value).is_absolute() or windows_path.drive or windows_path.root:
        raise ShortsBatchError(f"{label} must be relative: {value}")
    # Interpret either slash style consistently, including in non-Windows tests.
    path = (root / value.replace("\\", "/")).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ShortsBatchError(f"{label} escapes its allowed directory: {value}")
    return path


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ShortsBatchError(f"{label} must be a non-empty letters/numbers/dashes identifier")
    return value


def load_shorts_batch_manifest(
    manifest_path: Path, *, repository_root: Path | None = None
) -> ShortsBatchManifest:
    root = (repository_root or Path(__file__).resolve().parents[2]).resolve()
    path = manifest_path.resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ShortsBatchError(f"cannot read batch manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ShortsBatchError("batch manifest must be a JSON object")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ShortsBatchError("unsupported batch schema_version; expected 1")
    batch_id = _identifier(payload.get("batch_id"), "batch_id")
    if payload.get("expected_voice") != APPROVED_VOICE:
        raise ShortsBatchError(f"expected_voice must remain locked to {APPROVED_VOICE!r}")
    rows = payload.get("episodes")
    if not isinstance(rows, list) or not rows:
        raise ShortsBatchError("batch manifest requires at least one episode")
    ids: set[str] = set()
    outputs: set[Path] = set()
    episodes: list[ShortsBatchEpisode] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ShortsBatchError("every episode must be a JSON object")
        episode_id = _identifier(row.get("id"), "episode id")
        if episode_id in ids:
            raise ShortsBatchError(f"duplicate episode id: {episode_id}")
        ids.add(episode_id)
        project = _relative_path(root, row.get("project"), f"{episode_id} project")
        episode = ShortsBatchEpisode(
            id=episode_id,
            project=project,
            output=_relative_path(project, row.get("output"), f"{episode_id} output"),
            thumbnail=_relative_path(project, row.get("thumbnail"), f"{episode_id} thumbnail"),
            upload_package=_relative_path(
                project, row.get("upload_package"), f"{episode_id} upload_package"
            ),
            voice_manifest=_relative_path(
                project, row.get("voice_manifest"), f"{episode_id} voice_manifest"
            ),
        )
        if episode.output.suffix.lower() != ".mp4":
            raise ShortsBatchError(f"{episode_id} output must end in .mp4")
        if episode.output in {episode.raw_output, episode.mastered_output}:
            raise ShortsBatchError(f"{episode_id} output conflicts with an intermediate render")
        if episode.output in {episode.thumbnail, episode.upload_package, episode.voice_manifest}:
            raise ShortsBatchError(f"{episode_id} output conflicts with an input deliverable")
        if episode.output in outputs:
            raise ShortsBatchError(f"duplicate episode output: {episode.output}")
        outputs.add(episode.output)
        episodes.append(episode)
    return ShortsBatchManifest(path, root, batch_id, APPROVED_VOICE, tuple(episodes))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _secret_filename(name: str) -> bool:
    name = name.lower()
    return (
        name == ".env"
        or name.startswith(".env.")
        or Path(name).stem
        in {
            "credentials",
            "credential",
            "secrets",
            "secret",
            "access-token",
            "access_token",
            "refresh-token",
            "refresh_token",
            "private-key",
            "private_key",
            "service-account",
            "service_account",
        }
    )


def source_fingerprint(
    episode: ShortsBatchEpisode, manifest: ShortsBatchManifest
) -> tuple[str, list[dict[str, Any]]]:
    """Hash authored files and media, excluding render products and tool caches."""
    if not episode.project.is_dir():
        raise ShortsBatchError(f"project directory is missing: {episode.project}")
    excluded = {manifest.report_path, manifest.report_path.with_suffix(".json.tmp")}
    for item in manifest.episodes:
        excluded.update((item.output, item.raw_output, item.mastered_output))
    files: set[Path] = set()
    for directory, dirs, names in os.walk(episode.project, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name.lower() not in _EXCLUDED_DIRECTORIES)
        for name in dirs:
            child = Path(directory) / name
            if not child.resolve().is_relative_to(episode.project):
                raise ShortsBatchError(f"source directory escapes project: {child}")
            if child.is_symlink():
                raise ShortsBatchError(f"source directory symlinks are unsupported: {child}")
        for name in names:
            candidate = Path(directory) / name
            if _secret_filename(name) or candidate.suffix.lower() not in _SOURCE_EXTENSIONS:
                continue
            resolved = candidate.resolve()
            if not resolved.is_relative_to(episode.project):
                raise ShortsBatchError(f"source file escapes project: {candidate}")
            if resolved not in excluded:
                files.add(candidate)
    files.update((episode.thumbnail, episode.upload_package, episode.voice_manifest))
    source_files = [
        {"path": path.relative_to(episode.project).as_posix(), "sha256": _sha256(path)}
        for path in sorted(files, key=lambda item: item.relative_to(episode.project).as_posix())
    ]
    wrapper = manifest.repository_root / "scripts" / "render_hyperframes_windows.ps1"
    payload = {
        "pipeline_version": 1,
        "expected_voice": manifest.expected_voice,
        "wrapper_sha256": _sha256(wrapper),
        "episode": {
            "id": episode.id,
            "project": episode.project.relative_to(manifest.repository_root).as_posix(),
            "output": episode.output.relative_to(episode.project).as_posix(),
            "thumbnail": episode.thumbnail.relative_to(episode.project).as_posix(),
            "upload_package": episode.upload_package.relative_to(episode.project).as_posix(),
            "voice_manifest": episode.voice_manifest.relative_to(episode.project).as_posix(),
        },
        "files": source_files,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest(), source_files


def _powershell() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if not executable:
        raise ShortsBatchError("local rendering requires pwsh or powershell on PATH")
    return executable


def render_command(episode: ShortsBatchEpisode, manifest: ShortsBatchManifest) -> list[str]:
    wrapper = manifest.repository_root / "scripts" / "render_hyperframes_windows.ps1"
    if not wrapper.is_file():
        raise ShortsBatchError(f"Windows render wrapper is missing: {wrapper}")
    return [
        _powershell(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(wrapper),
        "-Project",
        str(episode.project),
        "-Output",
        str(episode.raw_output),
        "-Quality",
        "delivery",
        "-CheckFirst",
        "-VerifyShorts",
        "-Thumbnail",
        str(episode.thumbnail),
        "-UploadPackage",
        str(episode.upload_package),
        "-VoiceManifest",
        str(episode.voice_manifest),
        "-ExpectedVoice",
        manifest.expected_voice,
    ]


def master_command(episode: ShortsBatchEpisode) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(episode.raw_output),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-c:v",
        "copy",
        "-af",
        "loudnorm=I=-14:TP=-2:LRA=11",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(episode.mastered_output),
    ]


def _run_command(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "no diagnostic output").strip()[-6000:]
        raise ShortsBatchError(f"{Path(command[0]).name} exited {result.returncode}: {detail}")
    # Keep stdout machine-readable while exposing the actual capture-path summary.
    for line in result.stdout.splitlines():
        if "capture" in line and "gpu" in line:
            print(line.strip(), file=sys.stderr, flush=True)


def _require_file(path: Path, label: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ShortsBatchError(f"{label} is missing or empty: {path}")


def _validate_inputs(episode: ShortsBatchEpisode) -> None:
    for label, path in (
        ("thumbnail", episode.thumbnail),
        ("upload package", episode.upload_package),
        ("voice manifest", episode.voice_manifest),
        ("package.json", episode.project / "package.json"),
    ):
        _require_file(path, label)
    with Image.open(episode.thumbnail) as thumbnail:
        if thumbnail.size != (1080, 1920):
            raise ShortsBatchError(f"expected 1080x1920 thumbnail, got {thumbnail.size}")
    validate_shorts_upload_package(episode.upload_package.read_text(encoding="utf-8"))
    validate_voice_manifest(
        json.loads(episode.voice_manifest.read_text(encoding="utf-8")),
        expected_voice=APPROVED_VOICE,
    )


def _verify(video: Path, episode: ShortsBatchEpisode) -> dict[str, Any]:
    return validate_short_delivery(
        video,
        episode.thumbnail,
        upload_package=episode.upload_package,
        voice_manifest=episode.voice_manifest,
        expected_voice=APPROVED_VOICE,
    )


def _deliverable_hashes(episode: ShortsBatchEpisode) -> dict[str, str]:
    return {
        "video": _sha256(episode.output),
        "thumbnail": _sha256(episode.thumbnail),
        "upload_package": _sha256(episode.upload_package),
        "voice_manifest": _sha256(episode.voice_manifest),
    }


def _stamp(path: Path) -> tuple[int, int, int] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, stat.st_ino


def _previous_episodes(manifest: ShortsBatchManifest) -> dict[str, dict[str, Any]]:
    try:
        previous = json.loads(manifest.report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if (
        not isinstance(previous, dict)
        or previous.get("schema_version") != 1
        or previous.get("batch_id") != manifest.batch_id
        or previous.get("expected_voice") != manifest.expected_voice
        or previous.get("manifest") != str(manifest.path)
        or not isinstance(previous.get("episodes"), list)
    ):
        return {}
    return {
        item["id"]: item
        for item in previous["episodes"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    temporary = _relative_path(path.parent, path.name + ".tmp", "temporary batch report")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run_shorts_batch(
    manifest_path: Path,
    *,
    resume: bool = True,
    dry_run: bool = False,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Render each independent episode, persisting only verified successes for resume."""
    manifest = load_shorts_batch_manifest(manifest_path, repository_root=repository_root)
    return _run_batch(manifest, resume=resume, dry_run=dry_run)


def _run_batch(
    manifest: ShortsBatchManifest,
    *,
    resume: bool = True,
    dry_run: bool = False,
    validate_inputs: Callable[..., None] | None = None,
    verify_delivery: Callable[..., dict[str, Any]] | None = None,
    render_job: Callable[..., list[str]] | None = None,
    fingerprint_sources: Callable[..., tuple[str, list[dict[str, Any]]]] | None = None,
    report_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shared transaction loop; the legacy Shorts entry point keeps its existing gates."""
    validate_inputs = validate_inputs or _validate_inputs
    verify_delivery = verify_delivery or _verify
    render_job = render_job or render_command
    fingerprint_sources = fingerprint_sources or source_fingerprint
    previous = _previous_episodes(manifest) if resume and not dry_run else {}
    report: dict[str, Any] = {
        "schema_version": 1,
        "batch_id": manifest.batch_id,
        "manifest": str(manifest.path),
        "expected_voice": manifest.expected_voice,
        "started_at": _now(),
        "status": "dry_run" if dry_run else "running",
        "episodes": [],
    }
    report.update(report_extra or {})
    for number, episode in enumerate(manifest.episodes, 1):
        result: dict[str, Any] = {
            "id": episode.id,
            "project": str(episode.project),
            "output": str(episode.output),
            "thumbnail": str(episode.thumbnail),
            "upload_package": str(episode.upload_package),
            "voice_manifest": str(episode.voice_manifest),
            "resumed": False,
        }
        if hasattr(episode, "format"):
            result.update({key: getattr(episode, key) for key in ("format", "min_seconds", "max_seconds")})
        try:
            validate_inputs(episode)
            fingerprint, sources = fingerprint_sources(episode, manifest)
            result.update(source_fingerprint=fingerprint, source_files=sources)
            old = previous.get(episode.id, {})
            if (
                old.get("status") == "verified"
                and old.get("source_fingerprint") == fingerprint
                and old.get("output") == str(episode.output)
            ):
                try:
                    delivery = verify_delivery(episode.output, episode)
                    hashes = _deliverable_hashes(episode)
                    if hashes == old.get("deliverable_hashes"):
                        result.update(
                            status="verified",
                            resumed=True,
                            report=delivery,
                            deliverable_hashes=hashes,
                        )
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass
            if result.get("status") != "verified":
                render = render_job(episode, manifest)
                master = master_command(episode)
                result.update(render_command=render, master_command=master)
                if dry_run:
                    result["status"] = "planned"
                else:
                    print(f"[{number}/{len(manifest.episodes)}] {episode.id}: check + render", file=sys.stderr, flush=True)
                    episode.raw_output.parent.mkdir(parents=True, exist_ok=True)
                    before_render = _stamp(episode.raw_output)
                    _run_command(render, cwd=manifest.repository_root)
                    _require_file(episode.raw_output, "fresh unmastered render")
                    if _stamp(episode.raw_output) == before_render:
                        raise ShortsBatchError(
                            "render wrapper left a stale unmastered.mp4 unchanged"
                        )
                    before_master = _stamp(episode.mastered_output)
                    print(f"[{number}/{len(manifest.episodes)}] {episode.id}: master + validate", file=sys.stderr, flush=True)
                    _run_command(master, cwd=episode.project)
                    _require_file(episode.mastered_output, "fresh mastered render")
                    if _stamp(episode.mastered_output) == before_master:
                        raise ShortsBatchError("ffmpeg left a stale mastered render unchanged")
                    verify_delivery(episode.mastered_output, episode)
                    after_fingerprint, _ = fingerprint_sources(episode, manifest)
                    if after_fingerprint != fingerprint:
                        raise ShortsBatchError(
                            "project sources changed during rendering; rerun the episode"
                        )
                    episode.output.parent.mkdir(parents=True, exist_ok=True)
                    episode.mastered_output.replace(episode.output)
                    delivery = verify_delivery(episode.output, episode)
                    result.update(
                        status="verified",
                        report=delivery,
                        deliverable_hashes=_deliverable_hashes(episode),
                    )
        except Exception as exc:
            result.update(status="failed", error={"type": type(exc).__name__, "message": str(exc)})
        report["episodes"].append(result)
        if not dry_run:
            suffix = " (resumed)" if result["resumed"] else ""
            print(f"[{number}/{len(manifest.episodes)}] {episode.id}: {result['status']}{suffix}", file=sys.stderr, flush=True)
        if not dry_run:
            _write_report(manifest.report_path, report)
    failed = any(item["status"] == "failed" for item in report["episodes"])
    report.update(
        status="failed" if failed else ("dry_run" if dry_run else "verified"),
        finished_at=_now(),
        report_path=None if dry_run else str(manifest.report_path),
    )
    if not dry_run:
        _write_report(manifest.report_path, report)
    return report
