"""Verified story sources and explicit observed-publication reconciliation.

This adapter never publishes. Browser confirmation is an operator observation,
not an invented API readback; its evidence is retained with the queue receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import parse_qs, urlsplit

import portalocker
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .exceptions import ConfigurationError
from .models import VideoMetadata
from .publishing.meta import _validate_media_url
from .quality import PROHIBITED_PATTERNS, _contains_unqualified_claim
from .story_delivery import verify_current_render, verify_story_qa

if TYPE_CHECKING:
    from .social_campaign import CampaignPost, SocialCampaignManager


def inspect_story(manager: SocialCampaignManager, reference: str, post: CampaignPost) -> dict[str, Any]:
    from .social_campaign import _hashtags, _post_payload, _relative, _sha256

    project = _relative(manager.root, reference)
    if post.episode_id != project.name or not post.title:
        raise ConfigurationError("Story posts require the matching project episode_id and an explicit title.")
    verified = verify_current_render(project)
    verify_story_qa(project, verified)
    review_path = project / "DELIVERY_REVIEW.json"
    review = json.loads(review_path.read_text(encoding="utf-8-sig"))
    if (review.get("video_sha256") != verified["video_sha256"]
            or review.get("sampled_visual_review_passed") is not True
            or review.get("blocking_findings") != []
            or review.get("frame_review_sha256") != _sha256(project / "qa/frames/frame-review.json")):
        raise ConfigurationError("A current sampled visual review with no blocking findings is required.")
    plan = verified["plan"]
    if (plan["width"], plan["height"], plan["fps"]) != (1080, 1920, 30):
        raise ConfigurationError("Story social posts require the verified 1080x1920, 30fps contract.")
    if post.platform == "youtube":
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", post.account_id):
            raise ConfigurationError("YouTube account_id must be the UC-prefixed channel ID.")
    else:
        if post.privacy != "public" or not 4 <= plan["duration_seconds"] <= 60:
            raise ConfigurationError("Meta story posts must explicitly be public, 4–60 second Reels.")
        browser_handle = post.platform == "instagram" and post.transport == "browser" and re.fullmatch(
            r"@[A-Za-z0-9_.]{1,30}", post.account_id
        )
        if not browser_handle and not re.fullmatch(r"\d+", post.account_id):
            raise ConfigurationError("Use a numeric Meta account ID, or an exact Instagram @handle for browser transport.")
        if post.transport == "api":
            if not post.video_url:
                raise ConfigurationError("Meta API posts require hosted identical video bytes.")
            _validate_media_url(post.video_url)
    caption = post.caption
    if "synthetic" not in caption.casefold() and "ai-generated" not in caption.casefold():
        raise ConfigurationError("Story publication copy must disclose synthetic/AI-generated narration.")
    if post.platform == "instagram" and len(caption) > 2200:
        raise ConfigurationError("Instagram caption exceeds 2200 characters.")
    script_path = project / "script.txt"
    for label, pattern in PROHIBITED_PATTERNS.items():
        if _contains_unqualified_claim(post.title + "\n" + caption + "\n" + script_path.read_text(encoding="utf-8-sig"), pattern):
            raise ConfigurationError(f"Story script or publication copy contains a prohibited {label}.")
    subtitles = _relative(manager.root, post.subtitles) if post.subtitles else None
    if post.platform == "youtube" and manager.settings.publishing.upload_caption_track and not subtitles:
        raise ConfigurationError("Caption upload is enabled; supply the verified story SRT path.")
    if subtitles and _sha256(subtitles) != _sha256(project / "assets/audio/narration.srt"):
        raise ConfigurationError("Story subtitles must match the verified narration SRT.")
    files = [project / name for name in (
        "renders/final.report.json", "qa/audio/encoded-audio-verification.json",
        "qa/frames/frame-review.json", "DELIVERY_REVIEW.json", "UPLOAD_COPY.md", "script.txt",
        "assets/audio/narration.srt",
    )]
    if subtitles:
        files.append(subtitles)
    hashes = {path.relative_to(manager.root).as_posix(): _sha256(path) for path in files}
    fingerprint = hashlib.sha256(json.dumps({
        "files": hashes, "render_sources": verified["snapshot"],
        "video_sha256": verified["video_sha256"], "story_project": reference,
        "post": _post_payload(post), "settings": manager.settings.model_dump(mode="json"),
    }, sort_keys=True).encode()).hexdigest()
    tags = _hashtags(caption)[:15]
    return {
        "episode": SimpleNamespace(project=project, output=verified["video"], format="shorts", thumbnail=project / "poster.jpg"),
        "metadata": VideoMetadata(title=post.title, description=caption, tags=post.tags or [x[1:] for x in tags],
                                  hashtags=tags, chapters=[], thumbnail_text="", category_id=manager.settings.publishing.category_id),
        "subtitles": subtitles, "fingerprint": fingerprint, "video_sha256": verified["video_sha256"],
        "social_caption": caption,
    }


class PublicationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    platform: Literal["youtube", "instagram", "facebook"]
    account_id: str
    video_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(min_length=1, max_length=100)
    remote_id: str = Field(pattern=r"^[A-Za-z0-9_-]{5,100}$")
    url: str
    privacy: Literal["public", "private", "unlisted"]
    verified_at: datetime
    method: Literal["browser_observation", "api_readback"]
    evidence_file: str
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_published: Literal[True]

    @field_validator("account_id")
    @classmethod
    def canonical_handle(cls, value: str) -> str:
        return value.casefold() if value.startswith("@") else value

    @field_validator("verified_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Observation time must include a timezone")
        return value


def _observed_url(observation: PublicationObservation) -> None:
    url = urlsplit(observation.url)
    if url.scheme != "https" or url.username or url.password or url.port or url.fragment:
        raise ConfigurationError("Publication evidence requires a clean HTTPS platform URL.")
    host = url.hostname
    if observation.platform == "youtube":
        valid = host in {"youtube.com", "www.youtube.com"} and (
            (url.path == "/watch" and parse_qs(url.query) == {"v": [observation.remote_id]})
            or (url.path == "/shorts/" + observation.remote_id and not url.query)
        )
    elif observation.platform == "instagram":
        valid = host in {"instagram.com", "www.instagram.com"} and not url.query and url.path in {
            "/p/" + observation.remote_id + "/", "/reel/" + observation.remote_id + "/",
        }
    else:
        valid = host in {"facebook.com", "www.facebook.com"} and not url.query and (
            url.path == "/reel/" + observation.remote_id + "/"
            or url.path == "/reel/" + observation.remote_id
            or url.path.endswith("/posts/" + observation.remote_id)
            or url.path.endswith("/videos/" + observation.remote_id + "/")
        )
    if not valid:
        raise ConfigurationError("Publication URL must match its platform and remote ID, without tracking parameters.")


def _reinspect(manager: SocialCampaignManager, row: Any) -> tuple[CampaignPost, dict[str, Any]]:
    from .social_campaign import CampaignPost
    payload = json.loads(row["payload"])
    post = CampaignPost.model_validate(payload["post"])
    if not payload.get("story_project"):
        raise ConfigurationError("Observed publication requires a verified story campaign.")
    inspected = manager._inspect(None, post, story_project=payload["story_project"])
    if inspected["fingerprint"] != row["fingerprint"]:
        raise ConfigurationError("Queued story inputs changed; reconciliation cannot adopt different content.")
    return post, inspected


def claim_browser(manager: SocialCampaignManager, post_key: str) -> dict[str, Any]:
    from .social_campaign import _clock
    with portalocker.Lock(str(manager.database) + ".worker.lock", timeout=0), manager._connect() as conn:
        row = conn.execute("SELECT * FROM social_posts WHERE post_key=?", (post_key,)).fetchone()
        if not row or row["state"] != "pending" or row["publish_at"] > _clock().isoformat():
            raise ConfigurationError("Only a due pending browser post can be claimed; never replay a claimed/held post.")
        post, _ = _reinspect(manager, row)
        if post.transport != "browser":
            raise ConfigurationError("This job is not a browser publication.")
        return manager._update(post_key, state="browser_claimed", attempts=row["attempts"] + 1,
                               receipt=json.dumps({"browser_claimed_at": _clock().isoformat(), "privacy": post.privacy}))


def record_observed(manager: SocialCampaignManager, post_key: str, evidence_path: Path) -> dict[str, Any]:
    from .social_campaign import _clock, _relative, _sha256
    observation = PublicationObservation.model_validate_json(evidence_path.read_text(encoding="utf-8-sig"))
    _observed_url(observation)
    if observation.verified_at > _clock():
        raise ConfigurationError("Publication observation cannot be future dated.")
    proof = _relative(manager.root, observation.evidence_file)
    if _sha256(proof) != observation.evidence_sha256:
        raise ConfigurationError("Publication evidence bytes changed.")
    with portalocker.Lock(str(manager.database) + ".worker.lock", timeout=0), manager._connect() as conn:
        row = conn.execute("SELECT * FROM social_posts WHERE post_key=?", (post_key,)).fetchone()
        if not row or row["state"] not in {"pending", "browser_claimed", "uncertain", "published"}:
            raise ConfigurationError("Only a pending, claimed, uncertain or already published story may be reconciled; held jobs stay held.")
        post, inspected = _reinspect(manager, row)
        if (observation.platform != post.platform or observation.account_id != post.account_id
                or observation.video_sha256 != row["video_sha256"] or observation.privacy != post.privacy
                or observation.title != inspected["metadata"].title):
            raise ConfigurationError("Observed account, video, title or privacy does not match the queued story.")
        for other in conn.execute("SELECT post_key,receipt FROM social_posts WHERE platform=? AND account_id=?", (post.platform, post.account_id)):
            receipt = json.loads(other["receipt"])
            if other["post_key"] != post_key and observation.remote_id in {receipt.get("video_id"), receipt.get("media_id")}:
                raise ConfigurationError("That remote publication already belongs to another queue record.")
        prior = json.loads(row["receipt"])
        if (prior.get("video_id") or prior.get("media_id")) and observation.remote_id not in {
            prior.get("video_id"), prior.get("media_id"),
        }:
            raise ConfigurationError("A saved remote ID cannot be replaced by reconciliation.")
        if row["state"] == "published":
            return manager._public(row)
        receipt = {**prior, "video_id" if post.platform == "youtube" else "media_id": observation.remote_id,
                   "privacy": post.privacy, "url": observation.url, "published": True,
                   "verification": observation.method, "observation": observation.model_dump(mode="json")}
        return manager._update(post_key, state="published", receipt=json.dumps(receipt), error=None, next_attempt_at=None)
