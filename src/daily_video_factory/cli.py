from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, cast

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .config import load_settings
from .dashboard import create_app
from .doctor import run_doctor
from .logging import configure_logging
from .models import MUSIC_EDIT_STYLES, MusicEditStyle
from .music_video import MusicVideoPipeline
from .pipeline import DailyVideoPipeline
from .publishing.youtube import YouTubePublisher
from .scheduler import run_scheduler
from .viral_video import ViralShortPipeline

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
    brand: str = typer.Option(
        "PRAGON", help="Single brand wordmark used in titles and vocal cues."
    ),
    seconds: float = typer.Option(60, min=15, max=300, help="Render length in seconds."),
    visual_direction: str = typer.Option(
        "", help="Custom subjects, locations, atmosphere, wardrobe, and camera language."
    ),
    hook_words: str = typer.Option(
        "", help="Comma-separated words or short phrases for beat-locked kinetic type."
    ),
    edit_style: str = typer.Option(
        "smoke_velocity",
        help="pragon_neon, neon_strobe, smoke_velocity, luxury_noir, flash_editorial, or clean.",
    ),
    performer_mode: str = typer.Option(
        "stock_mix",
        help="stock_mix or malaysian_duet (locked recurring performers with Wan2.2-S2V).",
    ),
    male_performer_reference: Path | None = typer.Option(
        None, exists=True, dir_okay=False
    ),
    female_performer_reference: Path | None = typer.Option(
        None, exists=True, dir_okay=False
    ),
    friend_group_reference: Path | None = typer.Option(
        None, exists=True, dir_okay=False
    ),
    lyrics_file: Path | None = typer.Option(
        None,
        exists=True,
        dir_okay=False,
        help="Editor-approved lyrics with optional [section] and [vocal role] annotations.",
    ),
    lyrics_language: str = typer.Option(
        "auto", help="ISO-639-1 lyric language such as ms, id, or en; auto detects it."
    ),
    audit_only: bool = typer.Option(
        False,
        "--audit-only",
        help="Build timing, lyrics, storyboard, and performer plan without generating footage.",
    ),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
) -> None:
    """Build a beat-, phrase-, and lyric-synchronized music film."""
    if edit_style not in MUSIC_EDIT_STYLES:
        raise typer.BadParameter(
            "--edit-style must be pragon_neon, neon_strobe, smoke_velocity, luxury_noir, "
            "flash_editorial, or clean"
        )
    if performer_mode not in {"stock_mix", "malaysian_duet"}:
        raise typer.BadParameter("--performer-mode must be stock_mix or malaysian_duet")
    if lyrics_language != "auto" and not (
        len(lyrics_language) == 2 and lyrics_language.isalpha() and lyrics_language.islower()
    ):
        raise typer.BadParameter("--lyrics-language must be auto or a lowercase ISO-639-1 code")
    configure_logging()
    manifest = MusicVideoPipeline(load_settings(config)).run(
        track,
        title=title,
        brand=brand,
        max_duration_seconds=seconds,
        visual_direction=visual_direction,
        hook_words=hook_words,
        edit_style=cast(MusicEditStyle, edit_style),
        performer_mode=cast(Literal["stock_mix", "malaysian_duet"], performer_mode),
        male_performer_reference=male_performer_reference,
        female_performer_reference=female_performer_reference,
        friend_group_reference=friend_group_reference,
        lyrics_text=lyrics_file.read_text(encoding="utf-8") if lyrics_file else "",
        lyrics_language=lyrics_language,
        audit_only=audit_only,
    )
    console.print(f"[bold green]Complete:[/] {manifest.status}")
    console.print(f"Run: {manifest.run_id}")
    console.print(
        f"Video: {manifest.final_video}"
        if manifest.final_video
        else f"Audit artifacts: {manifest.output_root}"
    )


@app.command("viral-film")
def viral_film_command(
    recipe: str = typer.Option(
        "beat_creature",
        help="cinematic_insert, beat_creature, talking_duo, or physics_spectacle.",
    ),
    concept: str = typer.Option(..., help="The subject, action, environment, and camera idea."),
    provider: str = typer.Option("local_wan", help="local_wan, gemini_omni, or veo."),
    seconds: float = typer.Option(5, min=3, max=10),
    candidates: int = typer.Option(2, min=1, max=3, help="Local seeds to generate and rank."),
    reference: Path | None = typer.Option(None, exists=True, dir_okay=False),
    track: Path | None = typer.Option(None, exists=True, dir_okay=False),
    dialogue_a: str = typer.Option(""),
    dialogue_b: str = typer.Option(""),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
) -> None:
    """Build one coherent, vertical AI-native social clip."""
    if recipe not in {
        "cinematic_insert",
        "beat_creature",
        "talking_duo",
        "physics_spectacle",
    }:
        raise typer.BadParameter(
            "--recipe must be cinematic_insert, beat_creature, talking_duo, or physics_spectacle"
        )
    if provider not in {"local_wan", "gemini_omni", "veo"}:
        raise typer.BadParameter("--provider must be local_wan, gemini_omni, or veo")
    configure_logging()
    manifest = ViralShortPipeline(load_settings(config)).run(
        recipe=recipe,  # type: ignore[arg-type]
        concept=concept,
        provider_name=provider,  # type: ignore[arg-type]
        seconds=seconds,
        reference_image=reference,
        master_music=track,
        dialogue_a=dialogue_a,
        dialogue_b=dialogue_b,
        candidate_count=candidates,
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
