from pathlib import Path

from daily_video_factory.config import load_settings
from daily_video_factory.studio import StudioJobRequest, StudioManager


def test_studio_lists_composable_profiles(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    profile_ids = {str(item["id"]) for item in studio.profiles()}
    assert "atomy-us-openrouter" in profile_ids
    assert "general-explainer" in profile_ids


def test_studio_renders_safe_job_overrides(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    destination = tmp_path / "job.yaml"
    request = StudioJobRequest(
        profile="atomy-us-openrouter",
        duration_minutes=2,
        fps=30,
        quality="fast",
        stock_images=False,
        captions=False,
    )
    studio._render_job_config(request, destination)
    rendered = load_settings(destination)
    assert rendered.script.target_minutes == 2
    assert rendered.video.fps == 30
    assert rendered.video.crf == 23
    assert rendered.images.providers == ["title_card"]
    assert rendered.subtitles.burn_in is False
