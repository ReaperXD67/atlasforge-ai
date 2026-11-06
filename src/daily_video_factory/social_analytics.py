"""Local, checkpoint-matched learning from exported social analytics.

Platform exports have different metric names and denominators. Importers must map
them explicitly to this schema; missing values remain unknown rather than zero.
The report describes observational evidence, never a causal or viral prediction.
"""

from __future__ import annotations

import csv
import json
import math
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Metric = Literal[
    "share_rate", "save_rate", "qualified_click_rate", "completion_rate",
    "average_percentage_viewed",
]
METRICS = {
    "share_rate": "shares",
    "save_rate": "saves",
    "qualified_click_rate": "qualified_clicks",
    "completion_rate": "completed_views",
    "average_percentage_viewed": "average_percentage_viewed",
}


class SocialObservation(BaseModel):
    """One cumulative video snapshot, measured from its publication time.

    ``average_percentage_viewed`` is a percentage (e.g. 74.5), not a
    fraction; replaying can make it exceed 100. ``completed_views`` must use
    the same view denominator as ``views``. Do not substitute engaged views
    for total views, impressions for feed exposure, or missing values for zero.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    platform: Literal["youtube", "instagram", "facebook"]
    account_id: str = Field(min_length=1, max_length=256)
    video_id: str = Field(min_length=1, max_length=256)
    experiment_id: str = Field(min_length=1, max_length=256)
    variant: str = Field(min_length=1, max_length=256)
    format: Literal["short", "long"] = "short"
    published_at: datetime
    observed_at: datetime
    views: int = Field(ge=0)
    impressions: int | None = Field(default=None, ge=0)
    engaged_views: int | None = Field(default=None, ge=0)
    completed_views: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    qualified_clicks: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, gt=0)
    average_watch_seconds: float | None = Field(default=None, ge=0)
    average_percentage_viewed: float | None = Field(default=None, ge=0)
    topic: str = Field(default="", max_length=500)
    hook: str = Field(default="", max_length=500)

    @field_validator("published_at", "observed_at")
    @classmethod
    def aware_dates(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps require an explicit timezone")
        return value.astimezone(UTC)

    @field_validator(
        "views", "impressions", "engaged_views", "completed_views", "shares", "saves",
        "qualified_clicks", mode="before",
    )
    @classmethod
    def reject_boolean_counts(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("metric counts must be numbers, not booleans")
        return value

    @model_validator(mode="after")
    def consistent_snapshot(self) -> SocialObservation:
        if self.observed_at < self.published_at:
            raise ValueError("observed_at cannot precede published_at")
        for metric in ("engaged_views", "completed_views"):
            value = getattr(self, metric)
            if value is not None and value > self.views:
                raise ValueError(f"{metric} must use the same denominator and not exceed views")
        return self

    @property
    def age_hours(self) -> float:
        return (self.observed_at - self.published_at).total_seconds() / 3600


def _metric_value(item: SocialObservation, metric: str) -> float | None:
    value = getattr(item, METRICS[metric])
    if value is None or item.views == 0:
        return None
    if metric == "average_percentage_viewed":
        return float(value)
    return float(value) / item.views


class SocialAnalyticsStore:
    """SQLite snapshots with atomic imports and one measurement per video per report."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS social_observations (
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(platform, account_id, video_id, observed_at)
                )"""
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def ingest_file(self, path: Path) -> dict[str, int]:
        """Read a normalized JSON array (or {observations: [...]}) or UTF-8 CSV.

        Blank CSV cells are omitted, preserving unknown optional metrics. Native
        platform exports must first be mapped to the documented column schema.
        """
        path = Path(path)
        rows: list[object]
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = [
                    {key: value for key, value in row.items() if value not in ("", None)}
                    for row in csv.DictReader(stream)
                ]
        elif path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict):
                payload = payload.get("observations")
            if not isinstance(payload, list):
                raise ValueError("JSON must contain an array or an observations array")
            rows = payload
        else:
            raise ValueError("Analytics input must be a .csv or .json file")
        # Validate the whole file before writing so a bad row cannot partially import.
        observations = [SocialObservation.model_validate(row) for row in rows]
        return self.ingest(observations)

    def ingest(self, observations: list[SocialObservation]) -> dict[str, int]:
        result = {"inserted": 0, "updated": 0, "unchanged": 0}
        with self._connect() as db:
            for item in observations:
                identity = (item.platform, item.account_id, item.video_id)
                key = (*identity, item.observed_at.isoformat())
                prior = db.execute(
                    "SELECT payload FROM social_observations "
                    "WHERE platform=? AND account_id=? AND video_id=? LIMIT 1", identity,
                ).fetchone()
                if prior:
                    previous = SocialObservation.model_validate_json(prior["payload"])
                    for field in ("published_at", "experiment_id", "variant", "format"):
                        if getattr(item, field) != getattr(previous, field):
                            raise ValueError(
                                f"Conflicting {field} for {item.platform}/{item.video_id}; "
                                "a video must retain its experiment assignment"
                            )
                existing = db.execute(
                    "SELECT payload FROM social_observations "
                    "WHERE platform=? AND account_id=? AND video_id=? AND observed_at=?", key,
                ).fetchone()
                payload = item.model_dump_json()
                if existing and existing["payload"] == payload:
                    result["unchanged"] += 1
                    continue
                db.execute(
                    "INSERT INTO social_observations VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(platform, account_id, video_id, observed_at) "
                    "DO UPDATE SET payload=excluded.payload", (*key, payload),
                )
                result["updated" if existing else "inserted"] += 1
        return result

    def report(
        self, *, window_hours: float = 72, tolerance_hours: float = 12,
        min_videos: int = 3, min_views: int = 1000,
        primary_metric: Metric = "share_rate",
    ) -> dict[str, object]:
        """Compare variants at a matched age, separately for each account and format.

        Thresholds are workflow heuristics, not statistical significance. The
        primary metric must be chosen before inspecting results. Selection uses
        the nearest checkpoint, then the later snapshot for an exact tie.
        """
        if (
            not math.isfinite(window_hours) or not math.isfinite(tolerance_hours)
            or window_hours <= 0 or tolerance_hours < 0 or tolerance_hours > window_hours
        ):
            raise ValueError("Use a positive window and tolerance between zero and the window")
        if min_videos < 2 or min_views < 1:
            raise ValueError("Comparisons require at least two videos and positive views")
        if primary_metric not in METRICS:
            raise ValueError(f"Unsupported primary metric: {primary_metric}")
        with self._connect() as db:
            observations = [
                SocialObservation.model_validate_json(row["payload"])
                for row in db.execute("SELECT payload FROM social_observations ORDER BY observed_at")
            ]
        selected: dict[tuple[str, str, str], SocialObservation] = {}
        for item in observations:
            distance = abs(item.age_hours - window_hours)
            if distance > tolerance_hours:
                continue
            identity = (item.platform, item.account_id, item.video_id)
            current = selected.get(identity)
            if current is None or distance <= abs(current.age_hours - window_hours):
                selected[identity] = item
        cohorts: dict[tuple[str, str, str, str], list[SocialObservation]] = defaultdict(list)
        for item in selected.values():
            cohorts[(item.platform, item.account_id, item.experiment_id, item.format)].append(item)
        output: list[dict[str, object]] = []
        for (platform, account, experiment, video_format), items in sorted(cohorts.items()):
            variants: dict[str, list[SocialObservation]] = defaultdict(list)
            for item in items:
                variants[item.variant].append(item)
            summaries = [
                self._summarize_variant(name, videos, primary_metric, min_videos, min_views)
                for name, videos in sorted(variants.items())
            ]
            candidate = None
            if len(summaries) < 2:
                status = "needs_comparison"
                recommendation = "Collect another planned variant at the same checkpoint."
            elif not all(summary["eligible"] for summary in summaries):
                status = "insufficient_evidence"
                recommendation = (
                    "Collect more matched videos/views and the primary metric for every variant; "
                    "do not choose a winner from this sample."
                )
            else:
                ranked = sorted(
                    summaries,
                    key=lambda summary: cast(float, summary["primary_metric_median"]),
                    reverse=True,
                )
                if ranked[0]["primary_metric_median"] == ranked[1]["primary_metric_median"]:
                    status = "no_clear_difference"
                    recommendation = "Primary-metric medians tie; repeat the planned comparison."
                else:
                    status = "directional_signal"
                    candidate = ranked[0]["variant"]
                    recommendation = (
                        f"Repeat variant {candidate!r} in a new matched batch with fresh topics. "
                        "This observational difference is not a proven causal win."
                    )
            output.append({
                "platform": platform, "account_id": account, "experiment_id": experiment,
                "format": video_format, "status": status, "candidate_variant": candidate,
                "recommendation": recommendation, "variants": summaries,
            })
        return {
            "schema_version": 1,
            "data_status": "no_observations" if not observations else (
                "no_matching_checkpoint" if not selected else "observed"
            ),
            "source": "locally_imported_observations",
            "snapshot_count": len(observations), "selected_video_count": len(selected),
            "window_hours": window_hours, "tolerance_hours": tolerance_hours,
            "primary_metric": primary_metric,
            "thresholds": {"min_videos_per_variant": min_videos, "min_views_per_variant": min_views},
            "limitations": [
                "No live account analytics have been fetched by this report.",
                "Views and engagement definitions differ by platform; cohorts are never pooled.",
                "Snapshots are cumulative and selected once per video, never summed over time.",
                "Missing metrics stay unknown. Thresholds do not establish statistical significance.",
                "No observational result guarantees reach, sales, income, or a causal improvement.",
            ],
            "cohorts": output,
        }

    @staticmethod
    def _summarize_variant(
        name: str, videos: list[SocialObservation], primary_metric: str,
        min_videos: int, min_views: int,
    ) -> dict[str, object]:
        known = [item for item in videos if _metric_value(item, primary_metric) is not None]
        metrics: dict[str, dict[str, float | int | None]] = {}
        for metric in METRICS:
            values = [value for item in videos if (value := _metric_value(item, metric)) is not None]
            metrics[metric] = {
                "median": median(values) if values else None, "videos_with_metric": len(values),
            }
        known_views = sum(item.views for item in known)
        return {
            "variant": name, "video_count": len(videos), "views": sum(item.views for item in videos),
            "primary_metric_video_count": len(known), "primary_metric_views": known_views,
            "primary_metric_median": metrics[primary_metric]["median"],
            "eligible": (
                len(known) == len(videos) and len(known) >= min_videos and known_views >= min_views
            ),
            "metric_medians": metrics,
            "video_ids": sorted(item.video_id for item in videos),
            "topics": sorted({item.topic for item in videos if item.topic}),
            "hooks": sorted({item.hook for item in videos if item.hook}),
        }
