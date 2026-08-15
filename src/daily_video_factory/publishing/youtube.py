from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import Settings
from ..exceptions import ConfigurationError, ProviderFailed
from ..models import VideoMetadata

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class YouTubePublisher:
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

    def authenticate(self, interactive: bool = True):
        Request, Credentials, InstalledAppFlow, build, _ = self._imports()
        if not self.client_secrets.exists():
            raise ConfigurationError(
                f"YouTube OAuth client file not found: {self.client_secrets.resolve()}"
            )
        credentials = None
        if self.token_file.exists():
            credentials = Credentials.from_authorized_user_file(
                str(self.token_file), [YOUTUBE_UPLOAD_SCOPE]
            )
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            if not interactive:
                raise ConfigurationError(
                    "YouTube authorization is required; run atlasforge youtube-auth"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secrets), [YOUTUBE_UPLOAD_SCOPE]
            )
            credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def upload(
        self,
        video: Path,
        thumbnail: Path,
        subtitles: Path,
        metadata: VideoMetadata,
        publication_date: date,
    ) -> str:
        _, _, _, _, MediaFileUpload = self._imports()
        youtube = self.authenticate(interactive=False)
        privacy = self.settings.schedule.upload_privacy
        status: dict[str, object] = {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": self.settings.publishing.made_for_kids,
            "containsSyntheticMedia": self.settings.publishing.contains_synthetic_media,
        }
        if privacy == "private" and self.settings.schedule.publish_hour >= 0:
            local = datetime(
                publication_date.year,
                publication_date.month,
                publication_date.day,
                self.settings.schedule.publish_hour,
                tzinfo=ZoneInfo(self.settings.channel.timezone),
            )
            if local > datetime.now(ZoneInfo(self.settings.channel.timezone)):
                status["publishAt"] = (
                    local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")
                )
        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
                "defaultLanguage": self.settings.channel.language,
            },
            "status": status,
        }
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(
                str(video), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024
            ),
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        video_id = response.get("id")
        if not video_id:
            raise ProviderFailed(
                f"YouTube upload returned no video id: {json.dumps(response)[:1000]}"
            )
        if self.settings.publishing.upload_thumbnail and thumbnail.exists():
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg"),
            ).execute()
        if self.settings.publishing.upload_caption_track and subtitles.exists():
            youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": self.settings.channel.language,
                        "name": "English",
                        "isDraft": False,
                    }
                },
                media_body=MediaFileUpload(str(subtitles), mimetype="application/octet-stream"),
            ).execute()
        return str(video_id)
