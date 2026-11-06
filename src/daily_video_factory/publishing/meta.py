"""Meta Reels publishing via the official Facebook Login/Page token API.

Only GET requests are retried. A lost mutation response is reconciled against a
saved remote ID, never replayed blindly. Receipts contain no tokens or media URLs.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import portalocker

from ..artifacts import atomic_write
from ..exceptions import ConfigurationError, ProviderFailed


class MetaProcessingPending(ProviderFailed):
    """Remote processing continues; retry later using the SAME receipt."""


class MetaPublishUncertain(ProviderFailed):
    """A mutation may have succeeded; reconciliation is required before retry."""


@dataclass(frozen=True)
class MetaConfig:
    graph_version: str = ""
    page_id: str = ""
    instagram_account_id: str = ""
    page_access_token: str = field(default="", repr=False)
    poll_attempts: int = 12
    poll_interval_seconds: float = 5.0
    get_attempts: int = 3

    @classmethod
    def from_env(cls) -> MetaConfig:
        return cls(
            graph_version=os.getenv("META_GRAPH_VERSION", "").strip(),
            page_id=os.getenv("META_PAGE_ID", "").strip(),
            instagram_account_id=os.getenv("META_INSTAGRAM_ACCOUNT_ID", "").strip(),
            page_access_token=os.getenv("META_PAGE_ACCESS_TOKEN", "").strip(),
        )

    def validate(self, platform: str) -> None:
        if not re.fullmatch(r"v\d+\.\d+", self.graph_version):
            raise ConfigurationError(
                "Set META_GRAPH_VERSION to the supported version in your Meta app (vNN.N)."
            )
        if not self.page_access_token:
            raise ConfigurationError(
                "Set META_PAGE_ACCESS_TOKEN through a local secret store or environment."
            )
        account = self.instagram_account_id if platform == "instagram" else self.page_id
        if not re.fullmatch(r"\d+", account):
            name = "META_INSTAGRAM_ACCOUNT_ID" if platform == "instagram" else "META_PAGE_ID"
            raise ConfigurationError(f"Set {name} to the numeric account ID.")
        if not 1 <= self.poll_attempts <= 120 or not 1 <= self.get_attempts <= 5:
            raise ConfigurationError("Meta polling/read retry attempts are out of bounds.")
        if not 0 <= self.poll_interval_seconds <= 60:
            raise ConfigurationError("Meta poll interval must be between 0 and 60 seconds.")


def _validate_media_url(value: str) -> None:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        invalid = (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.port not in (None, 443)
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
            or "." not in host
            or any(c.isspace() for c in value)
        )
        with suppress(ValueError):
            invalid = invalid or not ipaddress.ip_address(host).is_global
    except ValueError:
        invalid = True
    if invalid:
        raise ConfigurationError(
            "Reels need an accessible public HTTPS media URL without embedded credentials."
        )


class MetaPublisher:
    def __init__(
        self,
        config: MetaConfig | None = None,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or MetaConfig.from_env()
        self.client = client or httpx.Client(timeout=60.0, follow_redirects=False)
        self._owns_client = client is None
        self.sleep = sleep

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def authorization_status(self) -> dict[str, Any]:
        result: dict[str, Any] = {"authorization_verified": False}
        for platform in ("instagram", "facebook"):
            try:
                self.config.validate(platform)
                result[platform] = {
                    "configured": True,
                    "detail": "Configured; account permissions have not been verified live.",
                }
            except ConfigurationError as exc:
                result[platform] = {"configured": False, "detail": str(exc)}
        return result

    def _url(self, edge: str) -> str:
        return f"https://graph.facebook.com/{self.config.graph_version}/{edge}"

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.config.page_access_token}"}
        headers.update(kwargs.pop("headers", {}))
        attempts = self.config.get_attempts if method == "GET" else 1
        for attempt in range(attempts):
            try:
                response = self.client.request(method, url, headers=headers, **kwargs)
            except httpx.HTTPError:
                if attempt + 1 < attempts:
                    self.sleep(min(2**attempt, 8))
                    continue
                raise ProviderFailed(
                    "Meta transport failure; credentials and remote response were omitted."
                ) from None
            if (
                method == "GET"
                and (response.status_code == 429 or response.status_code >= 500)
                and attempt + 1 < attempts
            ):
                self.sleep(min(2**attempt, 8))
                continue
            try:
                payload = response.json()
            except ValueError:
                raise ProviderFailed(
                    f"Meta returned invalid JSON (HTTP {response.status_code})."
                ) from None
            if not isinstance(payload, dict):
                raise ProviderFailed("Meta returned an invalid response object.")
            if not response.is_success or "error" in payload:
                error = payload.get("error", {})
                code = error.get("code") if isinstance(error, dict) else None
                # Never interpolate raw error text: Meta can echo token/URL input.
                suffix = f", API code {code}" if isinstance(code, int) else ""
                raise ProviderFailed(
                    f"Meta rejected the request (HTTP {response.status_code}{suffix})."
                )
            return payload
        raise ProviderFailed("Meta read retries exhausted.")

    @staticmethod
    def _save(path: Path, receipt: dict[str, Any], **updates: Any) -> None:
        receipt.update(updates, updated_at=datetime.now(UTC).isoformat())
        atomic_write(path, json.dumps(receipt, indent=2, sort_keys=True))

    @staticmethod
    def _id(payload: dict[str, Any], key: str) -> str:
        value = str(payload.get(key, ""))
        if not re.fullmatch(r"\d+", value):
            raise ProviderFailed("Meta returned no valid remote object ID.")
        return value

    def _receipt(
        self, path: Path, platform: str, account: str, video_url: str, caption: str, title: str
    ) -> dict[str, Any]:
        fingerprint = hashlib.sha256(
            json.dumps(
                [platform, account, self.config.graph_version, video_url, caption, title],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if path.exists():
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise ConfigurationError(
                    "Meta receipt is unreadable; reconcile it before continuing."
                ) from None
            if not isinstance(receipt, dict) or receipt.get("fingerprint") != fingerprint:
                raise ConfigurationError(
                    "Meta receipt does not match this account/content; do not reuse or delete an existing publication receipt."
                )
            return receipt
        receipt = {
            "schema_version": 1,
            "platform": platform,
            "account_id": account,
            "fingerprint": fingerprint,
            "state": "new",
            "published": False,
        }
        self._save(path, receipt)
        return receipt

    def _mutation(
        self, path: Path, receipt: dict[str, Any], stage: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        self._save(path, receipt, state=stage, uncertain_stage=stage)
        try:
            return self._request("POST", url, **kwargs)
        except ProviderFailed:
            self._save(path, receipt, state="uncertain")
            raise MetaPublishUncertain(
                f"Meta {stage} did not return a confirmed result. Keep the receipt; reconcile before any replay."
            ) from None

    def publish_instagram(self, video_url: str, caption: str, receipt_file: Path) -> dict[str, Any]:
        self.config.validate("instagram")
        _validate_media_url(video_url)
        if not caption.strip() or len(caption) > 2200:
            raise ConfigurationError("Instagram caption must contain 1–2200 characters.")
        path = Path(receipt_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(str(path) + ".lock", timeout=0):
            receipt = self._receipt(
                path, "instagram", self.config.instagram_account_id, video_url, caption, ""
            )
            if receipt.get("published"):
                return receipt
            if receipt.get("state") == "rejected":
                raise ProviderFailed(
                    "Instagram rejected or expired this container; inspect the saved receipt."
                )
            if not receipt.get("container_id"):
                if receipt["state"] != "new":
                    raise MetaPublishUncertain(
                        "Instagram container creation is uncertain; reconcile the saved receipt before restarting."
                    )
                payload = self._mutation(
                    path,
                    receipt,
                    "creating",
                    self._url(f"{self.config.instagram_account_id}/media"),
                    data={
                        "media_type": "REELS",
                        "video_url": video_url,
                        "caption": caption,
                        "share_to_feed": "true",
                    },
                )
                try:
                    container_id = self._id(payload, "id")
                except ProviderFailed:
                    self._save(path, receipt, state="uncertain")
                    raise MetaPublishUncertain(
                        "Instagram creation returned no ID; reconcile before retrying."
                    ) from None
                self._save(
                    path,
                    receipt,
                    container_id=container_id,
                    state="processing",
                    uncertain_stage=None,
                )
            publishing_attempted = receipt.get("uncertain_stage") == "publishing"
            for attempt in range(self.config.poll_attempts):
                payload = self._request(
                    "GET",
                    self._url(receipt["container_id"]),
                    params={"fields": "status_code,status"},
                )
                status = str(payload.get("status_code", "UNKNOWN"))
                if status not in {"IN_PROGRESS", "FINISHED", "PUBLISHED", "ERROR", "EXPIRED"}:
                    status = "UNKNOWN"
                self._save(path, receipt, remote_status=status)
                if status == "PUBLISHED":
                    self._save(
                        path, receipt, state="published", published=True, uncertain_stage=None
                    )
                    return receipt
                if status in {"ERROR", "EXPIRED"}:
                    self._save(path, receipt, state="rejected")
                    raise ProviderFailed(f"Instagram container status is {status}.")
                if status == "FINISHED" and not publishing_attempted:
                    break
                if attempt + 1 < self.config.poll_attempts:
                    self.sleep(self.config.poll_interval_seconds)
            else:
                if publishing_attempted:
                    raise MetaPublishUncertain(
                        "Instagram publish outcome is not confirmed; it will not be submitted twice."
                    )
                raise MetaProcessingPending(
                    "Instagram container is processing; retry later with the same receipt."
                )
            payload = self._mutation(
                path,
                receipt,
                "publishing",
                self._url(f"{self.config.instagram_account_id}/media_publish"),
                data={"creation_id": receipt["container_id"]},
            )
            try:
                media_id = self._id(payload, "id")
            except ProviderFailed:
                self._save(path, receipt, state="uncertain")
                raise MetaPublishUncertain(
                    "Instagram publish response has no ID; reconcile the saved container."
                ) from None
            self._save(
                path,
                receipt,
                media_id=media_id,
                state="published",
                published=True,
                uncertain_stage=None,
            )
            return receipt

    def _facebook_status(self, receipt: dict[str, Any]) -> dict[str, Any]:
        payload = self._request("GET", self._url(receipt["video_id"]), params={"fields": "status"})
        status = payload.get("status")
        if not isinstance(status, dict):
            raise ProviderFailed("Facebook returned no valid video status.")
        return status

    @staticmethod
    def _phase(status: dict[str, Any], key: str) -> str:
        phase = status.get(key, {})
        value = str(phase.get("status", "unknown")) if isinstance(phase, dict) else "unknown"
        return value if value in {"not_started", "in_progress", "complete", "error"} else "unknown"

    def publish_facebook(
        self, video_url: str, caption: str, receipt_file: Path, title: str = ""
    ) -> dict[str, Any]:
        self.config.validate("facebook")
        _validate_media_url(video_url)
        if not caption.strip() or len(caption) > 5000 or len(title) > 255:
            raise ConfigurationError(
                "Facebook requires a caption (up to 5000 characters) and a title up to 255 characters."
            )
        path = Path(receipt_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(str(path) + ".lock", timeout=0):
            receipt = self._receipt(
                path, "facebook", self.config.page_id, video_url, caption, title
            )
            if receipt.get("published"):
                return receipt
            if receipt.get("state") == "rejected":
                raise ProviderFailed("Facebook rejected this video; inspect the saved receipt.")
            if not receipt.get("video_id"):
                if receipt["state"] != "new":
                    raise MetaPublishUncertain(
                        "Facebook upload creation is uncertain; reconcile the receipt before restarting."
                    )
                payload = self._mutation(
                    path,
                    receipt,
                    "creating",
                    self._url(f"{self.config.page_id}/video_reels"),
                    data={"upload_phase": "start"},
                )
                try:
                    video_id = self._id(payload, "video_id")
                    self._save(path, receipt, video_id=video_id)
                    upload_url = str(payload.get("upload_url", ""))
                    expected = f"https://rupload.facebook.com/video-upload/{self.config.graph_version}/{video_id}"
                    if upload_url != expected:
                        raise ProviderFailed("Facebook returned an unexpected upload URL.")
                except ProviderFailed:
                    self._save(path, receipt, state="uncertain")
                    raise MetaPublishUncertain(
                        "Facebook upload creation response is invalid; reconcile before retrying."
                    ) from None
                self._save(path, receipt, video_id=video_id, state="created", uncertain_stage=None)
            if receipt["state"] == "created":
                upload_url = f"https://rupload.facebook.com/video-upload/{self.config.graph_version}/{receipt['video_id']}"
                payload = self._mutation(
                    path,
                    receipt,
                    "uploading",
                    upload_url,
                    headers={
                        "Authorization": f"OAuth {self.config.page_access_token}",
                        "file_url": video_url,
                    },
                )
                if payload.get("success") is not True:
                    self._save(path, receipt, state="uncertain")
                    raise MetaPublishUncertain(
                        "Facebook transfer was not confirmed; reconcile the saved video."
                    )
                self._save(path, receipt, state="uploaded", uncertain_stage=None)
            if receipt.get("uncertain_stage") == "uploading":
                status = self._facebook_status(receipt)
                if self._phase(status, "uploading_phase") != "complete":
                    raise MetaPublishUncertain(
                        "Facebook upload has not completed; it will not be transferred twice."
                    )
                self._save(path, receipt, state="uploaded", uncertain_stage=None)
            if receipt["state"] == "uploaded":
                payload = self._mutation(
                    path,
                    receipt,
                    "publishing",
                    self._url(f"{self.config.page_id}/video_reels"),
                    data={
                        "upload_phase": "finish",
                        "video_id": receipt["video_id"],
                        "video_state": "PUBLISHED",
                        "description": caption,
                        "title": title,
                    },
                )
                if payload.get("success") is not True:
                    self._save(path, receipt, state="uncertain")
                    raise MetaPublishUncertain(
                        "Facebook publish was not confirmed; reconcile the saved video."
                    )
                self._save(path, receipt, state="processing", uncertain_stage=None)
            for attempt in range(self.config.poll_attempts):
                status = self._facebook_status(receipt)
                publishing = self._phase(status, "publishing_phase")
                remote_status = status.get("video_status", "unknown")
                if remote_status not in {"processing", "ready", "error", "expired"}:
                    remote_status = "unknown"
                self._save(
                    path,
                    receipt,
                    remote_status=remote_status,
                    publishing_status=publishing,
                )
                if publishing == "complete":
                    self._save(
                        path, receipt, state="published", published=True, uncertain_stage=None
                    )
                    return receipt
                if status.get("video_status") == "error" or any(
                    self._phase(status, phase) == "error"
                    for phase in ("uploading_phase", "processing_phase", "publishing_phase")
                ):
                    self._save(path, receipt, state="rejected")
                    raise ProviderFailed(
                        "Facebook reported a failed video phase; inspect the remote video."
                    )
                if attempt + 1 < self.config.poll_attempts:
                    self.sleep(self.config.poll_interval_seconds)
            if receipt.get("uncertain_stage") == "publishing":
                raise MetaPublishUncertain(
                    "Facebook publication is unconfirmed; it will not be submitted twice."
                )
            raise MetaProcessingPending(
                "Facebook is processing; retry later with the same receipt."
            )
