from datetime import date
from pathlib import Path

import pytest

from daily_video_factory.exceptions import AlreadyPublished
from daily_video_factory.models import RunManifest, RunStatus, StageStatus
from daily_video_factory.state import RunStore


def test_store_persists_manifest_and_stages(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    manifest = RunManifest(
        run_id="2026-08-07-test",
        publication_date=date(2026, 8, 7),
        status=RunStatus.running,
        output_root=tmp_path / "run",
    )
    store.save_manifest(manifest)
    store.stage(manifest.run_id, "research", StageStatus.running)
    store.stage(manifest.run_id, "research", StageStatus.completed)
    assert store.stage_completed(manifest.run_id, "research")
    assert store.latest_resumable(date(2026, 8, 7)).run_id == manifest.run_id


def test_store_blocks_a_second_published_run(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    manifest = RunManifest(
        run_id="2026-08-07-published",
        publication_date=date(2026, 8, 7),
        status=RunStatus.published,
        output_root=tmp_path / "run",
    )
    store.save_manifest(manifest)
    with pytest.raises(AlreadyPublished):
        store.assert_not_published(date(2026, 8, 7))
