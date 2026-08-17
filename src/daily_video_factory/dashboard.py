from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from . import __version__
from .config import Settings
from .exceptions import ConfigurationError
from .media.ffmpeg import FFmpeg
from .music_video import analyze_music
from .state import RunStore
from .studio import StudioJob, StudioJobRequest, StudioManager


def create_app(settings: Settings, profile_directory: Path = Path("config/profiles")) -> FastAPI:
    app = FastAPI(title="AtlasForge AI", version=__version__)
    store = RunStore(settings.output_directory.resolve())
    studio = StudioManager(settings, profile_directory)

    def run_root(run: dict[str, object]) -> Path:
        """Resolve persisted host paths through the current Docker/native output mount."""
        output_root = settings.output_directory.resolve()
        stored = Path(str(run["output_root"])).resolve()
        if (stored == output_root or output_root in stored.parents) and stored.is_dir():
            return stored
        mounted = output_root / f"{run['publication_date']}-{run['run_id']}"
        if mounted.is_dir():
            return mounted.resolve()
        raise HTTPException(status_code=404, detail="Run artifacts are not available")

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, object]]:
        return store.list_runs()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        run["stages"] = store.list_stages(run_id)
        root = run_root(run)
        report = root / "quality" / "ai_clip_report.json"
        if report.is_file():
            run["ai_quality"] = json.loads(report.read_text(encoding="utf-8"))
        return run

    def run_artifact(run_id: str, field: str) -> Path:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        value = run.get(field)
        if not value:
            raise HTTPException(
                status_code=404, detail=f"{field.replace('_', ' ').title()} is not ready"
            )
        root = run_root(run)
        target = Path(str(value)).resolve()
        if root not in target.parents or not target.is_file():
            relative = {
                "final_video": Path("final/video.mp4"),
                "thumbnail": Path("thumbnails/viral-poster.jpg"),
            }.get(field)
            if relative is None or not (target := root / relative).is_file():
                # Narrated/music runs use a generated thumbnail name rather than viral-poster.
                if field != "thumbnail":
                    raise HTTPException(status_code=404, detail="Artifact not found")
                thumbnails = sorted((root / "thumbnails").glob("*.jpg"))
                if not thumbnails:
                    raise HTTPException(status_code=404, detail="Artifact not found")
                target = thumbnails[0]
        if root not in target.resolve().parents:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return target

    @app.get("/api/runs/{run_id}/video")
    def get_run_video(run_id: str) -> FileResponse:
        return FileResponse(run_artifact(run_id, "final_video"), media_type="video/mp4")

    @app.get("/api/runs/{run_id}/thumbnail")
    def get_run_thumbnail(run_id: str) -> FileResponse:
        return FileResponse(run_artifact(run_id, "thumbnail"), media_type="image/jpeg")

    @app.get("/api/runs/{run_id}/storyboard")
    def get_run_storyboard(run_id: str) -> dict[str, object]:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        root = run_root(run)
        storyboard = root / "storyboards" / "storyboard_timed.json"
        if not storyboard.is_file():
            raise HTTPException(status_code=404, detail="Storyboard is not ready")
        return json.loads(storyboard.read_text(encoding="utf-8"))

    @app.get("/api/runs/{run_id}/scenes/{scene_index}")
    def get_run_scene(run_id: str, scene_index: int) -> FileResponse:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        root = run_root(run)
        image_index = root / "scenes" / "images.json"
        if not image_index.is_file():
            raise HTTPException(status_code=404, detail="Scene images are not ready")
        payload = json.loads(image_index.read_text(encoding="utf-8"))
        match = next((item for item in payload if int(item.get("scene", -1)) == scene_index), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Scene image not found")
        raw_target = str(match.get("path", ""))
        target = Path(raw_target).resolve()
        if root not in target.parents or not target.is_file():
            filename = (
                PureWindowsPath(raw_target).name if "\\" in raw_target else Path(raw_target).name
            )
            target = (root / "scenes" / filename).resolve()
        if root not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="Scene image not found")
        return FileResponse(target, media_type="image/jpeg")

    @app.get("/api/profiles")
    def list_profiles() -> list[dict[str, object]]:
        return studio.profiles()

    @app.get("/api/system")
    def system_status() -> dict[str, object]:
        return studio.status()

    @app.post("/api/music/uploads", status_code=201)
    async def upload_music(file: Annotated[UploadFile, File()]) -> dict[str, object]:
        try:
            upload_id, target = studio.reserve_music_upload(file.filename or "track")
        except ConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        size = 0
        try:
            with target.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 250 * 1024 * 1024:
                        raise HTTPException(
                            status_code=413, detail="Music uploads are limited to 250 MB"
                        )
                    destination.write(chunk)
            if size < 4096:
                raise HTTPException(status_code=400, detail="The uploaded music file is empty")
            beat_map = await run_in_threadpool(analyze_music, target, FFmpeg())
            analysis_file = studio.upload_root / f"{upload_id}.json"
            analysis_file.write_text(beat_map.model_dump_json(indent=2), encoding="utf-8")
        except HTTPException:
            target.unlink(missing_ok=True)
            raise
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400, detail=f"Could not decode and analyze this track: {exc}"
            ) from exc
        finally:
            await file.close()
        return {
            "upload_id": upload_id,
            "filename": Path(file.filename or "track").name,
            "size_bytes": size,
            "audio_url": f"/api/music/uploads/{upload_id}/audio",
            "beat_map": beat_map.model_dump(mode="json"),
        }

    @app.get("/api/music/uploads/{upload_id}/audio")
    def get_music_upload(upload_id: str) -> FileResponse:
        target = studio.music_upload_path(upload_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Music upload not found")
        return FileResponse(target)

    @app.post("/api/reference/uploads", status_code=201)
    async def upload_reference(file: Annotated[UploadFile, File()]) -> dict[str, object]:
        try:
            upload_id, target = studio.reserve_reference_upload(file.filename or "reference")
        except ConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        size = 0
        try:
            with target.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 20 * 1024 * 1024:
                        raise HTTPException(
                            status_code=413, detail="Reference images are limited to 20 MB"
                        )
                    destination.write(chunk)
            if size < 1024:
                raise HTTPException(status_code=400, detail="The reference image is empty")
            with Image.open(target) as candidate:
                candidate.verify()
            with Image.open(target) as candidate:
                width, height = candidate.size
                image_format = candidate.format
            if width < 256 or height < 256:
                raise HTTPException(
                    status_code=400, detail="Reference images must be at least 256×256"
                )
        except HTTPException:
            target.unlink(missing_ok=True)
            raise
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            target.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400, detail="This is not a safe, readable image"
            ) from exc
        finally:
            await file.close()
        return {
            "upload_id": upload_id,
            "filename": Path(file.filename or "reference").name,
            "size_bytes": size,
            "width": width,
            "height": height,
            "format": image_format,
            "image_url": f"/api/reference/uploads/{upload_id}/image",
        }

    @app.get("/api/reference/uploads/{upload_id}/image")
    def get_reference_upload(upload_id: str) -> FileResponse:
        target = studio.reference_upload_path(upload_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Reference image not found")
        return FileResponse(target)

    @app.get("/api/jobs", response_model=list[StudioJob])
    def list_jobs() -> list[StudioJob]:
        return studio.list_jobs()

    @app.post("/api/jobs", response_model=StudioJob, status_code=202)
    def create_job(request: StudioJobRequest) -> StudioJob:
        try:
            return studio.create(request)
        except ConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}", response_model=StudioJob)
    def get_job(job_id: str) -> StudioJob:
        job = studio.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/api/jobs/{job_id}/log")
    def get_job_log(job_id: str) -> dict[str, str]:
        log = studio.log_tail(job_id)
        if log is None:
            raise HTTPException(status_code=404, detail="Job or log not found")
        return {"log": log}

    @app.post("/api/jobs/{job_id}/cancel", response_model=StudioJob)
    def cancel_job(job_id: str) -> StudioJob:
        job = studio.cancel(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    package_web = Path(__file__).with_name("web")
    development_web = Path.cwd() / "frontend" / "dist" / "client"
    web_root = package_web if package_web.is_dir() else development_web
    if web_root.is_dir():
        app.mount("/", StaticFiles(directory=web_root, html=True), name="studio")
    else:

        @app.get("/", response_class=HTMLResponse)
        def home() -> str:
            return "<h1>AtlasForge Studio frontend is not built.</h1><p>Run the frontend build, then restart this service.</p>"

    return app
