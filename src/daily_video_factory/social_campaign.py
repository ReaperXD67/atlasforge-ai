"""Durable, explicitly executed publication queue for verified production episodes."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import re
import socket
import sqlite3
import ssl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PureWindowsPath
from typing import Any, Literal
from urllib.parse import urlsplit

import portalocker
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import Settings
from .exceptions import ConfigurationError, ProviderFailed
from .models import VideoMetadata
from .production_batch import load_production_batch_manifest, verify_production_episode
from .publishing.meta import (
    MetaProcessingPending,
    MetaPublisher,
    MetaPublishUncertain,
    _validate_media_url,
)
from .publishing.youtube import YouTubePublisher
from .quality import PROHIBITED_PATTERNS, _contains_unqualified_claim


class CampaignPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    episode_id: str = Field(min_length=1)
    platform: Literal["youtube", "instagram", "facebook"]
    account_id: str = Field(min_length=1, max_length=100)
    publish_at: datetime
    caption: str = Field(min_length=1, max_length=5000)
    video_url: str | None = None
    privacy: Literal["private", "unlisted", "public"] = "private"
    subtitles: str | None = None

    @field_validator("publish_at")
    @classmethod
    def aware_schedule(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("publish_at must include a timezone offset")
        return value.astimezone(UTC)

    @field_validator("caption")
    @classmethod
    def validate_caption(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("caption cannot be blank")
        for label, pattern in PROHIBITED_PATTERNS.items():
            if _contains_unqualified_claim(value, pattern):
                raise ValueError(f"caption contains a prohibited {label}")
        return value.strip()


class Campaign(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    campaign_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    production_manifest: str
    posts: list[CampaignPost] = Field(min_length=1, max_length=500)


def load_campaign(path: Path) -> Campaign:
    """Parse a campaign without media verification or any remote effects."""
    try:
        campaign = Campaign.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        raise ConfigurationError(
            "Campaign JSON is invalid; check required fields, explicit timezone offsets, and caption policy."
        ) from None
    if len({post.id for post in campaign.posts}) != len(campaign.posts):
        raise ConfigurationError("Campaign post IDs must be unique.")
    return campaign


def _relative(root: Path, value: str) -> Path:
    windows = PureWindowsPath(value)
    if Path(value).is_absolute() or windows.drive or windows.root:
        raise ConfigurationError("Campaign file references must be repository-relative.")
    path = (root / value.replace("\\", "/")).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ConfigurationError("Campaign file reference escapes the repository.")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _section(markdown: str, name: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(name)}\s*$\n(.*?)(?=^##\s+|\Z)", markdown, re.I | re.M | re.S
    )
    return match.group(1).strip() if match else ""


def _clock(value: datetime | None = None) -> datetime:
    value = value or datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ConfigurationError("Worker time must include a timezone.")
    return value.astimezone(UTC)


class SocialCampaignManager:
    def __init__(
        self, settings: Settings, repository_root: Path, database: Path | None = None
    ) -> None:
        self.settings = settings
        self.root = repository_root.resolve()
        self.database = (database or self.root / "output/social/queue.sqlite").resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.youtube = YouTubePublisher(settings)
        self.meta = MetaPublisher()
        self.max_attempts = 8
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS social_posts (
                post_key TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, post_id TEXT NOT NULL,
                platform TEXT NOT NULL, account_id TEXT NOT NULL, publish_at TEXT NOT NULL,
                payload TEXT NOT NULL, fingerprint TEXT NOT NULL, video_sha256 TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT, error TEXT, receipt TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(platform, account_id, video_sha256)
            )""")

    def close(self) -> None:
        self.meta.close()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database, timeout=5)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        # Payload may contain a signed media URL. It never appears in status output.
        allowed = (
            "post_key",
            "campaign_id",
            "post_id",
            "platform",
            "account_id",
            "publish_at",
            "state",
            "attempts",
            "next_attempt_at",
            "error",
            "created_at",
            "updated_at",
        )
        result = {key: row[key] for key in allowed}
        receipt = json.loads(row["receipt"])
        for key in ("video_id", "media_id", "container_id", "privacy"):
            if receipt.get(key):
                result[key] = receipt[key]
        return result

    def list_posts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [
                self._public(row)
                for row in conn.execute("SELECT * FROM social_posts ORDER BY publish_at,post_key")
            ]

    def _inspect(
        self, production_manifest: str, post: CampaignPost, *, as_of: datetime | None = None
    ) -> dict[str, Any]:
        manifest_path = _relative(self.root, production_manifest)
        manifest = load_production_batch_manifest(manifest_path, repository_root=self.root)
        episode = next((item for item in manifest.episodes if item.id == post.episode_id), None)
        if episode is None:
            raise ConfigurationError("Campaign episode is not in the production manifest.")
        if post.platform != "youtube" and episode.format != "shorts":
            raise ConfigurationError(
                "Meta campaign posts require a verified vertical Shorts episode."
            )
        if post.platform != "youtube":
            if post.privacy != "public":
                raise ConfigurationError(
                    "Meta Reels are public; set privacy='public' explicitly for a Meta campaign post."
                )
            if not re.fullmatch(r"\d+", post.account_id):
                raise ConfigurationError("Meta campaign account_id must be numeric.")
            if not post.video_url:
                raise ConfigurationError("Meta posts require a hosted video_url.")
            _validate_media_url(post.video_url)
        elif not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", post.account_id):
            raise ConfigurationError("YouTube account_id must be the UC-prefixed channel ID.")
        report = verify_production_episode(episode)
        if post.platform == "facebook" and not 4 <= report["duration_seconds"] <= 60:
            raise ConfigurationError(
                "Facebook queue currently supports the verified 4–60 second Reels contract."
            )
        editorial = json.loads(episode.editorial_manifest.read_text(encoding="utf-8-sig"))
        today = _clock(as_of).date()
        for source in editorial["sources"]:
            age_days = (today - date.fromisoformat(source["checked_on"])).days
            if age_days < 0 or age_days > self.settings.research.max_official_source_age_days:
                raise ConfigurationError(
                    "Editorial evidence is future-dated or stale; refresh and verify its source before publication."
                )
        files = [
            manifest.path,
            episode.output,
            episode.thumbnail,
            episode.upload_package,
            episode.voice_manifest,
            episode.editorial_manifest,
        ]
        for field in ("script", "thumbnail_copy"):
            files.append(_relative(episode.project, editorial[field]))
        script = _relative(episode.project, editorial["script"]).read_text(encoding="utf-8-sig")
        for label, pattern in PROHIBITED_PATTERNS.items():
            if _contains_unqualified_claim(script, pattern):
                raise ConfigurationError(f"Production script contains a prohibited {label}.")
        if "story" in editorial:
            files.append(_relative(episode.project, editorial["story"]["timing_manifest"]))
        subtitles = _relative(self.root, post.subtitles) if post.subtitles else None
        if subtitles:
            files.append(subtitles)
        if (
            post.platform == "youtube"
            and self.settings.publishing.upload_caption_track
            and not subtitles
        ):
            raise ConfigurationError(
                "Caption upload is enabled; configure this post's subtitles path."
            )
        hashes = {
            str(path.relative_to(self.root)).replace("\\", "/"): _sha256(path) for path in files
        }
        markdown = episode.upload_package.read_text(encoding="utf-8-sig")
        hashtags = list(dict.fromkeys(re.findall(r"(?<!\w)#[A-Za-z0-9_]+", markdown)))[:15]
        description = "\n\n".join(
            [
                post.caption,
                _section(markdown, "Description"),
                " ".join(hashtags),
                "Disclosure: AI-generated narration.",
            ]
        )
        if len(description) > 5000:
            raise ConfigurationError(
                "Combined campaign caption, verified description, and disclosure exceed YouTube's description limit."
            )
        for label, pattern in PROHIBITED_PATTERNS.items():
            if _contains_unqualified_claim(
                report["metadata"]["title"] + "\n" + description, pattern
            ):
                raise ConfigurationError(f"Publication metadata contains a prohibited {label}.")
        metadata = VideoMetadata(
            title=report["metadata"]["title"],
            description=description,
            tags=[tag.lstrip("#") for tag in hashtags],
            hashtags=hashtags,
            chapters=[],
            thumbnail_text=editorial["packaging"]["thumbnail_text"],
            category_id=self.settings.publishing.category_id,
        )
        social_caption = post.caption + "\n\nDisclosure: AI-generated narration."
        if post.platform == "instagram" and len(social_caption) > 2200:
            raise ConfigurationError(
                "Instagram caption plus AI disclosure exceeds 2200 characters."
            )
        if post.platform == "facebook" and len(social_caption) > 5000:
            raise ConfigurationError(
                "Facebook caption plus AI disclosure exceeds the application's 5000-character limit."
            )
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "files": hashes,
                    "post": post.model_dump(mode="json"),
                    "production_manifest": production_manifest,
                    "settings": self.settings.model_dump(mode="json"),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return {
            "episode": episode,
            "metadata": metadata,
            "subtitles": subtitles,
            "fingerprint": fingerprint,
            "video_sha256": _sha256(episode.output),
            "social_caption": social_caption,
        }

    def enqueue(self, campaign_path: Path) -> list[dict[str, Any]]:
        campaign = load_campaign(campaign_path)
        prepared = [
            (post, self._inspect(campaign.production_manifest, post)) for post in campaign.posts
        ]
        results = []
        now = _clock().isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for post, inspected in prepared:
                key = f"{campaign.campaign_id}:{post.id}"
                existing = conn.execute(
                    "SELECT * FROM social_posts WHERE post_key=?", (key,)
                ).fetchone()
                if existing and existing["fingerprint"] != inspected["fingerprint"]:
                    raise ConfigurationError(
                        "An enqueued post changed. Use a new post ID; existing publication records are immutable."
                    )
                if existing:
                    results.append(self._public(existing))
                    continue
                duplicate = conn.execute(
                    "SELECT * FROM social_posts WHERE platform=? AND account_id=? AND video_sha256=?",
                    (post.platform, post.account_id, inspected["video_sha256"]),
                ).fetchone()
                if duplicate:
                    results.append({**self._public(duplicate), "deduplicated": True})
                    continue
                payload = json.dumps(
                    {
                        "production_manifest": campaign.production_manifest,
                        "post": post.model_dump(mode="json"),
                    }
                )
                conn.execute(
                    """INSERT INTO social_posts
                    (post_key,campaign_id,post_id,platform,account_id,publish_at,payload,fingerprint,video_sha256,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        key,
                        campaign.campaign_id,
                        post.id,
                        post.platform,
                        post.account_id,
                        post.publish_at.isoformat(),
                        payload,
                        inspected["fingerprint"],
                        inspected["video_sha256"],
                        now,
                        now,
                    ),
                )
                results.append(
                    self._public(
                        conn.execute(
                            "SELECT * FROM social_posts WHERE post_key=?", (key,)
                        ).fetchone()
                    )
                )
        return results

    def _update(self, key: str, **updates: Any) -> dict[str, Any]:
        allowed = {"state", "attempts", "next_attempt_at", "error", "receipt"}
        if set(updates) - allowed:
            raise ValueError("Unexpected queue update field")
        updates["updated_at"] = _clock().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE social_posts SET "
                + ",".join(f"{name}=?" for name in updates)
                + " WHERE post_key=?",
                (*updates.values(), key),
            )
            row = conn.execute("SELECT * FROM social_posts WHERE post_key=?", (key,)).fetchone()
            return self._public(row)

    def retry_blocked(self, post_key: str) -> dict[str, Any]:
        with (
            portalocker.Lock(str(self.database) + ".worker.lock", timeout=0),
            self._connect() as conn,
        ):
            row = conn.execute(
                "SELECT * FROM social_posts WHERE post_key=?", (post_key,)
            ).fetchone()
            if not row or row["state"] != "blocked":
                raise ConfigurationError(
                    "Only a blocked post can be retried; uncertain outcomes require external reconciliation."
                )
            return self._update(
                post_key, state="pending", attempts=0, error=None, next_attempt_at=None
            )

    def _account_ready(self, post: CampaignPost, *, live: bool) -> None:
        if post.platform == "youtube":
            if not self.youtube.authorization_status().get("authorized"):
                raise ConfigurationError("YouTube is not authorized.")
            if live:
                service = self.youtube.authenticate(interactive=False)
                response = service.channels().list(part="id", mine=True).execute()
                if {item.get("id") for item in response.get("items", [])} != {post.account_id}:
                    raise ConfigurationError(
                        "Authorized YouTube channel does not match the campaign account_id."
                    )
        else:
            self.meta.config.validate(post.platform)
            actual = (
                self.meta.config.instagram_account_id
                if post.platform == "instagram"
                else self.meta.config.page_id
            )
            if actual != post.account_id:
                raise ConfigurationError(
                    "Meta account configuration does not match the campaign account_id."
                )

    def _verify_remote_media(self, url: str, video: Path, expected_hash: str) -> None:
        _validate_media_url(url)
        host = urlsplit(url).hostname or ""
        # Resolve and reject private addresses before fetching user-configured URLs.
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError:
            raise ProviderFailed("Hosted media DNS lookup failed.") from None
        if not addresses or any(
            not ipaddress.ip_address(item[4][0]).is_global for item in addresses
        ):
            raise ConfigurationError("Hosted media must resolve only to public internet addresses.")
        digest = hashlib.sha256()
        total = 0
        maximum = video.stat().st_size
        parsed = urlsplit(url)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        connection = http.client.HTTPSConnection(
            host, timeout=30, context=ssl.create_default_context()
        )
        raw_socket = None
        started = time.monotonic()
        try:
            # Pin the checked IP to avoid a second DNS lookup/rebinding. TLS still
            # verifies the original hostname and the HTTP Host header uses it.
            raw_socket = socket.create_connection((str(addresses[0][4][0]), 443), timeout=30)
            connection.sock = ssl.create_default_context().wrap_socket(
                raw_socket, server_hostname=host
            )
            connection.sock.settimeout(60)
            connection.request(
                "GET",
                target,
                headers={"Accept-Encoding": "identity", "User-Agent": "AtlasForge-MediaVerifier/1"},
            )
            response = connection.getresponse()
            if response.status != 200:
                raise ProviderFailed(
                    f"Hosted media fetch failed (HTTP {response.status}); use a direct file URL."
                )
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > maximum:
                    raise ConfigurationError(
                        "Hosted media bytes do not match the verified local video."
                    )
                if time.monotonic() - started > 300:
                    raise ProviderFailed(
                        "Hosted media verification exceeded its five-minute limit."
                    )
                digest.update(chunk)
        except (OSError, http.client.HTTPException):
            raise ProviderFailed(
                "Hosted media download failed; URL and credentials omitted."
            ) from None
        finally:
            connection.close()
            if raw_socket is not None:
                raw_socket.close()
        if total != maximum or digest.hexdigest() != expected_hash:
            raise ConfigurationError("Hosted media bytes do not match the verified local video.")

    def _youtube_publish(
        self, row: sqlite3.Row, post: CampaignPost, inspected: dict[str, Any]
    ) -> dict[str, Any]:
        key = row["post_key"]
        receipt = json.loads(row["receipt"])
        episode = inspected["episode"]
        if not receipt.get("video_id"):
            self._update(
                key,
                state="uploading",
                receipt=json.dumps({"upload_started": True, "privacy": post.privacy}),
            )
            try:
                video_id = self.youtube.upload_video(
                    episode.output, inspected["metadata"], privacy=post.privacy
                )
                if not isinstance(video_id, str) or not re.fullmatch(
                    r"[A-Za-z0-9_-]{6,32}", video_id
                ):
                    raise ProviderFailed("YouTube returned no valid video ID.")
            except Exception:
                raise MetaPublishUncertain(
                    "YouTube upload outcome is uncertain; inspect the channel before resolving this record."
                ) from None
            receipt = {"video_id": video_id, "privacy": post.privacy}
            self._update(key, state="pending", receipt=json.dumps(receipt))
        # Shorts covers are selected through supported YouTube surfaces. A 9:16
        # production thumbnail is not submitted as a long-form custom thumbnail.
        if (
            self.settings.publishing.upload_thumbnail
            and episode.format == "youtube"
            and not receipt.get("thumbnail_uploaded")
        ):
            self.youtube.upload_thumbnail(receipt["video_id"], episode.thumbnail)
            receipt["thumbnail_uploaded"] = True
            self._update(key, receipt=json.dumps(receipt))
        if self.settings.publishing.upload_caption_track and not receipt.get("captions_uploaded"):
            self._update(
                key,
                state="uploading",
                receipt=json.dumps({**receipt, "caption_upload_started": True}),
            )
            try:
                self.youtube.upload_captions(receipt["video_id"], inspected["subtitles"])
            except Exception:
                raise MetaPublishUncertain(
                    "YouTube caption upload outcome is uncertain; the saved video will not be uploaded again."
                ) from None
            receipt["captions_uploaded"] = True
            self._update(key, state="pending", receipt=json.dumps(receipt))
        return receipt

    def _publish(
        self, row: sqlite3.Row, post: CampaignPost, inspected: dict[str, Any]
    ) -> dict[str, Any]:
        if post.platform == "youtube":
            return self._youtube_publish(row, post, inspected)
        self._verify_remote_media(
            post.video_url or "", inspected["episode"].output, row["video_sha256"]
        )
        receipt_name = hashlib.sha256(row["post_key"].encode()).hexdigest() + ".json"
        receipt_path = self.database.parent / "receipts" / receipt_name
        if post.platform == "instagram":
            return self.meta.publish_instagram(
                post.video_url or "", inspected["social_caption"], receipt_path
            )
        return self.meta.publish_facebook(
            post.video_url or "",
            inspected["social_caption"],
            receipt_path,
            title=inspected["metadata"].title,
        )

    def run_due(
        self, *, execute: bool = False, now: datetime | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        current = _clock(now)
        if not 1 <= limit <= 50:
            raise ConfigurationError("Worker limit must be between 1 and 50.")
        results: list[dict[str, Any]] = []
        with portalocker.Lock(str(self.database) + ".worker.lock", timeout=0):
            if execute:
                with self._connect() as conn:
                    interrupted = conn.execute(
                        "SELECT post_key FROM social_posts WHERE state='uploading'"
                    ).fetchall()
                    conn.execute(
                        "UPDATE social_posts SET state='uncertain',error='Interrupted YouTube mutation; external reconciliation required',updated_at=? WHERE state='uploading'",
                        (current.isoformat(),),
                    )
                    for item in interrupted:
                        results.append(self._public(conn.execute(
                            "SELECT * FROM social_posts WHERE post_key=?", (item["post_key"],)
                        ).fetchone()))
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT * FROM social_posts WHERE state='pending' AND publish_at<=?
                    AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY publish_at,post_key LIMIT ?""",
                    (current.isoformat(), current.isoformat(), limit),
                ).fetchall()
            for row in rows:
                key = row["post_key"]
                attempts = row["attempts"] + 1
                try:
                    payload = json.loads(row["payload"])
                    post = CampaignPost.model_validate(payload["post"])
                    inspected = self._inspect(payload["production_manifest"], post, as_of=current)
                    if inspected["fingerprint"] != row["fingerprint"]:
                        raise ConfigurationError(
                            "Queued artifacts or publishing settings changed after enqueue; publication is blocked."
                        )
                    self._account_ready(post, live=execute)
                    if not execute:
                        results.append(
                            {
                                **self._public(row),
                                "dry_run": True,
                                "readiness": "would_publish",
                                "live_checks_pending": True,
                            }
                        )
                        continue
                    self._update(key, attempts=attempts, error=None)
                    receipt = self._publish(row, post, inspected)
                    if post.platform != "youtube" and receipt.get("published") is not True:
                        raise MetaProcessingPending("Meta publication is not confirmed.")
                    results.append(
                        self._update(
                            key,
                            state="published",
                            receipt=json.dumps(receipt),
                            error=None,
                            next_attempt_at=None,
                        )
                    )
                except MetaPublishUncertain:
                    if execute:
                        results.append(
                            self._update(
                                key,
                                state="uncertain",
                                attempts=attempts,
                                error="Remote mutation outcome is uncertain; no automatic replay.",
                                next_attempt_at=None,
                            )
                        )
                    else:
                        results.append(
                            {
                                **self._public(row),
                                "dry_run": True,
                                "readiness": "blocked",
                                "error": "Uncertain remote state.",
                            }
                        )
                except (ConfigurationError, ValueError, OSError) as exc:
                    # Known local/config failures cannot expose upstream token-bearing error text.
                    detail = (
                        str(exc)
                        if isinstance(exc, ConfigurationError)
                        else "Local production verification failed; inspect the source package."
                    )
                    if execute:
                        results.append(
                            self._update(
                                key,
                                state="blocked",
                                attempts=attempts,
                                error=detail,
                                next_attempt_at=None,
                            )
                        )
                    else:
                        results.append(
                            {
                                **self._public(row),
                                "dry_run": True,
                                "readiness": "blocked",
                                "error": detail,
                            }
                        )
                except Exception as exc:
                    detail = (
                        "Remote processing is pending."
                        if isinstance(exc, MetaProcessingPending)
                        else "Provider/read operation failed; credentials and remote response omitted."
                    )
                    if execute:
                        blocked = attempts >= self.max_attempts
                        retry_at = (
                            None
                            if blocked
                            else (
                                current + timedelta(seconds=min(300 * 2 ** (attempts - 1), 3600))
                            ).isoformat()
                        )
                        results.append(
                            self._update(
                                key,
                                state="blocked" if blocked else "pending",
                                attempts=attempts,
                                error=detail,
                                next_attempt_at=retry_at,
                            )
                        )
                    else:
                        results.append(
                            {
                                **self._public(row),
                                "dry_run": True,
                                "readiness": "blocked",
                                "error": detail,
                            }
                        )
        return results
