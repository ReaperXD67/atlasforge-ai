"""Local social-operator commands; live mutations require an explicit --execute."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Literal, ParamSpec, TypeVar

import portalocker
import typer
from rich.console import Console

from .artifacts import atomic_write
from .config import load_settings
from .publishing.meta import MetaPublisher
from .publishing.youtube import YouTubePublisher
from .social_analytics import SocialAnalyticsStore

app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_show_locals=False,
    help="Publish verified campaigns and learn from social results.",
)
console = Console()
P = ParamSpec("P")
R = TypeVar("R")


def _safe_io(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except (typer.Exit, typer.Abort):
            raise
        except (ValueError, OSError, RuntimeError, sqlite3.Error, portalocker.exceptions.LockException):
            raise typer.BadParameter(
                "Social operation failed. Check the local configuration, input schema, files and "
                "worker lock. Sensitive input and provider errors are omitted. See docs/SOCIAL_AUTOMATION.md."
            ) from None
    return wrapped


def _manager(config: Path, root: Path, database: Path | None):
    from .social_campaign import SocialCampaignManager

    return SocialCampaignManager(load_settings(config), root.resolve(), database=database)


@contextmanager
def _managed(config: Path, root: Path, database: Path | None) -> Iterator:
    manager = _manager(config, root, database)
    try:
        yield manager
    finally:
        close = getattr(manager, "close", None)
        if close is not None:
            close()


@app.command("doctor")
@_safe_io
def doctor(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
) -> None:
    """Check local connection setup without printing credentials or making an upload."""
    settings = load_settings(config)
    meta = MetaPublisher()
    try:
        console.print_json(data={
            "youtube": YouTubePublisher(settings).authorization_status(),
            "meta": meta.authorization_status(),
            "account_creation": "Owner registration and verification must be completed in the browser.",
            "analytics": "Import normalized JSON/CSV exports; live analytics sync is not configured.",
        })
    finally:
        meta.close()


@app.command("enqueue")
@_safe_io
def enqueue(
    campaign: Path = typer.Option(..., exists=True, dir_okay=False),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Validate local deliveries and record immutable, duplicate-protected publish jobs."""
    try:
        with _managed(config, root, database) as manager:
            console.print_json(data=manager.enqueue(campaign))
    except (ValueError, OSError, RuntimeError) as exc:
        raise typer.BadParameter(
            "Campaign validation failed. Check the schema, account IDs, paths, and verified deliveries; "
            "input values are omitted to protect credentials. See docs/SOCIAL_AUTOMATION.md."
        ) from exc


@app.command("status")
@_safe_io
def status(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Show queued posts and confirmed outcomes; credentials are omitted."""
    with _managed(config, root, database) as manager:
        console.print_json(data=manager.list_posts())


@app.command("claim-browser")
@_safe_io
def claim_browser(
    post_key: str = typer.Option(...),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Reserve one due browser job locally before uploading; never automatically replay it."""
    with _managed(config, root, database) as manager:
        console.print_json(data=manager.claim_browser(post_key))


@app.command("record-observed")
@_safe_io
def record_observed(
    post_key: str = typer.Option(...),
    evidence: Path = typer.Option(..., exists=True, dir_okay=False),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Record an exact, independently confirmed publication without another remote upload."""
    with _managed(config, root, database) as manager:
        console.print_json(data=manager.record_observed(post_key, evidence))


@app.command("run-due")
@_safe_io
def run_due(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
    execute: bool = typer.Option(False, "--execute", help="Publish due verified posts to configured accounts."),
    limit: int = typer.Option(5, min=1, max=50),
) -> None:
    """Preview due posts by default; --execute sends them to the platform APIs."""
    with _managed(config, root, database) as manager:
        result = manager.run_due(execute=execute, limit=limit)
    console.print_json(data=result)
    if execute and any(row.get("state") in {"blocked", "uncertain"} for row in result):
        raise typer.Exit(1)


@app.command("retry-blocked")
@_safe_io
def retry_blocked(
    post_key: str = typer.Option(..., help="Exact post_key from social status."),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Return a corrected blocked job to pending; uncertain outcomes require reconciliation."""
    with _managed(config, root, database) as manager:
        console.print_json(data=manager.retry_blocked(post_key))


@app.command("watch")
@_safe_io
def watch(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
    execute: bool = typer.Option(False, "--execute", help="Publish due posts until this process is stopped."),
    interval_minutes: int = typer.Option(5, min=1, max=1440),
) -> None:
    """Run the queue worker on this computer; keep the process and computer running."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    manager = _manager(config, root, database)
    scheduler = BlockingScheduler(timezone="UTC")

    def tick() -> None:
        try:
            console.print_json(data=manager.run_due(execute=execute, limit=5))
        except (ValueError, OSError, RuntimeError, sqlite3.Error, portalocker.exceptions.LockException):
            console.print_json(data={
                "state": "worker_error",
                "detail": "Check configuration, database and worker lock; sensitive error details omitted.",
            })

    try:
        tick()
        scheduler.add_job(tick, "interval", minutes=interval_minutes, max_instances=1, coalesce=True)
        scheduler.start()
    finally:
        close = getattr(manager, "close", None)
        if close is not None:
            close()


@app.command("hold")
@_safe_io
def hold(
    post_key: list[str] = typer.Option(..., help="Exact post_key from status; repeat for an atomic group."),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Hold exact pending posts locally; workers cannot publish held jobs."""
    with _managed(config, root, database) as manager:
        console.print_json(data=manager.hold_posts(post_key))


@app.command("resume")
@_safe_io
def resume(
    post_key: list[str] = typer.Option(..., help="Exact held post_key; repeat for an atomic group."),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    database: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Release exact held jobs. Original due times remain; overdue jobs become eligible."""
    with _managed(config, root, database) as manager:
        console.print_json(data=manager.resume_posts(post_key))


@app.command("import-metrics")
@_safe_io
def import_metrics(
    source: Path = typer.Option(..., exists=True, dir_okay=False),
    database: Path = typer.Option(Path("output/social/analytics.sqlite"), dir_okay=False),
) -> None:
    """Import explicitly mapped JSON or CSV observations; repeated imports are safe."""
    try:
        console.print_json(data=SocialAnalyticsStore(database).ingest_file(source))
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(
            "Metrics import failed. Check the normalized JSON/CSV schema in docs/SOCIAL_GROWTH.md; "
            "input values are omitted to protect credentials."
        ) from exc


@app.command("report")
@_safe_io
def report(
    database: Path = typer.Option(Path("output/social/analytics.sqlite"), dir_okay=False),
    output: Path | None = typer.Option(None, dir_okay=False),
    window_hours: float = typer.Option(72, min=1),
    tolerance_hours: float = typer.Option(12, min=0),
    min_videos: int = typer.Option(3, min=2),
    min_views: int = typer.Option(1000, min=1),
    primary_metric: Literal[
        "share_rate", "save_rate", "qualified_click_rate", "completion_rate", "average_percentage_viewed"
    ] = typer.Option("share_rate"),
) -> None:
    """Compare matched-age observations, keeping each account/platform/format separate."""
    try:
        result = SocialAnalyticsStore(database).report(
            window_hours=window_hours, tolerance_hours=tolerance_hours,
            min_videos=min_videos, min_views=min_views, primary_metric=primary_metric,
        )
    except ValueError:
        raise typer.BadParameter(
            "Analytics report failed. Check the report window and normalized observations; "
            "sensitive input values are omitted. See docs/SOCIAL_GROWTH.md."
        ) from None
    if output:
        atomic_write(output, json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    console.print_json(data=result)
