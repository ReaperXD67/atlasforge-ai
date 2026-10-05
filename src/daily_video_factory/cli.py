from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, cast

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .browser_capture import BrowserCaptureRecipe, PlaywrightCliCaptureRunner
from .config import load_settings
from .dashboard import create_app
from .doctor import run_doctor
from .logging import configure_logging
from .media.audio import generate_original_music, generate_short_sfx_set
from .media.ffmpeg import FFmpeg
from .models import MUSIC_EDIT_STYLES, MusicEditStyle
from .music_video import MusicVideoPipeline
from .pipeline import DailyVideoPipeline
from .providers.tts import NarrationGenerator
from .publishing.youtube import YouTubePublisher
from .scheduler import run_scheduler
from .shorts import extract_hyperframes_narration, write_short_experiment_manifest
from .shorts_batch import ShortsBatchError, run_shorts_batch
from .shorts_delivery import ShortsDeliveryError, validate_short_delivery
from .viral_video import ViralShortPipeline
from .youtube_delivery import YouTubeDeliveryError, validate_youtube_delivery

app = typer.Typer(
    no_args_is_help=True,
    help="AtlasForge AI builds one complete, policy-aware YouTube video per day.",
)
console = Console()


@app.command("browser-capture")
def browser_capture_command(
    recipe: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(..., file_okay=False),
) -> None:
    """Capture a safe, declarative browser evidence recipe."""
    capture_recipe = BrowserCaptureRecipe.from_yaml(recipe)
    manifest = PlaywrightCliCaptureRunner(capture_recipe, output).run()
    console.print(f"[bold green]Capture complete:[/] {manifest}")


@app.command("narrate")
def narrate_command(
    text_file: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(..., file_okay=False),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    target_seconds: float | None = typer.Option(
        None, min=1, help="Fit narration and exact captions to this edit duration."
    ),
) -> None:
    """Generate mastered narration from an authored text file using the provider chain."""
    configure_logging()
    settings = load_settings(config)
    ffmpeg = FFmpeg()
    result = NarrationGenerator(settings, ffmpeg).run(
        text_file.read_text(encoding="utf-8"), output, target_seconds=target_seconds
    )
    console.print(f"[bold green]Narration complete:[/] {result.value}")
    console.print(f"Provider: {result.provider}")
    console.print(f"Duration: {ffmpeg.duration(result.value):.3f}s")
    exact_srt = output / "narration.exact.srt"
    if exact_srt.is_file():
        console.print(f"Exact captions: {exact_srt}")


@app.command("narrate-script")
def narrate_script_command(
    script: Path = typer.Option(..., exists=True, dir_okay=False, help="HyperFrames SCRIPT.md"),
    output: Path = typer.Option(..., file_okay=False),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True, dir_okay=False),
    target_seconds: float | None = typer.Option(
        None, min=1, help="Optionally fit narration and exact captions to this duration."
    ),
) -> None:
    """Narrate the spoken blocks in SCRIPT.md without maintaining a duplicate text file."""
    configure_logging()
    settings = load_settings(config)
    ffmpeg = FFmpeg()
    narration = extract_hyperframes_narration(script.read_text(encoding="utf-8"))
    result = NarrationGenerator(settings, ffmpeg).run(
        narration, output, target_seconds=target_seconds
    )
    console.print(f"[bold green]Narration complete:[/] {result.value}")
    console.print(f"Provider: {result.provider}")
    console.print(f"Duration: {ffmpeg.duration(result.value):.3f}s")
    console.print(f"Exact captions: {output / 'narration.exact.srt'}")


@app.command("short-manifest")
def short_manifest_command(
    spec: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(..., dir_okay=False),
) -> None:
    """Validate a Shorts growth experiment and write its measurement manifest."""
    result = write_short_experiment_manifest(spec, output)
    console.print(f"[bold green]Short experiment ready:[/] {result}")


@app.command("original-music")
def original_music_command(
    duration: float = typer.Option(..., min=1, max=3600),
    output: Path = typer.Option(..., dir_okay=False),
) -> None:
    """Generate a deterministic, original, narration-safe music bed."""
    result = generate_original_music(duration, output)
    console.print(f"[bold green]Original music ready:[/] {result}")


@app.command("short-sfx")
def short_sfx_command(
    output: Path = typer.Option(..., file_okay=False, help="Directory for generated WAV cues."),
) -> None:
    """Generate the deterministic, royalty-free micro-SFX kit used by Shorts."""
    results = generate_short_sfx_set(output)
    console.print(f"[bold green]Short SFX kit ready:[/] {len(results)} cues in {output}")


@app.command("verify-shorts-delivery")
def verify_shorts_delivery_command(
    video: Path = typer.Option(..., exists=True, dir_okay=False),
    thumbnail: Path = typer.Option(..., exists=True, dir_okay=False),
    upload_package: Path | None = typer.Option(None, exists=True, dir_okay=False),
    voice_manifest: Path | None = typer.Option(None, exists=True, dir_okay=False),
    expected_voice: str | None = typer.Option(None),
    min_seconds: float = typer.Option(20, min=1),
    max_seconds: float = typer.Option(30, min=1),
) -> None:
    """Reject an incomplete Shorts handoff before it reaches the upload queue."""
    try:
        report = validate_short_delivery(
            video,
            thumbnail,
            upload_package=upload_package,
            voice_manifest=voice_manifest,
            expected_voice=expected_voice,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
        )
    except ShortsDeliveryError as exc:
        console.print(f"[bold red]Shorts delivery failed:[/] {exc}")
        raise typer.Exit(1) from exc
    console.print("[bold green]Shorts delivery verified[/]")
    console.print_json(data=report)


@app.command("render-shorts-batch")
def render_shorts_batch_command(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False, help="Shorts batch JSON manifest."),
    resume: bool = typer.Option(
        True, "--resume/--fresh", help="Skip only unchanged, previously verified deliveries."
    ),
    dry_run: bool = typer.Option(False, help="Preview render and mastering jobs without encoding."),
) -> None:
    """Render a local Shorts batch with the approved voice and delivery gates."""
    try:
        report = run_shorts_batch(manifest, resume=resume, dry_run=dry_run)
    except ShortsBatchError as exc:
        console.print(f"[bold red]Shorts batch failed:[/] {exc}")
        raise typer.Exit(1) from exc
    console.print_json(data=report)
    if report["status"] == "failed":
        raise typer.Exit(1)


@app.command("verify-youtube-delivery")
def verify_youtube_delivery_command(
    video: Path = typer.Option(..., exists=True, dir_okay=False),
    thumbnail: Path = typer.Option(..., exists=True, dir_okay=False),
    upload_package: Path = typer.Option(..., exists=True, dir_okay=False),
    min_seconds: float = typer.Option(300, min=1),
    max_seconds: float = typer.Option(360, min=1),
) -> None:
    """Reject an incomplete long-form YouTube package before upload."""
    try:
        report = validate_youtube_delivery(
            video,
            thumbnail,
            upload_package,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
        )
    except YouTubeDeliveryError as exc:
        console.print(f"[bold red]YouTube delivery failed:[/] {exc}")
        raise typer.Exit(1) from exc
    console.print("[bold green]YouTube delivery verified[/]")
    console.print_json(data=report)


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
