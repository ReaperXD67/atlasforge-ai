from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TextIO

import httpx
import yaml
from pydantic import BaseModel, Field

from .artifacts import atomic_write
from .config import Settings, load_settings
from .exceptions import ConfigurationError


class StudioJobRequest(BaseModel):
    profile: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    topic: str | None = Field(default=None, max_length=300)
    duration_minutes: float | None = Field(default=None, ge=1, le=12)
    fps: Literal[30, 60] = 60
    quality: Literal["fast", "balanced", "max"] = "balanced"
    stock_images: bool = True
    local_ai: bool = False
    captions: bool = True
    fresh: bool = True


class StudioJob(BaseModel):
    job_id: str
    profile: str
    topic: str | None = None
    state: Literal["queued", "running", "completed", "failed", "cancelled", "interrupted"]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    pid: int | None = None
    exit_code: int | None = None
    config_file: Path
    log_file: Path


class _ManagedProcess:
    def __init__(self, process: subprocess.Popen[str], log_handle: TextIO) -> None:
        self.process = process
        self.log_handle = log_handle


class StudioManager:
    def __init__(self, settings: Settings, profile_directory: Path) -> None:
        self.settings = settings
        self.profile_directory = profile_directory.resolve()
        self.root = settings.output_directory.resolve() / ".studio" / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._processes: dict[str, _ManagedProcess] = {}
        self._machine_status = self._detect_machine()
        self._recover_interrupted_jobs()

    @staticmethod
    def _detect_machine() -> dict[str, object]:
        ffmpeg_path = shutil.which("ffmpeg")
        gpu_name = ""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                gpu_name = result.stdout.splitlines()[0].strip()
        except (OSError, subprocess.TimeoutExpired, IndexError):
            pass

        nvenc = False
        if ffmpeg_path:
            try:
                encoders = subprocess.run(
                    [ffmpeg_path, "-hide_banner", "-encoders"],
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=4,
                )
                nvenc = "h264_nvenc" in encoders.stdout
            except (OSError, subprocess.TimeoutExpired):
                pass

        return {
            "ffmpeg": bool(ffmpeg_path),
            "gpu": bool(gpu_name),
            "gpu_name": gpu_name,
            "nvenc": nvenc,
            "kokoro": importlib.util.find_spec("kokoro") is not None,
            "whisper": importlib.util.find_spec("faster_whisper") is not None,
            "comfyui": StudioManager._comfyui_available(),
        }

    @staticmethod
    def _comfyui_available() -> bool:
        base_url = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
        try:
            return httpx.get(f"{base_url}/system_stats", timeout=2).status_code == 200
        except httpx.HTTPError:
            return False

    def _profile_path(self, profile: str) -> Path:
        path = (self.profile_directory / f"{profile}.yaml").resolve()
        if path.parent != self.profile_directory or not path.is_file():
            raise ConfigurationError(f"Unknown studio profile: {profile}")
        return path

    def profiles(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        if not self.profile_directory.exists():
            return result
        for path in sorted(self.profile_directory.glob("*.yaml")):
            try:
                settings = load_settings(path)
                result.append(
                    {
                        "id": path.stem,
                        "name": settings.channel.name,
                        "brand": settings.channel.brand_name,
                        "region": settings.channel.region,
                        "goal": settings.channel.content_goal,
                        "duration_minutes": settings.script.target_minutes,
                        "text_provider": settings.script.text_providers[0],
                        "voice_provider": settings.voice.providers[0],
                        "fps": settings.video.fps,
                        "premium_enabled": settings.video.enable_premium_scenes,
                        "local_ai_enabled": settings.video.local_generation_enabled,
                    }
                )
            except ConfigurationError as exc:
                result.append({"id": path.stem, "error": str(exc)})
        return result

    def _job_path(self, job_id: str) -> Path:
        return self.root / job_id / "job.json"

    def _write_job(self, job: StudioJob) -> None:
        atomic_write(self._job_path(job.job_id), job.model_dump_json(indent=2))

    def _read_job(self, path: Path) -> StudioJob:
        return StudioJob.model_validate_json(path.read_text(encoding="utf-8"))

    def _recover_interrupted_jobs(self) -> None:
        for path in self.root.glob("*/job.json"):
            try:
                job = self._read_job(path)
            except (OSError, ValueError):
                continue
            if job.state in {"queued", "running"}:
                job.state = "interrupted"
                job.finished_at = datetime.now(UTC)
                job.pid = None
                self._write_job(job)

    def _render_job_config(self, request: StudioJobRequest, destination: Path) -> None:
        settings = load_settings(self._profile_path(request.profile))
        if request.duration_minutes is not None:
            settings.script.target_minutes = request.duration_minutes
            target_words = round(request.duration_minutes * settings.script.words_per_minute)
            # Keep the generated copy close to the requested runtime. The narration
            # layer provides a final pitch-preserving duration safeguard.
            settings.script.min_words = max(120, round(target_words * 0.85))
            settings.script.max_words = max(
                settings.script.min_words + 40, round(target_words * 1.08)
            )
        settings.video.fps = request.fps
        quality = {
            "fast": (23, "p4"),
            "balanced": (19, "p5"),
            "max": (16, "p6"),
        }[request.quality]
        settings.video.crf, settings.video.preset = quality
        settings.images.providers = (
            ["pexels", "title_card"] if request.stock_images else ["title_card"]
        )
        settings.video.stock_video_enabled = request.stock_images
        settings.video.local_generation_enabled = request.local_ai
        settings.subtitles.burn_in = request.captions
        settings.publishing.enabled = False
        payload = settings.model_dump(mode="json")
        atomic_write(destination, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))

    def create(self, request: StudioJobRequest) -> StudioJob:
        with self._lock:
            self._refresh_processes()
            if any(job.state in {"queued", "running"} for job in self.list_jobs()):
                raise RuntimeError("A generation is already running on this machine")
            job_id = uuid.uuid4().hex[:12]
            directory = self.root / job_id
            directory.mkdir(parents=True, exist_ok=False)
            config_file = directory / "config.yaml"
            log_file = directory / "process.log"
            self._render_job_config(request, config_file)
            job = StudioJob(
                job_id=job_id,
                profile=request.profile,
                topic=request.topic,
                state="queued",
                created_at=datetime.now(UTC),
                config_file=config_file,
                log_file=log_file,
            )
            self._write_job(job)
            command = [
                sys.executable,
                "-m",
                "daily_video_factory.cli",
                "run",
                "--config",
                str(config_file),
                "--no-upload",
                "--fresh" if request.fresh else "--resume",
            ]
            if request.topic:
                command.extend(["--topic", request.topic.strip()])
            log_handle = log_file.open("a", encoding="utf-8")
            process = subprocess.Popen(
                command,
                cwd=Path.cwd(),
                env=os.environ.copy(),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            job.state = "running"
            job.started_at = datetime.now(UTC)
            job.pid = process.pid
            self._processes[job_id] = _ManagedProcess(process, log_handle)
            self._write_job(job)
            return job

    def _refresh_processes(self) -> None:
        for job_id, managed in list(self._processes.items()):
            exit_code = managed.process.poll()
            if exit_code is None:
                continue
            managed.log_handle.close()
            job = self.get_job(job_id, refresh=False)
            if job is not None and job.state != "cancelled":
                job.state = "completed" if exit_code == 0 else "failed"
                job.exit_code = exit_code
                job.finished_at = datetime.now(UTC)
                job.pid = None
                self._write_job(job)
            del self._processes[job_id]

    def list_jobs(self, limit: int = 25) -> list[StudioJob]:
        self._refresh_processes()
        jobs: list[StudioJob] = []
        for path in self.root.glob("*/job.json"):
            try:
                jobs.append(self._read_job(path))
            except (OSError, ValueError):
                continue
        return sorted(jobs, key=lambda item: item.created_at, reverse=True)[:limit]

    def get_job(self, job_id: str, *, refresh: bool = True) -> StudioJob | None:
        if not re.fullmatch(r"[a-f0-9]{12}", job_id):
            return None
        if refresh:
            self._refresh_processes()
        path = self._job_path(job_id)
        return self._read_job(path) if path.exists() else None

    def cancel(self, job_id: str) -> StudioJob | None:
        with self._lock:
            managed = self._processes.get(job_id)
            job = self.get_job(job_id, refresh=False)
            if job is None:
                return None
            if managed is None or managed.process.poll() is not None:
                return job
            managed.process.terminate()
            try:
                managed.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                managed.process.kill()
                managed.process.wait(timeout=5)
            managed.log_handle.close()
            del self._processes[job_id]
            job.state = "cancelled"
            job.exit_code = managed.process.returncode
            job.finished_at = datetime.now(UTC)
            job.pid = None
            self._write_job(job)
            return job

    def log_tail(self, job_id: str, max_chars: int = 12_000) -> str | None:
        job = self.get_job(job_id)
        if job is None or not job.log_file.exists():
            return None
        with job.log_file.open("rb") as source:
            source.seek(0, 2)
            size = source.tell()
            source.seek(max(0, size - max_chars))
            return source.read().decode("utf-8", errors="replace")

    def status(self) -> dict[str, object]:
        return {
            **self._machine_status,
            "comfyui": self._comfyui_available(),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "pexels": bool(os.getenv("PEXELS_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "google": bool(os.getenv("GOOGLE_API_KEY")),
            "publishing_enabled": self.settings.publishing.enabled,
            "output_directory": str(self.settings.output_directory.resolve()),
            "profiles": len(self.profiles()),
            "width": self.settings.video.width,
            "height": self.settings.video.height,
            "fps": self.settings.video.fps,
            "codec": self.settings.video.codec,
            "fallback_codec": self.settings.video.fallback_codec,
        }
