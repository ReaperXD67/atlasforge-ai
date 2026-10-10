from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image

from . import shorts_batch
from .shorts_batch import APPROVED_VOICE, ShortsBatchEpisode, ShortsBatchManifest
from .shorts_delivery import (
    validate_short_delivery,
    validate_shorts_upload_package,
    validate_voice_manifest,
)
from .youtube_delivery import validate_upload_package, validate_youtube_delivery


class ProductionBatchError(shorts_batch.ShortsBatchError):
    """Raised when a mixed-format production batch fails its preparation gates."""


@dataclass(frozen=True)
class ProductionBatchEpisode(ShortsBatchEpisode):
    format: str
    min_seconds: float
    max_seconds: float
    editorial_manifest: Path


@dataclass(frozen=True)
class ProductionBatchManifest(ShortsBatchManifest):
    episodes: tuple[ProductionBatchEpisode, ...]

    @property
    def report_path(self) -> Path:
        return shorts_batch._relative_path(
            self.path.parent, "PRODUCTION_BATCH_REPORT.json", "production batch report"
        )


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductionBatchError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ProductionBatchError(f"{label} must be a finite number")
    return number


def load_production_batch_manifest(
    manifest_path: Path, *, repository_root: Path | None = None
) -> ProductionBatchManifest:
    # The legacy loader supplies the shared schema, path safety, voice and output gates.
    try:
        base = shorts_batch.load_shorts_batch_manifest(
            manifest_path, repository_root=repository_root
        )
    except shorts_batch.ShortsBatchError as exc:
        raise ProductionBatchError(str(exc)) from exc
    payload = json.loads(base.path.read_text(encoding="utf-8-sig"))
    episodes: list[ProductionBatchEpisode] = []
    projects: set[Path] = set()
    for episode, row in zip(base.episodes, payload["episodes"], strict=True):
        if episode.project in projects:
            raise ProductionBatchError(f"duplicate episode project: {episode.project}")
        projects.add(episode.project)
        format_name = row.get("format")
        if not isinstance(format_name, str) or format_name not in {"shorts", "youtube"}:
            raise ProductionBatchError(f"{episode.id} format must be 'shorts' or 'youtube'")
        default_min, default_max = (20, 35) if format_name == "shorts" else (300, 360)
        minimum = _number(row.get("min_seconds", default_min), "min_seconds")
        maximum = _number(row.get("max_seconds", default_max), "max_seconds")
        if not 0 < minimum < maximum:
            raise ProductionBatchError("duration bounds must satisfy 0 < min_seconds < max_seconds")
        if format_name == "shorts" and maximum > 180:
            raise ProductionBatchError("a Shorts delivery cannot exceed 180 seconds")
        editorial = shorts_batch._relative_path(
            episode.project, row.get("editorial_manifest"), f"{episode.id} editorial_manifest"
        )
        if editorial in {episode.output, episode.raw_output, episode.mastered_output}:
            raise ProductionBatchError(f"{episode.id} editorial_manifest conflicts with render output")
        episodes.append(
            ProductionBatchEpisode(
                id=episode.id,
                project=episode.project,
                output=episode.output,
                thumbnail=episode.thumbnail,
                upload_package=episode.upload_package,
                voice_manifest=episode.voice_manifest,
                format=format_name,
                min_seconds=minimum,
                max_seconds=maximum,
                editorial_manifest=editorial,
            )
        )
    return ProductionBatchManifest(
        base.path, base.repository_root, base.batch_id, base.expected_voice, tuple(episodes)
    )


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionBatchError(f"editorial {label} must be non-empty text")
    return value.strip()


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProductionBatchError(f"editorial {label} must be an object")
    return value


def validate_editorial_manifest(
    episode: ProductionBatchEpisode,
    *,
    title: str,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Check authored evidence and promise review, not predicted views or semantic truth."""
    shorts_batch._require_file(episode.editorial_manifest, "editorial manifest")
    editorial = _object(
        json.loads(episode.editorial_manifest.read_text(encoding="utf-8-sig")), "manifest"
    )
    if type(editorial.get("schema_version")) is not int or editorial["schema_version"] != 1:
        raise ProductionBatchError("editorial schema_version must be 1")
    _text(editorial.get("audience_problem"), "audience_problem")
    script_path = shorts_batch._relative_path(episode.project, editorial.get("script"), "script")
    thumbnail_copy = shorts_batch._relative_path(
        episode.project, editorial.get("thumbnail_copy"), "thumbnail_copy"
    )
    shorts_batch._require_file(script_path, "editorial script")
    shorts_batch._require_file(thumbnail_copy, "editorial thumbnail copy")
    script = _normalized(script_path.read_text(encoding="utf-8-sig"))
    hook = _object(editorial.get("hook"), "hook")
    payoff = _object(editorial.get("payoff"), "payoff")
    hook_time = _number(hook.get("at_seconds"), "hook.at_seconds")
    payoff_time = _number(payoff.get("at_seconds"), "payoff.at_seconds")
    hook_limit = 2 if episode.format == "shorts" else 10
    if not 0 <= hook_time <= hook_limit:
        raise ProductionBatchError(f"editorial hook must start in the first {hook_limit} seconds")
    duration_limit = duration_seconds if duration_seconds is not None else episode.max_seconds
    if not hook_time < payoff_time < duration_limit:
        raise ProductionBatchError("editorial payoff must follow the hook and occur before the end")
    for label, fragment in (("hook", hook.get("text")), ("payoff", payoff.get("text"))):
        anchor = _normalized(_text(fragment, f"{label}.text"))
        if anchor not in script:
            raise ProductionBatchError(f"editorial {label} text is not anchored in the script")

    packaging = _object(editorial.get("packaging"), "packaging")
    if _text(packaging.get("title"), "packaging.title") != title:
        raise ProductionBatchError("editorial title differs from the actual upload title")
    expected_copy = _normalized(_text(packaging.get("thumbnail_text"), "thumbnail_text"))
    if expected_copy != _normalized(thumbnail_copy.read_text(encoding="utf-8-sig")):
        raise ProductionBatchError("editorial thumbnail text differs from THUMBNAIL_COPY")
    _text(packaging.get("promise"), "packaging.promise")
    evidence_anchor = _normalized(_text(packaging.get("evidence_anchor"), "evidence_anchor"))
    if evidence_anchor not in script:
        raise ProductionBatchError("packaging promise has no literal script evidence anchor")
    if packaging.get("reviewed") is not True:
        raise ProductionBatchError("title/thumbnail promise alignment requires an explicit review")

    sources = editorial.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ProductionBatchError("editorial sources require at least one supported claim")
    for source in sources:
        source = _object(source, "source")
        _text(source.get("claim"), "source.claim")
        url = urlparse(_text(source.get("url"), "source.url"))
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ProductionBatchError("editorial source URLs must be credential-free HTTPS URLs")
        try:
            checked_on = _text(source.get("checked_on"), "source.checked_on")
            if date.fromisoformat(checked_on).isoformat() != checked_on:
                raise ValueError("expected an extended ISO calendar date")
        except ValueError as exc:
            raise ProductionBatchError("editorial source checked_on must be YYYY-MM-DD") from exc

    beats = editorial.get("retention_beats")
    if not isinstance(beats, list) or len(beats) < 3:
        raise ProductionBatchError("editorial retention_beats require at least three planned beats")
    times: list[float] = []
    for beat in beats:
        beat = _object(beat, "retention beat")
        _text(beat.get("purpose"), "retention beat purpose")
        at = _number(beat.get("at_seconds"), "retention beat at_seconds")
        if not 0 <= at < duration_limit:
            raise ProductionBatchError("editorial retention beat falls outside the video")
        times.append(at)
    maximum_gap = 12 if episode.format == "shorts" else 45
    if times[0] != 0 or any(
        not 0 < later - earlier <= maximum_gap
        for earlier, later in zip(times, times[1:], strict=False)
    ):
        raise ProductionBatchError(
            f"planned retention beats must start at 0 and progress with gaps <= {maximum_gap}s"
        )
    if duration_seconds is not None and duration_seconds - times[-1] > maximum_gap:
        raise ProductionBatchError("the final stretch has no planned retention beat")
    return {
        "hook_seconds": hook_time,
        "payoff_seconds": payoff_time,
        "source_claim_count": len(sources),
        "planned_beat_count": len(times),
        "packaging_review_declared": True,
        "semantic_accuracy_automatically_verified": False,
        "analytics_observed": False,
    }


def _metadata(episode: ProductionBatchEpisode, *, duration_seconds: float) -> dict[str, Any]:
    markdown = episode.upload_package.read_text(encoding="utf-8-sig")
    if episode.format == "shorts":
        return validate_shorts_upload_package(markdown)
    return validate_upload_package(markdown, duration_seconds=duration_seconds)


def _validate_inputs(episode: ProductionBatchEpisode) -> None:
    for label, path in (
        ("thumbnail", episode.thumbnail),
        ("upload package", episode.upload_package),
        ("voice manifest", episode.voice_manifest),
        ("package.json", episode.project / "package.json"),
    ):
        shorts_batch._require_file(path, label)
    with Image.open(episode.thumbnail) as image:
        if image.format not in {"JPEG", "PNG"}:
            raise ProductionBatchError("thumbnail must be JPEG or PNG")
        if episode.format == "shorts" and image.size != (1080, 1920):
            raise ProductionBatchError(f"expected 1080x1920 thumbnail, got {image.size}")
        if episode.format == "youtube" and (
            image.width < 1280 or image.width * 9 != image.height * 16
        ):
            raise ProductionBatchError("YouTube thumbnail must be 16:9 and at least 1280px wide")
    validate_voice_manifest(
        json.loads(episode.voice_manifest.read_text(encoding="utf-8-sig")),
        expected_voice=APPROVED_VOICE,
    )
    metadata = _metadata(episode, duration_seconds=episode.max_seconds)
    validate_editorial_manifest(episode, title=metadata["title"])


def render_command(
    episode: ProductionBatchEpisode, manifest: ProductionBatchManifest
) -> list[str]:
    command = shorts_batch.render_command(episode, manifest)
    if episode.format == "youtube":
        command[command.index("-VerifyShorts")] = "-VerifyYouTube"
    return [
        *command,
        "-MinDuration",
        f"{episode.min_seconds:g}",
        "-MaxDuration",
        f"{episode.max_seconds:g}",
        "-CheckSamples",
        "60" if episode.format == "youtube" else "17",
    ]


def _verify(video: Path, episode: ProductionBatchEpisode) -> dict[str, Any]:
    if episode.format == "shorts":
        delivery = validate_short_delivery(
            video,
            episode.thumbnail,
            upload_package=episode.upload_package,
            voice_manifest=episode.voice_manifest,
            expected_voice=APPROVED_VOICE,
            min_seconds=episode.min_seconds,
            max_seconds=episode.max_seconds,
        )
    else:
        delivery = validate_youtube_delivery(
            video,
            episode.thumbnail,
            episode.upload_package,
            min_seconds=episode.min_seconds,
            max_seconds=episode.max_seconds,
        )
        delivery["voice"] = validate_voice_manifest(
            json.loads(episode.voice_manifest.read_text(encoding="utf-8-sig")),
            expected_voice=APPROVED_VOICE,
        )
    delivery["editorial"] = validate_editorial_manifest(
        episode,
        title=delivery["metadata"]["title"],
        duration_seconds=delivery["duration_seconds"],
    )
    return delivery


def source_fingerprint(
    episode: ProductionBatchEpisode, manifest: ProductionBatchManifest
) -> tuple[str, list[dict[str, Any]]]:
    fingerprint, files = shorts_batch.source_fingerprint(episode, manifest)
    # Format/bounds and the runner/verifier implementations are resume inputs, too.
    implementations = [
        Path(__file__),
        Path(shorts_batch.__file__),
        Path(__file__).with_name("shorts_delivery.py"),
        Path(__file__).with_name("youtube_delivery.py"),
    ]
    editorial = json.loads(episode.editorial_manifest.read_text(encoding="utf-8-sig"))
    extra_files = [episode.editorial_manifest]
    for key in ("script", "thumbnail_copy"):
        extra_files.append(shorts_batch._relative_path(episode.project, editorial[key], key))
    payload = {
        "pipeline_version": 1,
        "source_fingerprint": fingerprint,
        "format": episode.format,
        "min_seconds": episode.min_seconds,
        "max_seconds": episode.max_seconds,
        "editorial_files": {
            path.relative_to(episode.project).as_posix(): shorts_batch._sha256(path)
            for path in extra_files
        },
        "implementation_hashes": {
            path.name: shorts_batch._sha256(path) for path in implementations
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(), files


def run_production_batch(
    manifest_path: Path,
    *,
    resume: bool = True,
    dry_run: bool = False,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    manifest = load_production_batch_manifest(manifest_path, repository_root=repository_root)
    return shorts_batch._run_batch(
        manifest,
        resume=resume,
        dry_run=dry_run,
        validate_inputs=_validate_inputs,
        verify_delivery=_verify,
        render_job=render_command,
        fingerprint_sources=source_fingerprint,
        report_extra={
            "kind": "mixed-production",
            "format_counts": {
                format_name: sum(item.format == format_name for item in manifest.episodes)
                for format_name in ("shorts", "youtube")
            },
        },
    )
