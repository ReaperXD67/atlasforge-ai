from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import portalocker

from .exceptions import AlreadyPublished
from .models import RunManifest, StageStatus


class RunStore:
    def __init__(self, output_root: Path) -> None:
        output_root.mkdir(parents=True, exist_ok=True)
        self.db_path = output_root / "runs.sqlite3"
        self.lock_path = output_root / "pipeline.lock"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    publication_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_root TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_published_per_day
                ON runs(publication_date) WHERE status = 'published';
                CREATE TABLE IF NOT EXISTS stages (
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 1,
                    message TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    PRIMARY KEY (run_id, stage),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )

    @contextmanager
    def exclusive(self, timeout_seconds: int = 1) -> Iterator[None]:
        with portalocker.Lock(self.lock_path, timeout=timeout_seconds):
            yield

    def assert_not_published(self, publication_date: date) -> None:
        with self._connect() as db:
            row = db.execute(
                "SELECT run_id FROM runs WHERE publication_date=? AND status='published' LIMIT 1",
                (publication_date.isoformat(),),
            ).fetchone()
        if row:
            raise AlreadyPublished(
                f"A video is already published for {publication_date}: {row['run_id']}"
            )

    def save_manifest(self, manifest: RunManifest) -> None:
        now = datetime.now(UTC).isoformat()
        payload = manifest.model_dump_json()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO runs(run_id, publication_date, status, output_root, manifest_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    output_root=excluded.output_root,
                    manifest_json=excluded.manifest_json,
                    updated_at=excluded.updated_at
                """,
                (
                    manifest.run_id,
                    manifest.publication_date.isoformat(),
                    manifest.status.value,
                    str(manifest.output_root),
                    payload,
                    now,
                    now,
                ),
            )

    def stage(self, run_id: str, stage: str, status: StageStatus, message: str = "") -> None:
        now = datetime.now(UTC).isoformat()
        finished = now if status in {StageStatus.completed, StageStatus.skipped, StageStatus.failed} else None
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO stages(run_id, stage, status, message, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, stage) DO UPDATE SET
                    status=excluded.status,
                    attempt=CASE WHEN excluded.status='running' THEN stages.attempt+1 ELSE stages.attempt END,
                    message=excluded.message,
                    finished_at=excluded.finished_at
                """,
                (run_id, stage, status.value, message, now, finished),
            )

    def stage_completed(self, run_id: str, stage: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT status FROM stages WHERE run_id=? AND stage=?", (run_id, stage)
            ).fetchone()
        return bool(row and row["status"] == StageStatus.completed.value)

    def list_runs(self, limit: int = 50) -> list[dict[str, object]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT manifest_json FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["manifest_json"]) for row in rows]

    def latest_resumable(self, publication_date: date) -> RunManifest | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT manifest_json FROM runs
                WHERE publication_date=? AND status IN ('queued','running','failed','ready')
                ORDER BY updated_at DESC LIMIT 1
                """,
                (publication_date.isoformat(),),
            ).fetchone()
        return RunManifest.model_validate_json(row["manifest_json"]) if row else None

