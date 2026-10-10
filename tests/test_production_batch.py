from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from typer.testing import CliRunner

from daily_video_factory import shorts_batch
from daily_video_factory.cli import app
from daily_video_factory.production_batch import (
    ProductionBatchError,
    load_production_batch_manifest,
    run_production_batch,
    source_fingerprint,
)


@pytest.fixture
def production(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, list[list[str]]]:
    root = tmp_path / "repository"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "render_hyperframes_windows.ps1").write_text("# wrapper")
    rows = []
    for episode_id, format_name in (("question-short", "shorts"), ("answer-video", "youtube")):
        project = root / "videos" / episode_id
        (project / "assets").mkdir(parents=True)
        (project / "package.json").write_text('{"scripts":{"render":"npx hyperframes@0.8.127"}}')
        (project / "index.html").write_text("<main>Assembled video</main>")
        Image.new("RGB", (1080, 1920) if format_name == "shorts" else (1920, 1080)).save(
            project / "assets" / "thumbnail.png"
        )
        title = "Find the real cost before starting"
        description = "Compare revenue and costs; an example is not an earnings forecast."
        if format_name == "youtube":
            description += "\n\n00:00 The question\n00:30 Revenue versus profit\n02:00 A worked example"
        (project / "UPLOAD_PACKAGE.md").write_text(
            f"## Title\n{title}\n\n## Description\n{description}\n\n"
            "## Hashtags\n#Atomy #Business #Education\n"
        )
        (project / "audio_request.json").write_text('{"provider":"kokoro","voice":"af_heart"}')
        (project / "SCRIPT.md").write_text(
            "What did it really cost? Revenue is not profit. Subtract all the costs first."
        )
        (project / "THUMBNAIL_COPY.txt").write_text("REAL COST?")
        beats = [0, 10, 20] if format_name == "shorts" else list(range(0, 301, 30))
        (project / "EDITORIAL.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "script": "SCRIPT.md",
                    "thumbnail_copy": "THUMBNAIL_COPY.txt",
                    "audience_problem": "Beginners confuse revenue with profit",
                    "hook": {"text": "What did it really cost?", "at_seconds": 0},
                    "payoff": {
                        "text": "Subtract all the costs first.",
                        "at_seconds": 23 if format_name == "shorts" else 290,
                    },
                    "packaging": {
                        "title": title,
                        "thumbnail_text": "REAL COST?",
                        "promise": "A cost checklist, not an earnings promise",
                        "evidence_anchor": "Subtract all the costs first.",
                        "reviewed": True,
                    },
                    "sources": [
                        {
                            "claim": "Revenue does not imply profit",
                            "url": "https://www.ftc.gov/business-guidance",
                            "checked_on": "2026-10-10",
                        }
                    ],
                    "retention_beats": [{"at_seconds": time, "purpose": "reveal"} for time in beats],
                }
            )
        )
        rows.append(
            {
                "id": episode_id,
                "project": f"videos/{episode_id}",
                "output": "renders/final.mp4",
                "thumbnail": "assets/thumbnail.png",
                "upload_package": "UPLOAD_PACKAGE.md",
                "voice_manifest": "audio_request.json",
                "editorial_manifest": "EDITORIAL.json",
                "format": format_name,
            }
        )
    manifest = root / "production.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "mixed-test",
                "expected_voice": "af_heart",
                "episodes": rows,
            }
        )
    )
    commands: list[list[str]] = []

    def fake_command(command: list[str], *, cwd: Path) -> None:
        commands.append(command)
        output = Path(command[-1] if command[0] == "ffmpeg" else command[command.index("-Output") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(f"fresh video {len(commands)}".encode())

    def probe(video: Path) -> dict[str, Any]:
        longform = "answer-video" in str(video)
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "pix_fmt": "yuv420p",
                    "width": 1920 if longform else 1080,
                    "height": 1080 if longform else 1920,
                    "avg_frame_rate": "30/1",
                },
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
            ],
            "format": {"duration": "315" if longform else "27"},
        }

    monkeypatch.setattr(shorts_batch, "_powershell", lambda: "powershell")
    monkeypatch.setattr(shorts_batch, "_run_command", fake_command)
    monkeypatch.setattr("daily_video_factory.shorts_delivery._probe", probe)
    monkeypatch.setattr("daily_video_factory.youtube_delivery._probe", probe)
    return root, manifest, commands


def _change_row(manifest: Path, **changes: Any) -> None:
    payload = json.loads(manifest.read_text())
    payload["episodes"][0].update(changes)
    manifest.write_text(json.dumps(payload))


def _change_editorial(root: Path, **changes: Any) -> None:
    path = root / "videos" / "question-short" / "EDITORIAL.json"
    payload = json.loads(path.read_text())
    payload.update(changes)
    path.write_text(json.dumps(payload))


def test_mixed_batch_routes_formats_duration_bounds_and_resumes(
    production: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest, commands = production
    first = run_production_batch(manifest, repository_root=root)
    assert first["status"] == "verified"
    assert first["format_counts"] == {"shorts": 1, "youtube": 1}
    assert len(commands) == 4
    assert "-VerifyShorts" in commands[0] and "-VerifyYouTube" not in commands[0]
    assert commands[0][commands[0].index("-MaxDuration") + 1] == "35"
    assert commands[0][commands[0].index("-CheckSamples") + 1] == "17"
    assert "-VerifyYouTube" in commands[2] and "-VerifyShorts" not in commands[2]
    assert commands[2][commands[2].index("-MinDuration") + 1] == "300"
    assert commands[2][commands[2].index("-MaxDuration") + 1] == "360"
    assert commands[2][commands[2].index("-CheckSamples") + 1] == "60"
    assert [item["report"]["voice"]["voice"] for item in first["episodes"]] == ["af_heart"] * 2
    assert all(not item["report"]["editorial"]["analytics_observed"] for item in first["episodes"])
    assert (root / "PRODUCTION_BATCH_REPORT.json").is_file()
    assert not (root / "BATCH_REPORT.json").exists()
    commands.clear()
    second = run_production_batch(manifest, repository_root=root)
    assert second["status"] == "verified"
    assert all(item["resumed"] for item in second["episodes"])
    assert commands == []


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"format": "vertical"}, "format"),
        ({"format": []}, "format"),
        ({"min_seconds": True}, "finite number"),
        ({"max_seconds": float("nan")}, "finite number"),
        ({"min_seconds": 40, "max_seconds": 35}, "duration bounds"),
        ({"min_seconds": 35, "max_seconds": 35}, "duration bounds"),
        ({"max_seconds": 181}, "180 seconds"),
        ({"editorial_manifest": "../../outside.json"}, "escapes"),
        ({"editorial_manifest": "renders/final.mp4"}, "conflicts"),
    ],
)
def test_production_manifest_rejects_bad_formats_bounds_and_paths(
    production: tuple[Path, Path, list[list[str]]], changes: dict[str, Any], message: str
) -> None:
    root, manifest, _ = production
    _change_row(manifest, **changes)
    with pytest.raises(ValueError, match=message):
        load_production_batch_manifest(manifest, repository_root=root)


def test_duplicate_project_is_rejected(production: tuple[Path, Path, list[list[str]]]) -> None:
    root, manifest, _ = production
    payload = json.loads(manifest.read_text())
    payload["episodes"][1]["project"] = payload["episodes"][0]["project"]
    payload["episodes"][1]["output"] = "renders/other.mp4"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ProductionBatchError, match="duplicate episode project"):
        load_production_batch_manifest(manifest, repository_root=root)


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"hook": {"text": "What did it really cost?", "at_seconds": 3}}, "first 2"),
        ({"hook": {"text": "Invented hook", "at_seconds": 0}}, "not anchored"),
        ({"payoff": {"text": "Unspoken conclusion", "at_seconds": 23}}, "not anchored"),
        ({"payoff": {"text": "Subtract all the costs first.", "at_seconds": 40}}, "before the end"),
        ({"retention_beats": [{"at_seconds": 0, "purpose": "hook"}]}, "at least three"),
        (
            {"retention_beats": [{"at_seconds": time, "purpose": "reveal"} for time in [0, 15, 20]]},
            "gaps <= 12",
        ),
        ({"sources": []}, "supported claim"),
        ({"sources": [{"claim": "Fact", "url": "http://example.com", "checked_on": "2026-10-10"}]}, "HTTPS"),
        ({"sources": [{"claim": "Fact", "url": "https://user:pass@example.com", "checked_on": "2026-10-10"}]}, "credential-free"),
        ({"sources": [{"claim": "Fact", "url": "https://example.com", "checked_on": "today"}]}, "YYYY-MM-DD"),
    ],
)
def test_editorial_failure_prevents_bad_episode_but_allows_independent_video(
    production: tuple[Path, Path, list[list[str]]], changes: dict[str, Any], message: str
) -> None:
    root, manifest, commands = production
    _change_editorial(root, **changes)
    result = run_production_batch(manifest, repository_root=root)
    assert result["status"] == "failed"
    assert [item["status"] for item in result["episodes"]] == ["failed", "verified"]
    assert message in result["episodes"][0]["error"]["message"]
    assert len(commands) == 2


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"title": "Misleading replacement title"}, "actual upload title"),
        ({"thumbnail_text": "GUARANTEED MONEY"}, "THUMBNAIL_COPY"),
        ({"evidence_anchor": "Invented proof"}, "literal script evidence"),
        ({"reviewed": False}, "explicit review"),
    ],
)
def test_packaging_gate_requires_script_backed_review_and_exact_copy(
    production: tuple[Path, Path, list[list[str]]], changes: dict[str, Any], message: str
) -> None:
    root, manifest, _ = production
    path = root / "videos" / "question-short" / "EDITORIAL.json"
    editorial = json.loads(path.read_text())
    editorial["packaging"].update(changes)
    path.write_text(json.dumps(editorial))
    result = run_production_batch(manifest, repository_root=root, dry_run=True)
    assert message in result["episodes"][0]["error"]["message"]


@pytest.mark.parametrize("change", ["bounds", "editorial", "script", "thumbnail_copy"])
def test_changed_editorial_or_delivery_contract_invalidates_only_affected_resume(
    production: tuple[Path, Path, list[list[str]]], change: str
) -> None:
    root, manifest, commands = production
    run_production_batch(manifest, repository_root=root)
    if change == "bounds":
        _change_row(manifest, max_seconds=34)
    elif change == "editorial":
        _change_editorial(root, audience_problem="A more specific beginner problem")
    elif change == "script":
        with (root / "videos" / "question-short" / "SCRIPT.md").open("a") as handle:
            handle.write("\nAn extra useful detail.")
    else:
        copy = root / "videos" / "question-short" / "THUMBNAIL_COPY.txt"
        copy.write_text("REAL COST?\n")
    commands.clear()
    second = run_production_batch(manifest, repository_root=root)
    assert second["status"] == "verified"
    assert [item["resumed"] for item in second["episodes"]] == [False, True]
    assert len(commands) == 2


def test_actual_duration_rechecks_payoff_and_retention_not_only_declared_bounds(
    production: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest, _ = production
    _change_editorial(root, payoff={"text": "Subtract all the costs first.", "at_seconds": 30})
    result = run_production_batch(manifest, repository_root=root)
    assert result["episodes"][0]["status"] == "failed"
    assert "before the end" in result["episodes"][0]["error"]["message"]
    assert not (root / "videos" / "question-short" / "renders" / "final.mp4").exists()


def test_missing_longform_chapters_is_rejected_before_encoding(
    production: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest, commands = production
    package = root / "videos" / "answer-video" / "UPLOAD_PACKAGE.md"
    package.write_text("## Title\nFind the real cost before starting\n## Description\nFacts.\n#One #Two #Three")
    result = run_production_batch(manifest, repository_root=root)
    assert result["episodes"][1]["status"] == "failed"
    assert "chapters" in result["episodes"][1]["error"]["message"]
    assert len(commands) == 2


def test_voice_change_rejected_for_longform_too(production: tuple[Path, Path, list[list[str]]]) -> None:
    root, manifest, _ = production
    (root / "videos" / "answer-video" / "audio_request.json").write_text(
        '{"provider":"kokoro","voice":"af_sky"}'
    )
    result = run_production_batch(manifest, repository_root=root, dry_run=True)
    assert result["episodes"][1]["status"] == "failed"
    assert "af_heart" in result["episodes"][1]["error"]["message"]


def test_failed_command_does_not_block_another_format(
    production: tuple[Path, Path, list[list[str]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest, commands = production
    original = shorts_batch._run_command

    def fail_short(command: list[str], *, cwd: Path) -> None:
        if "-VerifyShorts" in command:
            raise subprocess.CalledProcessError(1, command)
        original(command, cwd=cwd)

    monkeypatch.setattr(shorts_batch, "_run_command", fail_short)
    result = run_production_batch(manifest, repository_root=root)
    assert [item["status"] for item in result["episodes"]] == ["failed", "verified"]
    assert len(commands) == 2


def test_sources_changing_mid_render_never_replace_an_existing_final(
    production: tuple[Path, Path, list[list[str]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest, _ = production
    run_production_batch(manifest, repository_root=root)
    final = root / "videos" / "question-short" / "renders" / "final.mp4"
    previous_final = final.read_bytes()
    original = shorts_batch._run_command

    def mutate_source(command: list[str], *, cwd: Path) -> None:
        original(command, cwd=cwd)
        if "-VerifyShorts" in command:
            (root / "videos" / "question-short" / "index.html").write_text("Changed during capture")

    monkeypatch.setattr(shorts_batch, "_run_command", mutate_source)
    result = run_production_batch(manifest, repository_root=root, resume=False)
    assert [item["status"] for item in result["episodes"]] == ["failed", "verified"]
    assert "sources changed during rendering" in result["episodes"][0]["error"]["message"]
    assert final.read_bytes() == previous_final


def test_stale_master_never_replaces_a_verified_final(
    production: tuple[Path, Path, list[list[str]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest, _ = production
    run_production_batch(manifest, repository_root=root)
    short_project = root / "videos" / "question-short"
    previous_final = (short_project / "renders" / "final.mp4").read_bytes()
    stale = short_project / "renders" / ".batch-mastered-question-short.mp4"
    stale.write_bytes(b"stale prior intermediate")
    original = shorts_batch._run_command

    def leave_short_master_unchanged(command: list[str], *, cwd: Path) -> None:
        if command[0] == "ffmpeg" and cwd == short_project:
            return
        original(command, cwd=cwd)

    monkeypatch.setattr(shorts_batch, "_run_command", leave_short_master_unchanged)
    result = run_production_batch(manifest, repository_root=root, resume=False)
    assert [item["status"] for item in result["episodes"]] == ["failed", "verified"]
    assert "stale mastered render" in result["episodes"][0]["error"]["message"]
    assert (short_project / "renders" / "final.mp4").read_bytes() == previous_final


def test_tampered_longform_video_invalidates_only_its_resume(
    production: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest, commands = production
    run_production_batch(manifest, repository_root=root)
    (root / "videos" / "answer-video" / "renders" / "final.mp4").write_bytes(b"different file")
    commands.clear()
    result = run_production_batch(manifest, repository_root=root)
    assert result["status"] == "verified"
    assert [item["resumed"] for item in result["episodes"]] == [True, False]
    assert len(commands) == 2


def test_dry_run_leaves_completed_report_unchanged(
    production: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest, commands = production
    run_production_batch(manifest, repository_root=root)
    saved = (root / "PRODUCTION_BATCH_REPORT.json").read_bytes()
    commands.clear()
    result = run_production_batch(manifest, repository_root=root, dry_run=True)
    assert result["status"] == "dry_run"
    assert [item["status"] for item in result["episodes"]] == ["planned", "planned"]
    assert commands == []
    assert (root / "PRODUCTION_BATCH_REPORT.json").read_bytes() == saved


def test_project_caches_are_still_excluded_from_mixed_resume(
    production: tuple[Path, Path, list[list[str]]],
) -> None:
    root, path, _ = production
    manifest = load_production_batch_manifest(path, repository_root=root)
    before, _ = source_fingerprint(manifest.episodes[0], manifest)
    cache = manifest.episodes[0].project / ".hyperframes" / "checks.json"
    cache.parent.mkdir()
    cache.write_text("generated diagnostics")
    narration_cache = manifest.episodes[0].project / ".production-cache" / "cached.wav"
    narration_cache.parent.mkdir()
    narration_cache.write_bytes(b"cached synthesis; rendered audio is separately hashed")
    waveform_cache = manifest.episodes[0].project / ".waveform-cache" / "peaks.json"
    waveform_cache.parent.mkdir()
    waveform_cache.write_text('{"generated_peaks":[0,0.4,0]}')
    after, _ = source_fingerprint(manifest.episodes[0], manifest)
    assert before == after


def test_mixed_cli_is_registered_and_propagates_failed_batches(
    production: tuple[Path, Path, list[list[str]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, manifest, _ = production
    monkeypatch.setattr(
        "daily_video_factory.cli.run_production_batch", lambda *args, **kwargs: {"status": "failed"}
    )
    cli = CliRunner()
    assert cli.invoke(app, ["render-production-batch", "--help"]).exit_code == 0
    result = cli.invoke(app, ["render-production-batch", "--manifest", str(manifest), "--dry-run"])
    assert result.exit_code == 1
