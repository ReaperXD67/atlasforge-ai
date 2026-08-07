from __future__ import annotations

from pathlib import Path

import pytest

from daily_video_factory.config import Settings, load_settings


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

