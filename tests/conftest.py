from __future__ import annotations

from pathlib import Path

import pytest

from daily_video_factory.config import Settings, load_settings


@pytest.fixture(autouse=True)
def isolated_publishing_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on or reuse this workstation's connected accounts."""
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRETS_FILE", str(tmp_path / "youtube-client.json"))
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(tmp_path / "youtube-token.json"))
    # Set empty values instead of removing them so load_dotenv cannot restore real tokens.
    for name in (
        "META_GRAPH_VERSION", "META_PAGE_ID", "META_INSTAGRAM_ACCOUNT_ID", "META_PAGE_ACCESS_TOKEN",
    ):
        monkeypatch.setenv(name, "")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings(
        Path("config/default.yaml"),
        overrides={
            "runtime": {"output_directory": str(tmp_path / "output")},
            "script": {
                "min_words": 100,
                "max_words": 2000,
                "brand_mention_min_fraction": 0.5,
            },
        },
    )
