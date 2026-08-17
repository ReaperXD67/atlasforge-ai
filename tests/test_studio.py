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
    assert rendered.script.min_words == 246
    assert rendered.script.max_words == 313
    assert rendered.video.fps == 30
    assert rendered.video.crf == 23
    assert rendered.video.stock_video_enabled is False
    assert rendered.video.local_generation_enabled is False
    assert rendered.images.providers == ["title_card"]
    assert rendered.subtitles.burn_in is False


def test_studio_music_mode_is_beat_cut_and_keeps_publishing_off(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    destination = tmp_path / "music-job.yaml"
    request = StudioJobRequest(
        profile="atomy-us-openrouter",
        mode="music_film",
        music_upload_id="0123456789abcdef",
        local_ai=True,
    )
    studio._render_job_config(request, destination)
    rendered = load_settings(destination)
    assert rendered.video.transition_seconds == 0.0
    assert rendered.video.stock_video_max_scenes_per_video == 64
    assert rendered.images.providers == ["title_card"]
    assert rendered.subtitles.burn_in is False
    assert rendered.publishing.enabled is False


def test_studio_resolves_only_supported_music_uploads(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    upload_id, path = studio.reserve_music_upload("launch-track.mp3")
    path.write_bytes(b"music")
    (studio.upload_root / f"{upload_id}.json").write_text("{}", encoding="utf-8")
    assert studio.music_upload_path(upload_id) == path.resolve()
    assert studio.music_upload_path("../../escape") is None
