from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from daily_video_factory.cli import app
from daily_video_factory.config import Settings
from daily_video_factory.publishing.youtube import YOUTUBE_SCOPES, YouTubePublisher


@pytest.mark.parametrize("no_browser", [False, True])
def test_cli_oauth_controls_browser_without_changing_loopback_or_scopes(
    no_browser: bool, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = tmp_path / "client.json"
    client.write_text("{}", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text("{}", encoding="utf-8")
    token = tmp_path / "token.json"
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRETS_FILE", str(client))
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(token))
    monkeypatch.setattr("daily_video_factory.cli.load_settings", lambda _: settings)
    captured = {}

    def run_local_server(**kwargs):
        captured.update(kwargs)
        # The SDK prints the official URL even when browser opening is disabled.
        print("Please visit https://accounts.google.com/o/oauth2/auth?test=fixture")
        return SimpleNamespace(to_json=lambda: '{"fixture":"saved"}')

    def from_client_secrets_file(filename, scopes):
        captured["filename"] = filename
        captured["scopes"] = scopes
        return SimpleNamespace(run_local_server=run_local_server)

    def build(api, version, **kwargs):
        captured["api"] = (api, version, kwargs["cache_discovery"])
        return object()

    monkeypatch.setattr(YouTubePublisher, "_imports", lambda _: (
        None, None, SimpleNamespace(from_client_secrets_file=from_client_secrets_file),
        build, None,
    ))
    arguments = ["youtube-auth", "--config", str(config)]
    if no_browser:
        arguments.append("--no-browser")
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 0, result.output
    assert captured["open_browser"] is (not no_browser)
    assert captured["host"] == "127.0.0.1" and captured["port"] == 0
    assert captured["access_type"] == "offline" and captured["prompt"] == "consent"
    assert captured["scopes"] == list(YOUTUBE_SCOPES)
    assert captured["filename"] == str(client)
    assert captured["api"] == ("youtube", "v3", False)
    assert "https://accounts.google.com/" in result.output
    assert token.read_text(encoding="utf-8") == '{"fixture":"saved"}'
