from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .config import load_settings
from .dashboard import create_app
from .doctor import run_doctor
from .logging import configure_logging
from .music_video import MusicVideoPipeline
from .pipeline import DailyVideoPipeline
from .publishing.youtube import YouTubePublisher
from .scheduler import run_scheduler

app = typer.Typer(
    no_args_is_help=True,
    help="AtlasForge AI builds one complete, policy-aware YouTube video per day.",
)
console = Console()


@app.command("run")
def run_command(
    publication_date: str | None = typer.Option(
        None, "--date", help="Editorial/publication date in YYYY-MM-DD format. Defaults to today."
    ),
    topic: str | None = typer.Option(None, help="Override automatic topic research."),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    resume: bool = typer.Option(True, "--resume/--fresh", help="Resume a checkpointed run."),
    upload: bool | None = typer.Option(
        None, "--upload/--no-upload", help="Override publishing.enabled."
    ),
) -> None:
    """Run the full pipeline."""
    configure_logging()
    settings = load_settings(config)
    try:
        run_date = date.fromisoformat(publication_date) if publication_date else date.today()
    except ValueError as exc:
        raise typer.BadParameter("--date must use YYYY-MM-DD") from exc
    manifest = DailyVideoPipeline(settings).run(
        run_date, topic_override=topic, resume=resume, upload=upload
    )
    console.print(f"[bold green]Complete:[/] {manifest.status}")
    console.print(f"Run: {manifest.run_id}")
    console.print(f"Video: {manifest.final_video}")
    console.print(f"Thumbnail: {manifest.thumbnail}")
    if manifest.youtube_video_id:
        console.print(f"YouTube: https://youtu.be/{manifest.youtube_video_id}")


@app.command("doctor")
def doctor_command(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
) -> None:
    """Check a machine without spending API credits."""
    settings = load_settings(config)
    table = Table("Check", "Result", "Detail")
    failed_required = False
    for check in run_doctor(settings):
        status = (
            "[green]PASS[/]"
            if check.ok
            else ("[red]FAIL[/]" if check.required else "[yellow]OPTIONAL[/]")
        )
        table.add_row(check.name, status, check.detail)
        failed_required |= check.required and not check.ok
    console.print(table)
    if failed_required:
        raise typer.Exit(1)


@app.command("music-film")
def music_film_command(
    track: Path = typer.Option(..., exists=True, dir_okay=False, help="Uploaded master track."),
    title: str = typer.Option("Sepang Track Experience", help="Event or film title."),
    seconds: float = typer.Option(60, min=15, max=300, help="Render length in seconds."),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
) -> None:
    """Build a beat-synchronized faceless music film."""
    configure_logging()
    manifest = MusicVideoPipeline(load_settings(config)).run(
        track,
        title=title,
        max_duration_seconds=seconds,
    )
    console.print(f"[bold green]Complete:[/] {manifest.status}")
    console.print(f"Run: {manifest.run_id}")
    console.print(f"Video: {manifest.final_video}")


@app.command("youtube-auth")
def youtube_auth_command(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
) -> None:
    """Perform the one-time local OAuth flow for YouTube upload."""
    YouTubePublisher(load_settings(config)).authenticate(interactive=True)
    console.print("[green]YouTube authorization saved.[/]")


@app.command("schedule")
def schedule_command(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
) -> None:
    """Run the persistent once-daily scheduler."""
    configure_logging()
    run_scheduler(load_settings(config))


@app.command("dashboard")
def dashboard_command(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8741, min=1, max=65535),
) -> None:
    """Serve the local progress dashboard."""
    settings = load_settings(config)
    uvicorn.run(create_app(settings), host=host, port=port)


if __name__ == "__main__":
    app()
