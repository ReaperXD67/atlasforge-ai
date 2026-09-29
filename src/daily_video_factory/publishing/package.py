from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..artifacts import atomic_write
from ..config import Settings
from ..exceptions import ConfigurationError
from ..models import RunManifest, RunStatus, VideoMetadata
from ..state import RunStore
from .youtube import YouTubePublisher


class PublishSubmission(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    privacy: Literal["private", "unlisted", "public"] = "private"
    publish_at: datetime | None = None
    upload_thumbnail: bool = True
    upload_captions: bool = True
    confirm_public: bool = False

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            tag = value.strip()[:100]
            folded = tag.casefold()
            if tag and folded not in seen:
                cleaned.append(tag)
                seen.add(folded)
        if sum(len(tag) for tag in cleaned) + max(0, len(cleaned) - 1) > 500:
            raise ValueError("YouTube tags must fit within the 500-character limit")
        return cleaned

    @model_validator(mode="after")
    def validate_release(self) -> PublishSubmission:
        if self.privacy == "public" and not self.confirm_public:
            raise ValueError("Confirm a public release explicitly, or upload it privately")
        if self.publish_at is not None:
            if self.publish_at.tzinfo is None:
                raise ValueError("Scheduled publication time must include a timezone")
            if self.publish_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(minutes=5):
                raise ValueError("Scheduled publication must be at least five minutes in the future")
            if self.privacy != "private":
                raise ValueError("YouTube scheduling requires Private visibility")
        return self


class PublishJob(BaseModel):
    publish_id: str
    run_id: str
    state: Literal["queued", "running", "completed", "failed"] = "queued"
    stage: Literal["validating", "metadata", "video", "thumbnail", "captions", "complete"] = (
        "validating"
    )
    progress: int = Field(default=0, ge=0, le=100)
    message: str = "Queued for private upload"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    video_id: str | None = None
    youtube_url: str | None = None
    error: str | None = None


class PublishPreview(BaseModel):
    run_id: str
    run_status: str
    title: str
    description: str
    tags: list[str]
    category_id: str
    video_url: str
    thumbnail_url: str
    video_bytes: int
    thumbnail_bytes: int
    captions_available: bool
    quality_state: Literal["passed", "not_reported", "failed"]
    privacy: Literal["private", "unlisted", "public"] = "private"
    client_configured: bool
    authorized: bool
    auth_detail: str
    existing_video_id: str | None = None
    youtube_url: str | None = None
    blockers: list[str] = Field(default_factory=list)
    can_publish: bool = False


class PublishArtifacts(BaseModel):
    run_id: str
    root: Path
    video: Path
    thumbnail: Path
    subtitles: Path
    metadata: VideoMetadata


class PublishManager:
    """Durable one-click upload jobs with per-stage receipts and duplicate protection."""

    def __init__(self, settings: Settings, store: RunStore) -> None:
        self.settings = settings
        self.store = store
        self.publisher = YouTubePublisher(settings)
        self.root = settings.output_directory.resolve() / ".studio" / "publishing"
        self.jobs_root = self.root / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active_runs: set[str] = set()
        self._oauth_flows: dict[str, tuple[object, datetime]] = {}
        self._recover_jobs()

    def _job_path(self, publish_id: str) -> Path:
        return self.jobs_root / f"{publish_id}.json"

    def _save_job(self, job: PublishJob) -> None:
        atomic_write(self._job_path(job.publish_id), job.model_dump_json(indent=2))

    def _recover_jobs(self) -> None:
        for path in self.jobs_root.glob("*.json"):
            try:
                job = PublishJob.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if job.state in {"queued", "running"}:
                job.state = "failed"
                job.error = "Studio restarted during publishing; retry resumes from its receipt."
                job.message = job.error
                job.finished_at = datetime.now(UTC)
                self._save_job(job)

    def get_job(self, publish_id: str) -> PublishJob | None:
        if not publish_id or any(character not in "0123456789abcdef" for character in publish_id):
            return None
        path = self._job_path(publish_id)
        if not path.is_file():
            return None
        try:
            return PublishJob.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def auth_status(self) -> dict[str, object]:
        return self.publisher.authorization_status()

    def begin_authorization(self, redirect_uri: str) -> dict[str, str]:
        url, state, flow = self.publisher.begin_browser_authorization(redirect_uri)
        with self._lock:
            cutoff = datetime.now(UTC) - timedelta(minutes=10)
            self._oauth_flows = {
                key: value for key, value in self._oauth_flows.items() if value[1] > cutoff
            }
            self._oauth_flows[state] = (flow, datetime.now(UTC))
        return {"authorization_url": url, "state": state}

    def finish_authorization(self, state: str, authorization_response: str) -> None:
        with self._lock:
            entry = self._oauth_flows.pop(state, None)
        if entry is None or entry[1] < datetime.now(UTC) - timedelta(minutes=10):
            raise ConfigurationError("This authorization request expired; start it again in Studio")
        self.publisher.finish_browser_authorization(entry[0], authorization_response)

    @staticmethod
    def _fallback_metadata(run: dict[str, object], settings: Settings) -> VideoMetadata:
        topic = str(run.get("topic") or f"{settings.channel.brand_name} video").strip()
        title = topic[:100]
        brand = settings.channel.brand_name.strip()
        description = (
            f"{topic}\n\n"
            "Watch the complete video for practical context and verify important details "
            "with official sources before making a decision.\n\n"
            f"Produced for {settings.channel.name}. {settings.channel.disclosure}"
        )[:5000]
        tags = [item for item in [brand, settings.channel.name, "explainer", "guide"] if item]
        return VideoMetadata(
            title=title,
            description=description,
            tags=tags,
            hashtags=[f"#{brand.replace(' ', '')}"] if brand else [],
            chapters=[],
            thumbnail_text=title[:70],
            category_id=settings.publishing.category_id,
        )

    def artifacts(self, run: dict[str, object], root: Path) -> PublishArtifacts:
        metadata_file = root / "metadata" / "metadata.json"
        if metadata_file.is_file():
            metadata = VideoMetadata.model_validate_json(metadata_file.read_text(encoding="utf-8"))
        else:
            metadata = self._fallback_metadata(run, self.settings)
        video = root / "final" / "video.mp4"
        raw_thumbnail = run.get("thumbnail")
        thumbnail = (
            Path(str(raw_thumbnail)).resolve()
            if raw_thumbnail
            else root / "thumbnails" / "thumbnail.jpg"
        )
        if root.resolve() not in thumbnail.parents or not thumbnail.is_file():
            candidates = sorted((root / "thumbnails").glob("*.*"))
            thumbnail = candidates[0] if candidates else root / "thumbnails" / "thumbnail.jpg"
        return PublishArtifacts(
            run_id=str(run["run_id"]),
            root=root.resolve(),
            video=video.resolve(),
            thumbnail=thumbnail.resolve(),
            subtitles=(root / "subtitles" / "subtitles.srt").resolve(),
            metadata=metadata,
        )

    def preview(self, run: dict[str, object], root: Path) -> PublishPreview:
        artifacts = self.artifacts(run, root)
        status = self.auth_status()
        report_file = root / "metadata" / "quality_report.json"
        quality_state: Literal["passed", "not_reported", "failed"] = "not_reported"
        if report_file.is_file():
            try:
                report = json.loads(report_file.read_text(encoding="utf-8"))
                quality_state = "passed" if report.get("passed") else "failed"
            except (OSError, json.JSONDecodeError):
                quality_state = "failed"
        receipt = self._load_receipt(artifacts)
        existing_video_id = str(
            receipt.get("video_id") or run.get("youtube_video_id") or ""
        ) or None
        blockers: list[str] = []
        if str(run.get("status")) not in {"ready", "published"}:
            blockers.append("The final render is not ready")
        if not artifacts.video.is_file():
            blockers.append("The final MP4 is missing")
        if not artifacts.thumbnail.is_file():
            blockers.append("The thumbnail is missing")
        if quality_state == "failed":
            blockers.append("The final quality gate did not pass")
        if not status["client_configured"]:
            blockers.append("YouTube OAuth client is not configured")
        elif not status["authorized"]:
            blockers.append("YouTube is not authorized")
        return PublishPreview(
            run_id=artifacts.run_id,
            run_status=str(run.get("status")),
            title=artifacts.metadata.title,
            description=artifacts.metadata.description,
            tags=artifacts.metadata.tags,
            category_id=artifacts.metadata.category_id,
            video_url=f"/api/runs/{artifacts.run_id}/video",
            thumbnail_url=f"/api/runs/{artifacts.run_id}/thumbnail",
            video_bytes=artifacts.video.stat().st_size if artifacts.video.is_file() else 0,
            thumbnail_bytes=(
                artifacts.thumbnail.stat().st_size if artifacts.thumbnail.is_file() else 0
            ),
            captions_available=artifacts.subtitles.is_file(),
            quality_state=quality_state,
            client_configured=bool(status["client_configured"]),
            authorized=bool(status["authorized"]),
            auth_detail=str(status["detail"]),
            existing_video_id=existing_video_id,
            youtube_url=f"https://youtu.be/{existing_video_id}" if existing_video_id else None,
            blockers=blockers,
            can_publish=not blockers,
        )

    def create(
        self,
        run: dict[str, object],
        root: Path,
        submission: PublishSubmission,
    ) -> PublishJob:
        preview = self.preview(run, root)
        hard_blockers = [item for item in preview.blockers if item != "YouTube is not authorized"]
        if hard_blockers:
            raise ConfigurationError("; ".join(hard_blockers))
        if not preview.authorized:
            raise ConfigurationError("Connect YouTube before uploading this package")
        artifacts = self.artifacts(run, root)
        if preview.existing_video_id:
            receipt = self._load_receipt(artifacts)
            if not receipt.get("video_id"):
                receipt["video_id"] = preview.existing_video_id
                receipt["video_uploaded"] = True
                receipt["recovered_from_legacy_receipt"] = True
                self._save_receipt(artifacts, receipt)
        with self._lock:
            if artifacts.run_id in self._active_runs:
                raise RuntimeError("This render already has an upload in progress")
            self._active_runs.add(artifacts.run_id)
        job = PublishJob(
            publish_id=uuid.uuid4().hex[:16],
            run_id=artifacts.run_id,
            message="Validating video, metadata, thumbnail, and captions",
        )
        self._save_job(job)
        threading.Thread(
            target=self._run,
            args=(job, artifacts, submission),
            daemon=True,
            name=f"youtube-publish-{job.publish_id}",
        ).start()
        return job

    def _update_job(self, job: PublishJob, **updates: object) -> None:
        for field, value in updates.items():
            setattr(job, field, value)
        self._save_job(job)

    @staticmethod
    def _receipt_path(artifacts: PublishArtifacts) -> Path:
        return artifacts.root / "metadata" / "youtube_publish.json"

    def _load_receipt(self, artifacts: PublishArtifacts) -> dict[str, object]:
        path = self._receipt_path(artifacts)
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_receipt(self, artifacts: PublishArtifacts, receipt: dict[str, object]) -> None:
        receipt["updated_at"] = datetime.now(UTC).isoformat()
        atomic_write(
            self._receipt_path(artifacts),
            json.dumps(receipt, indent=2, ensure_ascii=False),
        )

    @staticmethod
    def _metadata_fingerprint(
        metadata: VideoMetadata, submission: PublishSubmission
    ) -> str:
        payload = {
            "title": metadata.title,
            "description": metadata.description,
            "tags": metadata.tags,
            "category_id": metadata.category_id,
            "privacy": submission.privacy,
            "publish_at": submission.publish_at.isoformat() if submission.publish_at else None,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def _run(
        self,
        job: PublishJob,
        artifacts: PublishArtifacts,
        submission: PublishSubmission,
    ) -> None:
        try:
            self._update_job(
                job,
                state="running",
                stage="validating",
                progress=2,
                started_at=datetime.now(UTC),
                message="Package validated; preparing YouTube upload",
            )
            metadata = artifacts.metadata.model_copy(
                update={
                    "title": submission.title,
                    "description": submission.description,
                    "tags": submission.tags,
                }
            )
            receipt = self._load_receipt(artifacts)
            fingerprint = self._metadata_fingerprint(metadata, submission)
            video_id = str(receipt.get("video_id") or "")
            if video_id:
                if receipt.get("metadata_fingerprint") != fingerprint:
                    self._update_job(
                        job,
                        stage="metadata",
                        progress=10,
                        message="Updating title, description, tags, and visibility",
                    )
                    self.publisher.update_video_metadata(
                        video_id,
                        metadata,
                        privacy=submission.privacy,
                        publish_at=submission.publish_at,
                    )
                    receipt["metadata_fingerprint"] = fingerprint
                    self._save_receipt(artifacts, receipt)
            else:
                self._update_job(
                    job,
                    stage="video",
                    progress=8,
                    message="Uploading the final MP4 with metadata",
                )

                def report_video_progress(progress: float) -> None:
                    self._update_job(
                        job,
                        progress=8 + round(progress * 67),
                        message=f"Uploading final MP4 · {round(progress * 100)}%",
                    )

                video_id = self.publisher.upload_video(
                    artifacts.video,
                    metadata,
                    privacy=submission.privacy,
                    publish_at=submission.publish_at,
                    on_progress=report_video_progress,
                )
                receipt.update(
                    {
                        "video_id": video_id,
                        "video_uploaded": True,
                        "metadata_fingerprint": fingerprint,
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                )
                self._save_receipt(artifacts, receipt)
                atomic_write(artifacts.root / "metadata" / "youtube_video_id.txt", video_id)

            if (
                submission.upload_thumbnail
                and artifacts.thumbnail.is_file()
                and not receipt.get("thumbnail_uploaded")
            ):
                self._update_job(
                    job,
                    stage="thumbnail",
                    progress=82,
                    message="Setting the custom thumbnail",
                )
                self.publisher.upload_thumbnail(video_id, artifacts.thumbnail)
                receipt["thumbnail_uploaded"] = True
                self._save_receipt(artifacts, receipt)

            if (
                submission.upload_captions
                and artifacts.subtitles.is_file()
                and not receipt.get("captions_uploaded")
            ):
                self._update_job(
                    job,
                    stage="captions",
                    progress=91,
                    message="Uploading the timed caption track",
                )
                self.publisher.upload_captions(video_id, artifacts.subtitles)
                receipt["captions_uploaded"] = True
                self._save_receipt(artifacts, receipt)

            receipt["package_completed"] = True
            self._save_receipt(artifacts, receipt)
            current = self.store.get_run(artifacts.run_id)
            if current is not None:
                manifest = RunManifest.model_validate(current)
                manifest.youtube_video_id = video_id
                manifest.status = RunStatus.published
                self.store.save_manifest(manifest)
                atomic_write(artifacts.root / "manifest.json", manifest.model_dump_json(indent=2))
            youtube_url = f"https://youtu.be/{video_id}"
            self._update_job(
                job,
                state="completed",
                stage="complete",
                progress=100,
                message="YouTube package completed without duplicate uploads",
                video_id=video_id,
                youtube_url=youtube_url,
                finished_at=datetime.now(UTC),
            )
        except Exception as exc:
            self._update_job(
                job,
                state="failed",
                message=f"Upload paused safely: {exc}",
                error=str(exc),
                finished_at=datetime.now(UTC),
            )
        finally:
            with self._lock:
                self._active_runs.discard(artifacts.run_id)
