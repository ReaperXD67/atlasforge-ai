"""Small local stage runner: explicit inputs, content-addressed reuse and honest receipts."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

import portalocker
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = re.compile(r"(?:[a-z]:[/\\]|/Users/|/home/|https?://|(?:access_token|password|client_secret)=|\bsk-[A-Za-z0-9_-]{20,})", re.I)


class PipelineError(ValueError):
    """An explicit local pipeline cannot safely produce its declared artifacts."""


def relative(value: str) -> str:
    if (not value or "\\" in value or ":" in value or "\x00" in value
            or PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
            or ".." in PurePosixPath(value).parts
            or any(part.lower() in {".git", ".env", ".venv", "secrets", "node_modules"}
                   for part in PurePosixPath(value).parts)):
        raise ValueError("Use a contained, nonprivate relative POSIX file path")
    return value


def local(root: Path, name: str, *, exists: bool = True) -> Path:
    relative(name)
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or (exists and not target.is_file()):
        raise PipelineError("A required local file is missing or escapes its root")
    return target


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise PipelineError("A pipeline receipt must contain an object")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
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
        if temporary:
            temporary.unlink(missing_ok=True)


class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    executor: Literal["python", "node"]
    entrypoint: str
    args: list[str] = Field(default_factory=list, max_length=40)
    inputs: list[str] = Field(default_factory=list, max_length=100)
    repo_inputs: list[str] = Field(default_factory=list, max_length=100)
    outputs: list[str] = Field(min_length=1, max_length=100)
    output_trees: list[str] = Field(default_factory=list, max_length=8)
    timeout_seconds: int = Field(default=10800, ge=1, le=21600)

    _entry = field_validator("entrypoint")(relative)

    @field_validator("inputs", "outputs", "repo_inputs", "output_trees")
    @classmethod
    def paths(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("File lists must contain distinct paths")
        return [relative(value) for value in values]

    @field_validator("args")
    @classmethod
    def arguments(cls, values: list[str]) -> list[str]:
        for value in values:
            if (len(value) > 512 or any(c in value for c in "\n\r\x00") or PRIVATE.search(value)
                    or ".." in value.split("/") or "{" in value.replace("{project}", "")
                    or "}" in value.replace("{project}", "")):
                raise ValueError("Arguments must be portable literals or {project} paths, without secrets")
        return values

    @model_validator(mode="after")
    def disjoint_files(self) -> Stage:
        if (set(self.inputs) & set(self.outputs)
                or any(name == tree or name.startswith(tree + "/") for name in self.inputs for tree in self.output_trees)):
            raise ValueError("A stage cannot overwrite one of its own declared inputs")
        suffix = ".py" if self.executor == "python" else ".mjs"
        if not self.entrypoint.startswith("scripts/") or not self.entrypoint.endswith(suffix):
            raise ValueError("Use a reviewed scripts/*.py or scripts/*.mjs entrypoint")
        return self


class StoryPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = 1
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,99}$")
    brief: str = "BRIEF.md"
    stages: list[Stage] = Field(min_length=1, max_length=16)

    _brief = field_validator("brief")(relative)

    @model_validator(mode="after")
    def unique_producers(self) -> StoryPipeline:
        ids = [stage.id for stage in self.stages]
        outputs = [name for stage in self.stages for name in stage.outputs]
        if len(ids) != len(set(ids)) or len(outputs) != len(set(outputs)):
            raise ValueError("Stage IDs and output producers must be unique")
        if self.brief in outputs:
            raise ValueError("The authored story brief is immutable input")
        produced: set[str] = set()
        all_outputs = set(outputs)
        owners: list[tuple[str, str, bool]] = []
        for stage in self.stages:
            if any(name in all_outputs and name not in produced for name in stage.inputs):
                raise ValueError("Stages must appear after the producers of their inputs")
            produced.update(stage.outputs)
            for name, is_tree in [(name, False) for name in stage.outputs] + [(name, True) for name in stage.output_trees]:
                for prior, owner, prior_tree in owners:
                    if owner != stage.id and (name == prior or (prior_tree and name.startswith(prior + "/"))
                                              or (is_tree and prior.startswith(name + "/"))):
                        raise ValueError("Stage output trees must have distinct ownership")
                owners.append((name, stage.id, is_tree))
        return self


def implementation_hashes(root: Path) -> dict[str, str]:
    """Cover transitive local Python/JS/template imports without a second dependency engine."""
    paths: set[Path] = set()
    for directory in (root / "src", root / "scripts"):
        if directory.is_dir():
            paths.update(p for p in directory.rglob("*") if p.is_file() and
                         p.suffix in {".py", ".mjs", ".js", ".css", ".ps1"})
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(paths)}


def toolchain_fingerprint() -> dict[str, Any]:
    versions: dict[str, Any] = {"python": list(sys.version_info[:3]), "tools": {}, "packages": {}, "chrome": {}}
    for program in ("node", "ffmpeg", "ffprobe"):
        executable = shutil.which(program)
        if executable:
            result = subprocess.run([executable, "--version" if program == "node" else "-version"],
                                    capture_output=True, text=True, timeout=20, check=True)
            versions["tools"][program] = {"version": result.stdout.splitlines()[0], "binary_sha256": sha(Path(executable))}
        else:
            versions["tools"][program] = None
    for package in ("numpy", "scipy", "soundfile", "pydantic", "portalocker", "pillow", "faster-whisper"):
        try:
            versions["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions["packages"][package] = None
    if os.name == "nt":
        for base in ("C:/Program Files/Google/Chrome/Application", "C:/Program Files (x86)/Google/Chrome/Application"):
            directory = Path(base)
            if (directory / "chrome.exe").is_file():
                versions["chrome"] = {p.relative_to(directory).as_posix(): sha(p)
                                      for p in [directory / "chrome.exe", *sorted(directory.glob("*/chrome.dll"))]}
                break
    return versions


def fingerprint(stage: Stage, project: Path, root: Path, *, brief: str,
                implementation: dict[str, str], toolchain: dict[str, Any]) -> tuple[str, dict[str, str]]:
    inputs = {"project/" + name: sha(local(project, name)) for name in [brief, *stage.inputs]}
    inputs.update({"repo/" + name: sha(local(root, name)) for name in [stage.entrypoint, *stage.repo_inputs]})
    body = {"stage": stage.model_dump(), "inputs": inputs, "implementation": implementation,
            "toolchain": toolchain}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(), inputs


def output_hashes(stage: Stage, project: Path) -> dict[str, str]:
    result = {name: sha(local(project, name)) for name in stage.outputs}
    for name in stage.output_trees:
        directory = local(project, name, exists=False)
        if not directory.is_dir() or (project / name).is_symlink():
            raise PipelineError("An output tree is missing or is a symlink")
        files = list(directory.rglob("*"))
        if any(path.is_symlink() for path in files):
            raise PipelineError("Output trees cannot contain symlinks")
        for path in files:
            if path.is_file():
                key = path.relative_to(project).as_posix()
                result[key] = sha(local(project, key))
    return result


def execute_stage(stage: Stage, project: Path, root: Path, log: Path) -> None:
    program = sys.executable if stage.executor == "python" else shutil.which("node")
    if not program:
        raise PipelineError("A required local runtime is unavailable")
    argv = [program, str(local(root, stage.entrypoint)),
            *(arg.replace("{project}", str(project)) for arg in stage.args)]
    # Reviewed local code is trusted; this is not an operating-system sandbox.
    # Shell parsing and environment/credentials in portable receipts are avoided.
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(argv, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=stage.timeout_seconds, check=False)
    if result.returncode:
        raise PipelineError("Stage command failed; inspect its local log")


def run_pipeline(project: Path, *, execute: bool = False, resume: bool = False,
                 root: Path = ROOT) -> dict[str, Any]:
    root, project = root.resolve(), project.resolve()
    if not project.is_relative_to(root / "videos") or project == root / "videos":
        raise PipelineError("The story project must be inside this repository's videos directory")
    spec_path = local(project, "PIPELINE.json")
    spec = StoryPipeline.model_validate(read(spec_path))
    if spec.project_id != project.name:
        raise PipelineError("Pipeline identity differs from its project directory")
    local(project, spec.brief)
    for stage in spec.stages:
        local(root, stage.entrypoint)
    if not execute:
        return {"status": "plan_only", "project_id": spec.project_id,
                "stages": [stage.id for stage in spec.stages], "executed": False,
                "creative_quality_verified": False, "published": False}
    evidence = root / "output/story-pipeline" / spec.project_id
    evidence.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    directory = evidence / run_id
    report: dict[str, Any] = {"schema_version": 1, "run_id": run_id, "project_id": spec.project_id,
        "started_at": datetime.now(UTC).isoformat(), "status": "running", "stages": [],
        "executed": True, "creative_quality_verified": False,
        "audience_performance_predicted": False, "published": False}
    started = time.perf_counter()
    with portalocker.Lock(str(evidence / "pipeline.lock"), timeout=0):
        directory.mkdir()
        state_path = evidence / "state.json"
        write(directory / "report.json", report)
        write(evidence / "latest.json", report)
        try:
            state = read(state_path) if state_path.is_file() else {"stages": {}}
            implementation = implementation_hashes(root)
            toolchain = toolchain_fingerprint()
            report["toolchain"] = toolchain
            authored_hash = sha(spec_path)
            brief_hash = sha(local(project, spec.brief))
            for stage in spec.stages:
                stage_started = time.perf_counter()
                current: dict[str, Any] = {"id": stage.id, "status": "running"}
                report["stages"].append(current)
                signature, inputs = fingerprint(stage, project, root, brief=spec.brief,
                                                implementation=implementation, toolchain=toolchain)
                cached = state.get("stages", {}).get(stage.id, {})
                cached_outputs = None
                if resume and cached.get("signature") == signature:
                    with suppress(OSError, PipelineError):
                        cached_outputs = output_hashes(stage, project)
                if cached_outputs is not None and cached_outputs == cached.get("outputs"):
                    current.update(status="reused", input_signature=signature, outputs=cached_outputs)
                else:
                    print(f"[{stage.id}] starting", flush=True)
                    execute_stage(stage, project, root, directory / f"{stage.id}.log")
                    if fingerprint(stage, project, root, brief=spec.brief,
                                   implementation=implementation, toolchain=toolchain)[0] != signature:
                        raise PipelineError("Stage inputs changed during execution")
                    outputs = output_hashes(stage, project)
                    current.update(status="passed", input_signature=signature, inputs=inputs, outputs=outputs)
                    state.setdefault("stages", {})[stage.id] = {"signature": signature, "outputs": outputs}
                    write(state_path, state)
                if (sha(spec_path) != authored_hash or sha(local(project, spec.brief)) != brief_hash
                        or implementation_hashes(root) != implementation):
                    raise PipelineError("Authored pipeline or implementation changed during execution")
                current["elapsed_seconds"] = round(time.perf_counter() - stage_started, 3)
                print(f"[{stage.id}] {current['status']} in {current['elapsed_seconds']:.3f}s", flush=True)
                write(directory / "report.json", report)
            # Check every stage again: a later stage must not mutate an earlier output.
            for stage in spec.stages:
                saved = state["stages"][stage.id]
                if (fingerprint(stage, project, root, brief=spec.brief,
                                implementation=implementation, toolchain=toolchain)[0] != saved["signature"]
                        or output_hashes(stage, project) != saved["outputs"]):
                    raise PipelineError("A later stage changed an earlier stage's inputs or outputs")
            if toolchain_fingerprint() != toolchain:
                raise PipelineError("The media toolchain changed during the run")
            report["status"] = "stages_verified"
            if any("STORY_PACKAGE.json" in stage.outputs for stage in spec.stages):
                from daily_video_factory.story_delivery import (
                    verify_current_render,
                    verify_story_qa,
                )

                verified = verify_current_render(project)
                verify_story_qa(project, verified)
                package = read(local(project, "STORY_PACKAGE.json"))
                if (package.get("status") != "verified_technical_export"
                        or package.get("video_sha256") != verified["video_sha256"]
                        or sha(local(project, package["archive"])) != package.get("archive_sha256")):
                    raise PipelineError("Packaged bytes differ from the verified film or package receipt")
                report.update(status="verified_technical_delivery", video_sha256=verified["video_sha256"],
                              archive_sha256=package["archive_sha256"], technical_delivery_verified=True)
        except BaseException as exc:
            report.update(status="failed", error_type=type(exc).__name__,
                          error="Pipeline stopped; inspect the failed stage's local log and declared files")
            if report["stages"] and report["stages"][-1]["status"] == "running":
                report["stages"][-1]["status"] = "failed"
            raise
        finally:
            report["finished_at"] = datetime.now(UTC).isoformat()
            report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            write(directory / "report.json", report)
            write(evidence / "latest.json", report)
    return report
