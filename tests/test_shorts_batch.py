import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from daily_video_factory import shorts_batch
from daily_video_factory.shorts_batch import (
    ShortsBatchError,
    load_shorts_batch_manifest,
    run_shorts_batch,
    source_fingerprint,
)


@pytest.fixture
def batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, list[list[str]]]:
    root = tmp_path / "repo"
    wrapper = root / "scripts" / "render_hyperframes_windows.ps1"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("# render wrapper\n", encoding="utf-8")
    rows = []
    for episode_id in ("pv-is-not-money", "smaller-leg"):
        project = root / "videos" / episode_id
        assets = project / "assets"
        assets.mkdir(parents=True)
        (project / "index.html").write_text("<main>Short</main>\n", encoding="utf-8")
        (project / "package.json").write_text('{"render":"hyperframes@0.6.17"}', encoding="utf-8")
        (project / "hyperframes.json").write_text('{"width":1080,"height":1920}', encoding="utf-8")
        (assets / "voice.wav").write_bytes(b"authored audio")
        Image.new("RGB", (1080, 1920)).save(assets / "thumbnail.png")
        (project / "UPLOAD_PACKAGE.md").write_text(
            "## Title\nUseful Short\n\n## Description\nA clear explanation.\n\n"
            "## Hashtags\n#Atomy #Shorts #Truth\n",
            encoding="utf-8",
        )
        (project / "audio_request.json").write_text(
            '{"provider":"kokoro","voice":"af_heart"}',
            encoding="utf-8",
        )
        rows.append(
            {
                "id": episode_id,
                "project": f"videos/{episode_id}",
                "output": "renders/final.mp4",
                "thumbnail": "assets/thumbnail.png",
                "upload_package": "UPLOAD_PACKAGE.md",
                "voice_manifest": "audio_request.json",
            }
        )
    manifest = root / "batch.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "atomy-quick-truths",
                "expected_voice": "af_heart",
                "episodes": rows,
            }
        ),
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_command(command: list[str], *, cwd: Path) -> None:
        commands.append(command)
        if command[0] == "ffmpeg":
            output = Path(command[-1])
            content = f"mastered video {len(commands)}".encode()
        else:
            output = Path(command[command.index("-Output") + 1])
            content = f"fresh raw video {len(commands)}".encode()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)

    monkeypatch.setattr("daily_video_factory.shorts_batch._powershell", lambda: "powershell")
    monkeypatch.setattr("daily_video_factory.shorts_batch._run_command", fake_command)
    monkeypatch.setattr(
        "daily_video_factory.shorts_delivery._probe",
        lambda _: {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "pix_fmt": "yuv420p",
                    "width": 1080,
                    "height": 1920,
                    "avg_frame_rate": "30/1",
                },
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
            ],
            "format": {"duration": "27"},
        },
    )
    return root, manifest, commands


def _change_manifest(manifest: Path, **changes: Any) -> None:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload.update(changes)
    manifest.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize(
    "field,value",
    [
        ("project", "../outside"),
        ("output", "../../outside.mp4"),
        ("thumbnail", "..\\..\\outside.png"),
        ("voice_manifest", "C:\\outside.json"),
        ("upload_package", "/outside.md"),
    ],
)
def test_manifest_rejects_paths_outside_allowed_directories(
    batch: tuple[Path, Path, list[list[str]]],
    field: str,
    value: str,
) -> None:
    root, manifest, _ = batch
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["episodes"][0][field] = value
    _change_manifest(manifest, episodes=payload["episodes"])
    with pytest.raises(ShortsBatchError, match="relative|escapes"):
        load_shorts_batch_manifest(manifest, repository_root=root)


def test_manifest_rejects_duplicate_ids(batch: tuple[Path, Path, list[list[str]]]) -> None:
    root, manifest, _ = batch
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["episodes"][1]["id"] = payload["episodes"][0]["id"]
    _change_manifest(manifest, episodes=payload["episodes"])
    with pytest.raises(ShortsBatchError, match="duplicate episode id"):
        load_shorts_batch_manifest(manifest, repository_root=root)


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"schema_version": 2}, "schema_version"),
        ({"schema_version": True}, "schema_version"),
        ({"episodes": []}, "at least one"),
        ({"expected_voice": "af_sky"}, "af_heart"),
    ],
)
def test_manifest_rejects_invalid_schema_empty_batch_and_voice_changes(
    batch: tuple[Path, Path, list[list[str]]],
    changes: dict[str, Any],
    message: str,
) -> None:
    root, manifest, _ = batch
    _change_manifest(manifest, **changes)
    with pytest.raises(ShortsBatchError, match=message):
        load_shorts_batch_manifest(manifest, repository_root=root)


def test_batch_renders_masters_and_resumes_verified_unchanged_deliveries(
    batch: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest, commands = batch
    report = run_shorts_batch(manifest, repository_root=root)
    assert report["status"] == "verified"
    assert len(commands) == 4
    assert "-CheckFirst" in commands[0] and "-VerifyShorts" in commands[0]
    assert commands[0][commands[0].index("-Quality") + 1] == "delivery"
    assert commands[0][commands[0].index("-ExpectedVoice") + 1] == "af_heart"
    assert commands[1][commands[1].index("-af") + 1] == "loudnorm=I=-14:TP=-2:LRA=11"
    assert commands[1][commands[1].index("-c:v") + 1] == "copy"
    assert all(item["report"]["audio_channels"] == 2 for item in report["episodes"])
    assert (root / "BATCH_REPORT.json").is_file()
    commands.clear()
    resumed = run_shorts_batch(manifest, repository_root=root)
    assert resumed["status"] == "verified"
    assert all(item["resumed"] for item in resumed["episodes"])
    assert commands == []


@pytest.mark.parametrize(
    "relative_path,new_content",
    [
        ("index.html", b"<main>Changed narration timing</main>"),
        ("hyperframes.json", b'{"width":1080,"height":1920,"duration":26}'),
        ("assets/voice.wav", b"changed narration audio"),
        (
            "UPLOAD_PACKAGE.md",
            b"## Title\nChanged title\n\n## Description\nUpdated.\n#One #Two #Three",
        ),
    ],
)
def test_source_changes_invalidate_only_the_affected_resume_episode(
    batch: tuple[Path, Path, list[list[str]]],
    relative_path: str,
    new_content: bytes,
) -> None:
    root, manifest, commands = batch
    first = run_shorts_batch(manifest, repository_root=root)
    commands.clear()
    (root / "videos" / "pv-is-not-money" / relative_path).write_bytes(new_content)
    second = run_shorts_batch(manifest, repository_root=root)
    assert second["status"] == "verified"
    assert len(commands) == 2
    assert not second["episodes"][0]["resumed"]
    assert second["episodes"][1]["resumed"]
    assert first["episodes"][0]["source_fingerprint"] != second["episodes"][0]["source_fingerprint"]


@pytest.mark.parametrize("change", ["missing", "replaced"])
def test_resume_rejects_missing_or_changed_final_even_when_sources_match(
    batch: tuple[Path, Path, list[list[str]]],
    change: str,
) -> None:
    root, manifest, commands = batch
    run_shorts_batch(manifest, repository_root=root)
    final = root / "videos" / "pv-is-not-money" / "renders" / "final.mp4"
    if change == "missing":
        final.unlink()
    else:
        final.write_bytes(b"a different, stale delivery")
    commands.clear()
    second = run_shorts_batch(manifest, repository_root=root)
    assert second["status"] == "verified"
    assert len(commands) == 2
    assert not second["episodes"][0]["resumed"]
    assert second["episodes"][1]["resumed"]


def test_cache_and_render_outputs_do_not_change_source_fingerprint(
    batch: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest_path, _ = batch
    manifest = load_shorts_batch_manifest(manifest_path, repository_root=root)
    episode = manifest.episodes[0]
    before, _ = source_fingerprint(episode, manifest)
    for relative in (".hyperframes/cache.json", "snapshots/frame.png", "renders/final.mp4"):
        path = episode.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"generated artifact")
    (episode.project / ".env").write_text("not source material", encoding="utf-8")
    after, sources = source_fingerprint(episode, manifest)
    assert after == before
    assert "assets/voice.wav" in {item["path"] for item in sources}
    assert ".env" not in {item["path"] for item in sources}


def test_stale_raw_output_cannot_be_counted_as_success(
    batch: tuple[Path, Path, list[list[str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, manifest, commands = batch
    run_shorts_batch(manifest, repository_root=root)
    commands.clear()
    monkeypatch.setattr(
        "daily_video_factory.shorts_batch._run_command", lambda *args, **kwargs: None
    )
    report = run_shorts_batch(manifest, repository_root=root, resume=False)
    assert report["status"] == "failed"
    assert all(item["status"] == "failed" for item in report["episodes"])
    assert all("stale unmastered" in item["error"]["message"] for item in report["episodes"])


def test_failed_episode_does_not_prevent_other_episodes_from_completing(
    batch: tuple[Path, Path, list[list[str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, manifest, commands = batch
    original = shorts_batch._run_command

    def fail_first(command: list[str], *, cwd: Path) -> None:
        if "-Project" in command and "pv-is-not-money" in command[command.index("-Project") + 1]:
            raise subprocess.CalledProcessError(1, command)
        original(command, cwd=cwd)

    monkeypatch.setattr("daily_video_factory.shorts_batch._run_command", fail_first)
    report = run_shorts_batch(manifest, repository_root=root)
    assert report["status"] == "failed"
    assert [item["status"] for item in report["episodes"]] == ["failed", "verified"]
    assert len(commands) == 2
    saved = json.loads((root / "BATCH_REPORT.json").read_text(encoding="utf-8"))
    assert saved["episodes"][0]["error"]["type"] == "CalledProcessError"


def test_dry_run_previews_commands_without_encoding_or_overwriting_report(
    batch: tuple[Path, Path, list[list[str]]],
) -> None:
    root, manifest, commands = batch
    run_shorts_batch(manifest, repository_root=root)
    saved = (root / "BATCH_REPORT.json").read_bytes()
    commands.clear()
    plan = run_shorts_batch(manifest, repository_root=root, dry_run=True)
    assert plan["status"] == "dry_run"
    assert [item["status"] for item in plan["episodes"]] == ["planned", "planned"]
    assert all(item["render_command"] and item["master_command"] for item in plan["episodes"])
    assert commands == []
    assert (root / "BATCH_REPORT.json").read_bytes() == saved
