from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer import BadParameter
from typer.testing import CliRunner

from daily_video_factory import social_cli
from daily_video_factory.social_analytics import SocialAnalyticsStore

runner = CliRunner()


def metric_record(**overrides) -> dict[str, object]:
    return {
        "platform": "youtube", "account_id": "channel1", "video_id": "v1",
        "experiment_id": "hook1", "variant": "a", "published_at": "2026-11-01T12:00:00Z",
        "observed_at": "2026-11-04T12:00:00Z", "views": 100, "shares": 4,
        **overrides,
    }


def test_social_help_exposes_operator_commands() -> None:
    result = runner.invoke(social_cli.app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "doctor", "enqueue", "status", "run-due", "watch", "import-metrics", "report", "retry-blocked",
        "hold", "resume",
    ):
        assert command in result.output


def test_doctor_with_no_connections_is_read_only(tmp_path: Path, monkeypatch, settings) -> None:
    monkeypatch.setattr(social_cli, "load_settings", lambda path: settings)
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRETS_FILE", str(tmp_path / "missing-client.json"))
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(tmp_path / "missing-token.json"))
    for name in ("META_GRAPH_VERSION", "META_PAGE_ID", "META_INSTAGRAM_ACCOUNT_ID", "META_PAGE_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    def unexpected_request(*args, **kwargs):
        raise AssertionError("doctor must not make network requests")

    monkeypatch.setattr("httpx.Client.request", unexpected_request)
    result = runner.invoke(social_cli.app, ["doctor"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["youtube"]["authorized"] is False
    assert report["meta"]["instagram"]["configured"] is False
    assert report["meta"]["facebook"]["configured"] is False
    assert report["meta"]["authorization_verified"] is False


def test_empty_report_writes_honest_json_artifact(tmp_path: Path) -> None:
    database = tmp_path / "metrics.sqlite"
    output = tmp_path / "reports" / "report.json"
    result = runner.invoke(social_cli.app, ["report", "--database", str(database), "--output", str(output)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report == json.loads(output.read_text(encoding="utf-8"))
    assert report["data_status"] == "no_observations"
    assert report["cohorts"] == []


def test_cli_import_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "observations.json"
    source.write_text(json.dumps([metric_record()]), encoding="utf-8")
    args = ["import-metrics", "--source", str(source), "--database", str(tmp_path / "metrics.sqlite")]
    first = runner.invoke(social_cli.app, args)
    second = runner.invoke(social_cli.app, args)
    assert first.exit_code == second.exit_code == 0
    assert json.loads(first.output)["inserted"] == 1
    assert json.loads(second.output) == {"inserted": 0, "updated": 0, "unchanged": 1}


@pytest.mark.parametrize("record", [
    metric_record(access_token="DO-NOT-PRINT-THIS-TOKEN"),
    metric_record(views="https://cdn.example/video.mp4?signature=DO-NOT-PRINT-THIS-SIGNATURE"),
    metric_record(platform="secret-token-platform"),
])
def test_invalid_import_omits_raw_inputs_and_commits_nothing(tmp_path: Path, record) -> None:
    source = tmp_path / "observations.json"
    source.write_text(json.dumps([metric_record(video_id="valid"), record]), encoding="utf-8")
    database = tmp_path / "metrics.sqlite"
    result = runner.invoke(social_cli.app, ["import-metrics", "--source", str(source), "--database", str(database)])
    assert result.exit_code != 0
    for secret in ("DO-NOT-PRINT", "cdn.example", "secret-token-platform"):
        assert secret not in result.output
    assert SocialAnalyticsStore(database).report()["snapshot_count"] == 0


def test_invalid_report_window_is_actionable_without_traceback(tmp_path: Path) -> None:
    result = runner.invoke(social_cli.app, [
        "report", "--database", str(tmp_path / "metrics.sqlite"),
        "--window-hours", "24", "--tolerance-hours", "48",
    ])
    assert result.exit_code != 0
    assert "window" in result.output
    assert "Traceback" not in result.output


def test_report_rejects_corrupted_database_without_echoing_payload(tmp_path: Path) -> None:
    database = tmp_path / "metrics.sqlite"
    SocialAnalyticsStore(database)
    malformed = metric_record(views="https://cdn.example/media?signature=DO-NOT-PRINT")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO social_observations VALUES (?, ?, ?, ?, ?)",
            ("youtube", "channel1", "v1", "2026-11-04T12:00:00Z", json.dumps(malformed)),
        )
    result = runner.invoke(social_cli.app, ["report", "--database", str(database)])
    assert result.exit_code != 0
    assert "DO-NOT-PRINT" not in result.output
    assert "cdn.example" not in result.output


@pytest.mark.parametrize("execute", [False, True])
def test_due_queue_is_preview_until_execute_is_explicit(monkeypatch, execute: bool) -> None:
    calls = []

    class Manager:
        def run_due(self, **kwargs):
            calls.append(kwargs)
            return [{"state": "published" if kwargs["execute"] else "pending", "dry_run": not kwargs["execute"]}]

    monkeypatch.setattr(social_cli, "_manager", lambda *args: Manager())
    args = ["run-due", "--limit", "2"] + (["--execute"] if execute else [])
    result = runner.invoke(social_cli.app, args)
    assert result.exit_code == 0
    assert calls == [{"execute": execute, "limit": 2}]
    assert json.loads(result.output)[0]["dry_run"] is not execute


def test_invalid_queue_limit_never_creates_manager(monkeypatch) -> None:
    def unexpected_manager(*args):
        raise AssertionError("invalid queue arguments must not open a manager")

    monkeypatch.setattr(social_cli, "_manager", unexpected_manager)
    result = runner.invoke(social_cli.app, ["run-due", "--limit", "0", "--execute"])
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)
    error = result.exception.__context__
    assert isinstance(error, BadParameter)
    assert error.param.name == "limit"


def test_enqueue_failure_does_not_echo_external_exception(tmp_path: Path, monkeypatch) -> None:
    campaign = tmp_path / "campaign.json"
    campaign.write_text("{}", encoding="utf-8")

    class Manager:
        def enqueue(self, path):
            raise ValueError("https://cdn.example/video?signature=DO-NOT-PRINT-THIS-TOKEN")

    monkeypatch.setattr(social_cli, "_manager", lambda *args: Manager())
    result = runner.invoke(social_cli.app, ["enqueue", "--campaign", str(campaign)])
    assert result.exit_code != 0
    assert "DO-NOT-PRINT" not in result.output
    assert "cdn.example" not in result.output


def test_status_reads_manager_without_running_jobs(monkeypatch) -> None:
    class Manager:
        def list_posts(self):
            return [{"post_id": "post1", "state": "pending"}]

        def run_due(self, **kwargs):
            raise AssertionError("status must not publish")

    monkeypatch.setattr(social_cli, "_manager", lambda *args: Manager())
    result = runner.invoke(social_cli.app, ["status"])
    assert result.exit_code == 0
    assert json.loads(result.output) == [{"post_id": "post1", "state": "pending"}]


@pytest.mark.parametrize("state", ["blocked", "uncertain"])
def test_failed_execute_returns_nonzero_after_structured_result(monkeypatch, state: str) -> None:
    class Manager:
        def run_due(self, **kwargs):
            return [{"post_key": "campaign:post", "state": state}]

    monkeypatch.setattr(social_cli, "_manager", lambda *args: Manager())
    result = runner.invoke(social_cli.app, ["run-due", "--execute"])
    assert result.exit_code == 1
    assert json.loads(result.output) == [{"post_key": "campaign:post", "state": state}]


def test_retry_blocked_forwards_exact_post_key_without_publishing(monkeypatch) -> None:
    calls = []

    class Manager:
        def retry_blocked(self, key):
            calls.append(key)
            return {"post_key": key, "state": "pending"}

    monkeypatch.setattr(social_cli, "_manager", lambda *args: Manager())
    result = runner.invoke(social_cli.app, ["retry-blocked", "--post-key", "campaign:post"])
    assert result.exit_code == 0
    assert calls == ["campaign:post"]
    assert json.loads(result.output)["state"] == "pending"


def test_database_failure_is_nonzero_and_does_not_echo_exception(monkeypatch) -> None:
    def failed_manager(*args):
        raise sqlite3.OperationalError("private database path DO-NOT-PRINT")

    monkeypatch.setattr(social_cli, "_manager", failed_manager)
    result = runner.invoke(social_cli.app, ["status"])
    assert result.exit_code != 0
    assert "DO-NOT-PRINT" not in result.output
    assert "worker lock" in result.output


@pytest.mark.parametrize("command,expected_state", [("hold", "held"), ("resume", "pending")])
def test_hold_resume_forwards_an_exact_group_without_running_worker(monkeypatch, command, expected_state):
    calls = []

    class Manager:
        def hold_posts(self, keys):
            calls.append(("hold", keys))
            return [{"post_key": key, "state": "held"} for key in keys]

        def resume_posts(self, keys):
            calls.append(("resume", keys))
            return [{"post_key": key, "state": "pending"} for key in keys]

        def run_due(self, **kwargs):
            raise AssertionError("hold/resume must not run publication")

    monkeypatch.setattr(social_cli, "_manager", lambda *args: Manager())
    result = runner.invoke(social_cli.app, [
        command, "--post-key", "campaign:one", "--post-key", "campaign:two",
    ])
    assert result.exit_code == 0
    assert calls == [(command, ["campaign:one", "campaign:two"])]
    assert {row["state"] for row in json.loads(result.output)} == {expected_state}


@pytest.mark.parametrize("command", ["hold", "resume"])
def test_hold_resume_requires_explicit_selection_and_redacts_failure(monkeypatch, command):
    class Manager:
        def hold_posts(self, keys):
            raise RuntimeError("https://private.example/?token=DO-NOT-PRINT")

        resume_posts = hold_posts

    monkeypatch.setattr(social_cli, "_manager", lambda *args: Manager())
    assert runner.invoke(social_cli.app, [command]).exit_code != 0
    result = runner.invoke(social_cli.app, [command, "--post-key", "campaign:one"])
    assert result.exit_code != 0
    assert "DO-NOT-PRINT" not in result.output
    assert "private.example" not in result.output
