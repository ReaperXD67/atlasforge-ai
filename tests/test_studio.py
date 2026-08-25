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
    assert rendered.script.min_words == 224
    assert rendered.script.max_words == 308
    assert rendered.video.fps == 30
    assert rendered.video.crf == 23
    assert rendered.video.stock_video_enabled is False
    assert rendered.video.local_generation_enabled is False
    assert rendered.images.providers == ["title_card"]
    assert rendered.subtitles.burn_in is False
    assert rendered.storyboard.engagement_mode == "retention"
    assert rendered.storyboard.target_scene_seconds == 6
    assert rendered.voice.providers[0] == "chatterbox"


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
        music_gap_provider="local_wan",
        music_visual_direction="Adult smokers in a neon race garage with wet asphalt",
        music_hook_words="LIGHT IT UP, REDLINE",
        music_edit_style="flash_editorial",
    )
    assert request.music_visual_direction.startswith("Adult smokers")
    assert request.music_hook_words == "LIGHT IT UP, REDLINE"
    assert request.music_edit_style == "flash_editorial"
    studio._render_job_config(request, destination)
    rendered = load_settings(destination)
    assert rendered.video.transition_seconds == 4 / rendered.video.fps
    assert rendered.video.stock_video_max_scenes_per_video == 64
    assert rendered.images.providers == ["title_card"]
    assert rendered.subtitles.burn_in is False
    assert rendered.video.local_generation_enabled is True
    assert rendered.video.local_generation_max_scenes_per_video == 2
    assert rendered.video.enable_premium_scenes is False
    assert rendered.publishing.enabled is False


def test_studio_music_mode_can_arm_cloud_gap_rescue(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    destination = tmp_path / "music-cloud-job.yaml"
    studio._render_job_config(
        StudioJobRequest(
            profile="atomy-us-openrouter",
            mode="music_film",
            music_upload_id="0123456789abcdef",
            local_ai=True,
            music_gap_provider="gemini_omni",
        ),
        destination,
    )
    rendered = load_settings(destination)

    assert rendered.video.enable_premium_scenes is True
    assert rendered.video.premium_providers == ["gemini_omni"]
    assert rendered.video.premium_max_scenes_per_video == 2
    assert rendered.video.local_generation_enabled is False


def test_studio_music_mode_arms_fail_closed_malaysian_duet(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    destination = tmp_path / "malaysian-duet.yaml"

    studio._render_job_config(
        StudioJobRequest(
            profile="atomy-us-openrouter",
            mode="music_film",
            music_upload_id="0123456789abcdef",
            music_performer_mode="malaysian_duet",
            music_performer_mix=0.3,
            music_performer_budget_usd=9,
        ),
        destination,
    )
    rendered = load_settings(destination)

    assert rendered.video.performance_generation_enabled is True
    assert rendered.video.performance_mix_ratio == 0.3
    assert rendered.video.performance_daily_budget_usd == 9
    assert rendered.video.performance_preflight_enabled is True
    assert rendered.video.performance_require_all_scenes is True


def test_studio_refuses_paid_duet_before_job_when_fal_key_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("FAL_KEY", raising=False)
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    upload_id, music = studio.reserve_music_upload("song.wav")
    music.write_bytes(b"not-decoded-because-create-only")
    request = StudioJobRequest(
        profile="atomy-us-openrouter",
        mode="music_film",
        music_upload_id=upload_id,
        music_performer_mode="malaysian_duet",
    )

    try:
        studio.create(request)
    except RuntimeError as exc:
        assert "no paid generation was started" in str(exc)
    else:
        raise AssertionError("A missing FAL key must stop before process creation")

    assert studio.list_jobs() == []


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


def test_studio_viral_mode_uses_vertical_local_contract(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    destination = tmp_path / "viral-job.yaml"
    request = StudioJobRequest(
        profile="atomy-us-openrouter",
        mode="viral_short",
        viral_prompt="A ginger cat dancing in a premium garage",
        viral_recipe="beat_creature",
        viral_provider="local_wan",
        viral_seconds=8,
        viral_candidates=3,
    )

    studio._render_job_config(request, destination)
    rendered = load_settings(destination)

    assert (rendered.video.width, rendered.video.height) == (1080, 1920)
    assert (rendered.video.comfyui_width, rendered.video.comfyui_height) == (576, 1024)
    assert rendered.video.comfyui_frames == 193
    assert rendered.video.comfyui_steps == 28
    assert rendered.video.comfyui_rife_enabled is True
    assert rendered.video.interpolate_low_fps_clips is False
    assert rendered.video.local_generation_enabled is True
    assert rendered.video.local_generation_candidates == 3
    assert rendered.video.enable_premium_scenes is False
    assert rendered.subtitles.burn_in is False
    assert rendered.publishing.enabled is False


def test_studio_resolves_only_supported_reference_uploads(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    upload_id, path = studio.reserve_reference_upload("hero-cat.webp")
    path.write_bytes(b"image")
    assert studio.reference_upload_path(upload_id) == path.resolve()
    assert studio.reference_upload_path("../../escape") is None


def test_studio_resolves_only_supported_voice_uploads(tmp_path: Path) -> None:
    settings = load_settings(
        Path("config/profiles/atomy-us-openrouter.yaml"),
        overrides={"runtime": {"output_directory": str(tmp_path / "output")}},
    )
    studio = StudioManager(settings, Path("config/profiles"))
    upload_id, path = studio.reserve_voice_upload("consented-voice.wav")
    path.write_bytes(b"voice")
    assert studio.voice_upload_path(upload_id) == path.resolve()
    assert studio.voice_upload_path("../../escape") is None
