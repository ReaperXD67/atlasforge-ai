from pathlib import Path

from daily_video_factory.config import load_settings


def test_loads_default_configuration() -> None:
    settings = load_settings(Path("config/default.yaml"))
    assert settings.video.width == 1920
    assert settings.video.enable_premium_scenes is False
    assert settings.video.stock_video_enabled is True
    assert settings.video.stock_video_semantic_ranking is True
    assert settings.video.local_generation_enabled is True
    assert settings.voice.kokoro_speed == 0.98
    assert settings.publishing.enabled is False
    assert settings.script.text_providers[0] == "gemini"


def test_environment_output_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OUTPUT_DIRECTORY", str(tmp_path / "custom"))
    settings = load_settings(Path("config/default.yaml"))
    assert settings.output_directory == tmp_path / "custom"


def test_environment_model_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MODEL_DIRECTORY", str(tmp_path / "models"))
    settings = load_settings(Path("config/default.yaml"))
    assert settings.model_directory == tmp_path / "models"


def test_profile_inherits_default_configuration() -> None:
    settings = load_settings(Path("config/profiles/atomy-us-openrouter.yaml"))
    assert settings.video.fps == 60
    assert settings.script.text_providers == ["openrouter"]
    assert settings.voice.providers == ["chatterbox", "kokoro"]
    assert settings.subtitles.whisper_compute_type == "int8"


def test_general_profile_disables_required_brand() -> None:
    settings = load_settings(Path("config/profiles/general-explainer.yaml"))
    assert settings.channel.brand_required is False
    assert settings.channel.brand_name == ""
