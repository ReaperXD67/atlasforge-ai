from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_video_factory.social_analytics import SocialAnalyticsStore, SocialObservation


def observation(video_id: str = "v1", **overrides) -> SocialObservation:
    published = datetime(2026, 11, 1, 12, tzinfo=UTC)
    return SocialObservation.model_validate({
        "platform": "youtube", "account_id": "biznex", "video_id": video_id,
        "experiment_id": "hook-01", "variant": "question", "published_at": published,
        "observed_at": published + timedelta(hours=72), "views": 500, "shares": 10,
        **overrides,
    })


def test_reimport_is_idempotent_and_snapshot_corrections_replace(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    assert store.ingest([observation()]) == {"inserted": 1, "updated": 0, "unchanged": 0}
    assert store.ingest([observation()]) == {"inserted": 0, "updated": 0, "unchanged": 1}
    assert store.ingest([observation(views=520)]) == {"inserted": 0, "updated": 1, "unchanged": 0}
    assert store.report()["cohorts"][0]["variants"][0]["views"] == 520


def test_snapshots_are_not_added_and_nearest_age_is_selected(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    base = observation()
    store.ingest([
        base,
        observation(views=800, observed_at=base.published_at + timedelta(hours=80)),
        observation(views=2000, observed_at=base.published_at + timedelta(hours=168)),
    ])
    report = store.report()
    assert report["snapshot_count"] == 3
    assert report["selected_video_count"] == 1
    assert report["cohorts"][0]["variants"][0]["views"] == 500
    assert store.report(window_hours=168)["cohorts"][0]["variants"][0]["views"] == 2000


def test_zero_views_and_unknown_metrics_never_invent_rates(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([observation(views=0, shares=0), observation("v2", shares=None)])
    summary = store.report()["cohorts"][0]["variants"][0]
    assert summary["primary_metric_median"] is None
    assert summary["metric_medians"]["save_rate"]["median"] is None
    assert summary["eligible"] is False


def test_small_samples_cannot_select_a_candidate(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([
        observation(views=100000, shares=5000),
        observation("v2", variant="reveal", views=20, shares=1),
    ])
    cohort = store.report()["cohorts"][0]
    assert cohort["status"] == "insufficient_evidence"
    assert cohort["candidate_variant"] is None


def test_matched_cohort_recommends_replication_not_a_causal_win(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([
        observation(f"q{i}", shares=10, topic=f"topic-{i}", hook="Question first")
        for i in range(3)
    ] + [
        observation(f"r{i}", variant="reveal", shares=30, topic=f"topic-{i}", hook="Show proof")
        for i in range(3)
    ])
    cohort = store.report()["cohorts"][0]
    assert cohort["status"] == "directional_signal"
    assert cohort["candidate_variant"] == "reveal"
    assert "not a proven causal win" in cohort["recommendation"]
    assert cohort["variants"][1]["primary_metric_median"] == pytest.approx(0.06)
    assert cohort["variants"][1]["hooks"] == ["Show proof"]


def test_platforms_accounts_experiments_and_formats_never_pool(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([
        observation(), observation(platform="instagram"),
        observation(account_id="other"), observation("v2", experiment_id="cta-02"),
        observation("long-v1", format="long"),
    ])
    report = store.report()
    assert len(report["cohorts"]) == 5
    assert all(item["status"] == "needs_comparison" for item in report["cohorts"])


def test_replay_percentage_is_not_clamped_or_confused_with_completion(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([observation(average_percentage_viewed=145.7)])
    summary = store.report(primary_metric="average_percentage_viewed")["cohorts"][0]["variants"][0]
    assert summary["primary_metric_median"] == 145.7
    assert summary["metric_medians"]["completion_rate"]["median"] is None


def test_bad_file_rolls_back_all_rows(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    path = tmp_path / "metrics.json"
    bad = observation("bad").model_dump(mode="json")
    bad["views"] = -10
    path.write_text(json.dumps([observation().model_dump(mode="json"), bad]), encoding="utf-8")
    with pytest.raises(ValidationError):
        store.ingest_file(path)
    assert store.report()["data_status"] == "no_observations"


def test_experiment_reassignment_is_rejected_and_transaction_rolls_back(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([observation()])
    with pytest.raises(ValueError, match="Conflicting variant"):
        store.ingest([observation("new"), observation(variant="renamed")])
    assert store.report()["snapshot_count"] == 1


def test_csv_blank_metrics_remain_unknown(tmp_path: Path) -> None:
    path = tmp_path / "metrics.csv"
    path.write_text(
        "platform,account_id,video_id,experiment_id,variant,published_at,observed_at,views,shares,saves\n"
        "instagram,biznex,i1,hooks,a,2026-11-01T00:00:00Z,2026-11-04T00:00:00Z,400,0,\n",
        encoding="utf-8-sig",
    )
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    assert store.ingest_file(path)["inserted"] == 1
    summary = store.report()["cohorts"][0]["variants"][0]
    assert summary["metric_medians"]["share_rate"]["median"] == 0
    assert summary["metric_medians"]["save_rate"]["median"] is None


@pytest.mark.parametrize("overrides", [
    {"views": True}, {"shares": -1}, {"completed_views": 501}, {"engaged_views": 600},
    {"average_percentage_viewed": float("nan")}, {"average_watch_seconds": float("inf")},
    {"published_at": "2026-11-01T00:00:00"}, {"observed_at": "2026-10-01T00:00:00Z"},
    {"account_id": "   "}, {"viewz": 100},
])
def test_invalid_observations_fail_closed(overrides) -> None:
    with pytest.raises(ValidationError):
        observation(**overrides)


def test_unmatched_checkpoint_is_explicit(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([observation()])
    report = store.report(window_hours=24)
    assert report["data_status"] == "no_matching_checkpoint"
    assert report["cohorts"] == []


def test_equal_variants_do_not_pick_an_arbitrary_winner(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([
        observation(f"{variant}{i}", variant=variant)
        for variant in ["a", "b"] for i in range(3)
    ])
    report = store.report()
    assert report["cohorts"][0]["status"] == "no_clear_difference"
    assert report["cohorts"][0]["candidate_variant"] is None


def test_missing_primary_metric_prevents_cherry_picked_comparison(tmp_path: Path) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    store.ingest([
        observation(f"{variant}{i}", variant=variant)
        for variant in ["a", "b"] for i in range(3)
    ] + [observation("missing", variant="a", shares=None)])
    assert store.report()["cohorts"][0]["status"] == "insufficient_evidence"


@pytest.mark.parametrize("kwargs", [
    {"window_hours": float("nan")}, {"tolerance_hours": float("inf")},
    {"window_hours": 0}, {"tolerance_hours": -1}, {"min_videos": 1}, {"min_views": 0},
    {"primary_metric": "viral_score"},
])
def test_invalid_comparison_parameters_are_rejected(tmp_path: Path, kwargs) -> None:
    store = SocialAnalyticsStore(tmp_path / "analytics.sqlite3")
    with pytest.raises(ValueError):
        store.report(**kwargs)
