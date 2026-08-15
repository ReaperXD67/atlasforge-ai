from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings
from .exceptions import ConfigurationError
from .state import RunStore
from .studio import StudioJob, StudioJobRequest, StudioManager


def create_app(settings: Settings, profile_directory: Path = Path("config/profiles")) -> FastAPI:
    app = FastAPI(title="AtlasForge AI", version=__version__)
    store = RunStore(settings.output_directory.resolve())
    studio = StudioManager(settings, profile_directory)

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, object]]:
        return store.list_runs()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        run["stages"] = store.list_stages(run_id)
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
        target = Path(str(value)).resolve()
        output_root = settings.output_directory.resolve()
        if output_root not in target.parents or not target.is_file():
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
        root = Path(str(run["output_root"])).resolve()
        output_root = settings.output_directory.resolve()
        storyboard = root / "storyboards" / "storyboard_timed.json"
        if output_root not in storyboard.parents or not storyboard.is_file():
            raise HTTPException(status_code=404, detail="Storyboard is not ready")
        return json.loads(storyboard.read_text(encoding="utf-8"))

    @app.get("/api/profiles")
    def list_profiles() -> list[dict[str, object]]:
        return studio.profiles()

    @app.get("/api/system")
    def system_status() -> dict[str, object]:
        return studio.status()

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
