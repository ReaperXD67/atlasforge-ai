from __future__ import annotations

import json
import mimetypes
import os
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..artifacts import atomic_write
from ..config import Settings
from ..exceptions import ConfigurationError, ProviderFailed
from ..models import VideoMetadata

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_CAPTION_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_SCOPES = (YOUTUBE_UPLOAD_SCOPE, YOUTUBE_CAPTION_SCOPE)


class YouTubePublisher:
    """YouTube Data API adapter with browser OAuth and independently retryable stages."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client_secrets = Path(
            os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "secrets/youtube_client_secret.json")
        )
        self.token_file = Path(os.getenv("YOUTUBE_TOKEN_FILE", "secrets/youtube_token.json"))

    def _imports(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            return Request, Credentials, InstalledAppFlow, build, MediaFileUpload
        except ImportError as exc:
            raise ConfigurationError(
                "Install the youtube extra: pip install -e '.[youtube]'"
            ) from exc

    def authorization_status(self) -> dict[str, object]:
        configured = self.client_secrets.is_file()
        token_present = self.token_file.is_file()
        status: dict[str, object] = {
            "client_configured": configured,
            "token_present": token_present,
            "authorized": False,
            "detail": "Add a YouTube Desktop OAuth client to continue.",
        }
        try:
            _, Credentials, _, _, _ = self._imports()
        except ConfigurationError as exc:
            status["detail"] = str(exc)
            return status
        if not configured:
            return status
        status["detail"] = "Authorize this local Studio once in your browser."
        if not token_present:
            return status
        try:
            credentials = Credentials.from_authorized_user_file(
                str(self.token_file), list(YOUTUBE_SCOPES)
            )
        except (OSError, ValueError, json.JSONDecodeError):
            status["detail"] = "The saved YouTube authorization is unreadable; authorize again."
            return status
        has_scopes = credentials.has_scopes(YOUTUBE_SCOPES)
        refreshable = bool(credentials.refresh_token)
        status["authorized"] = bool(has_scopes and (credentials.valid or refreshable))
        status["detail"] = (
            "YouTube is connected and ready."
            if status["authorized"]
            else "Authorization is missing the upload/caption permissions; authorize again."
        )
        return status

    def _save_credentials(self, credentials: Any) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.token_file, credentials.to_json())

    def authenticate(self, interactive: bool = True):
        Request, Credentials, InstalledAppFlow, build, _ = self._imports()
        if not self.client_secrets.exists():
            raise ConfigurationError(
                f"YouTube OAuth client file not found: {self.client_secrets.resolve()}"
            )
        credentials = None
        if self.token_file.exists():
            credentials = Credentials.from_authorized_user_file(
                str(self.token_file), list(YOUTUBE_SCOPES)
            )
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        has_scopes = bool(credentials and credentials.has_scopes(YOUTUBE_SCOPES))
        if not credentials or not credentials.valid or not has_scopes:
            if not interactive:
                raise ConfigurationError(
                    "YouTube authorization is required; connect YouTube in AtlasForge Studio"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secrets), list(YOUTUBE_SCOPES)
            )
            credentials = flow.run_local_server(
                host="127.0.0.1", port=0, access_type="offline", prompt="consent"
            )
        self._save_credentials(credentials)
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def begin_browser_authorization(self, redirect_uri: str) -> tuple[str, str, Any]:
        _, _, InstalledAppFlow, _, _ = self._imports()
        if not self.client_secrets.is_file():
            raise ConfigurationError(
                f"YouTube OAuth client file not found: {self.client_secrets.resolve()}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secrets),
            list(YOUTUBE_SCOPES),
            redirect_uri=redirect_uri,
            autogenerate_code_verifier=True,
        )
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        return authorization_url, state, flow

    def finish_browser_authorization(self, flow: Any, authorization_response: str) -> None:
        flow.fetch_token(authorization_response=authorization_response)
        self._save_credentials(flow.credentials)

    def _status_body(
        self, privacy: str, publish_at: datetime | None
    ) -> dict[str, object]:
        status: dict[str, object] = {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": self.settings.publishing.made_for_kids,
            "containsSyntheticMedia": self.settings.publishing.contains_synthetic_media,
        }
        if publish_at is not None:
            status["privacyStatus"] = "private"
            status["publishAt"] = publish_at.isoformat().replace("+00:00", "Z")
        return status

    def _video_body(
        self, metadata: VideoMetadata, privacy: str, publish_at: datetime | None
    ) -> dict[str, object]:
        return {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
                "defaultLanguage": self.settings.channel.language,
            },
            "status": self._status_body(privacy, publish_at),
        }

    def upload_video(
        self,
        video: Path,
        metadata: VideoMetadata,
        *,
        privacy: str,
        publish_at: datetime | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> str:
        _, _, _, _, MediaFileUpload = self._imports()
        youtube = self.authenticate(interactive=False)
        request = youtube.videos().insert(
            part="snippet,status",
            body=self._video_body(metadata, privacy, publish_at),
            media_body=MediaFileUpload(
                str(video), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024
            ),
        )
        response = None
        while response is None:
            chunk_status, response = request.next_chunk()
            if chunk_status is not None and on_progress is not None:
                on_progress(float(chunk_status.progress()))
        video_id = response.get("id")
        if not video_id:
            raise ProviderFailed(
                f"YouTube upload returned no video id: {json.dumps(response)[:1000]}"
            )
        if on_progress is not None:
            on_progress(1.0)
        return str(video_id)

    def update_video_metadata(
        self,
        video_id: str,
        metadata: VideoMetadata,
        *,
        privacy: str,
        publish_at: datetime | None = None,
    ) -> None:
        youtube = self.authenticate(interactive=False)
        youtube.videos().update(
            part="snippet,status",
            body={"id": video_id, **self._video_body(metadata, privacy, publish_at)},
        ).execute()

    def upload_thumbnail(self, video_id: str, thumbnail: Path) -> None:
        _, _, _, _, MediaFileUpload = self._imports()
        youtube = self.authenticate(interactive=False)
        mime = mimetypes.guess_type(thumbnail.name)[0] or "image/jpeg"
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail), mimetype=mime),
        ).execute()

    def upload_captions(self, video_id: str, subtitles: Path) -> None:
        _, _, _, _, MediaFileUpload = self._imports()
        youtube = self.authenticate(interactive=False)
        language = self.settings.channel.language
        youtube.captions().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "language": language,
                    "name": f"{language.upper()} captions",
                    "isDraft": False,
                }
            },
            media_body=MediaFileUpload(
                str(subtitles), mimetype="application/octet-stream", resumable=True
            ),
        ).execute()

    def upload(
        self,
        video: Path,
        thumbnail: Path,
        subtitles: Path,
        metadata: VideoMetadata,
        publication_date: date,
    ) -> str:
        """Backward-compatible CLI path. Studio uses the checkpointed package manager."""
        metadata_root = video.parent.parent / "metadata"
        receipt_file = metadata_root / "youtube_publish.json"
        id_file = metadata_root / "youtube_video_id.txt"
        receipt: dict[str, object] = {}
        if receipt_file.is_file():
            try:
                receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                receipt = {}
        if not receipt.get("video_id") and id_file.is_file():
            receipt["video_id"] = id_file.read_text(encoding="utf-8").strip()

        def save_receipt() -> None:
            receipt["updated_at"] = datetime.now(ZoneInfo("UTC")).isoformat()
            atomic_write(receipt_file, json.dumps(receipt, indent=2, ensure_ascii=False))

        publish_at = None
        if self.settings.schedule.upload_privacy == "private":
            local = datetime(
                publication_date.year,
                publication_date.month,
                publication_date.day,
                self.settings.schedule.publish_hour,
                tzinfo=ZoneInfo(self.settings.channel.timezone),
            )
            if local > datetime.now(ZoneInfo(self.settings.channel.timezone)):
                publish_at = local.astimezone(ZoneInfo("UTC"))
        video_id = str(receipt.get("video_id") or "")
        if video_id:
            self.update_video_metadata(
                video_id,
                metadata,
                privacy=self.settings.schedule.upload_privacy,
                publish_at=publish_at,
            )
        else:
            video_id = self.upload_video(
                video,
                metadata,
                privacy=self.settings.schedule.upload_privacy,
                publish_at=publish_at,
            )
            receipt["video_id"] = video_id
            receipt["video_uploaded"] = True
            save_receipt()
            atomic_write(id_file, video_id)
        if (
            self.settings.publishing.upload_thumbnail
            and thumbnail.exists()
            and not receipt.get("thumbnail_uploaded")
        ):
            self.upload_thumbnail(video_id, thumbnail)
            receipt["thumbnail_uploaded"] = True
            save_receipt()
        if (
            self.settings.publishing.upload_caption_track
            and subtitles.exists()
            and not receipt.get("captions_uploaded")
        ):
            self.upload_captions(video_id, subtitles)
            receipt["captions_uploaded"] = True
            save_receipt()
        receipt["package_completed"] = True
        save_receipt()
        return video_id
