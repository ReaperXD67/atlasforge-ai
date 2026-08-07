from pathlib import Path

from daily_video_factory.config import load_settings


def test_loads_default_configuration() -> None:
    settings = load_settings(Path("config/default.yaml"))
    assert settings.video.width == 1920
    assert settings.video.enable_premium_scenes is False
    assert settings.publishing.enabled is False
    assert settings.script.text_providers[0] == "gemini"


def test_environment_output_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OUTPUT_DIRECTORY", str(tmp_path / "custom"))
    settings = load_settings(Path("config/default.yaml"))
    assert settings.output_directory == tmp_path / "custom"

