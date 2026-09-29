from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from daily_video_factory.config import LipSyncConfig
from daily_video_factory.exceptions import ProviderFailed, ProviderUnavailable
from daily_video_factory.media.lipsync import RhubarbLipSyncGenerator


def test_rhubarb_lipsync_builds_expected_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "rhubarb.exe"
    executable.write_bytes(b"stub")
    audio = tmp_path / "narration.wav"
    audio.write_bytes(b"RIFF")
    dialog = tmp_path / "narration.txt"
    dialog.write_text("Two legs, one smaller side.", encoding="utf-8")
    output = tmp_path / "lip_sync.json"
    observed: list[str] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        observed.extend(command)
        temporary = Path(command[command.index("--output") + 1])
        temporary.write_text(
            json.dumps(
                {
                    "metadata": {"duration": 1.2},
                    "mouthCues": [
                        {"start": 0.0, "end": 0.2, "value": "X"},
                        {"start": 0.2, "end": 1.2, "value": "A"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("daily_video_factory.media.lipsync.subprocess.run", fake_run)
    result = RhubarbLipSyncGenerator(
        LipSyncConfig(enabled=True, executable=executable)
    ).run(audio, dialog, output)

    assert result == output
    assert "--recognizer" in observed
    assert "pocketSphinx" in observed
    assert "--extendedShapes" in observed
    assert json.loads(output.read_text(encoding="utf-8"))["mouthCues"][1]["value"] == "A"


def test_rhubarb_lipsync_requires_executable(tmp_path: Path) -> None:
    generator = RhubarbLipSyncGenerator(
        LipSyncConfig(enabled=True, executable=tmp_path / "missing.exe")
    )

    with pytest.raises(ProviderUnavailable, match="Rhubarb executable"):
        generator.run(tmp_path / "voice.wav", tmp_path / "dialog.txt", tmp_path / "out.json")


def test_rhubarb_lipsync_rejects_invalid_cues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "rhubarb.exe"
    executable.write_bytes(b"stub")
    audio = tmp_path / "narration.wav"
    audio.write_bytes(b"RIFF")
    dialog = tmp_path / "narration.txt"
    dialog.write_text("Hello", encoding="utf-8")

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        Path(command[command.index("--output") + 1]).write_text(
            json.dumps(
                {
                    "metadata": {"duration": 1.0},
                    "mouthCues": [{"start": 0.8, "end": 0.2, "value": "?"}],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("daily_video_factory.media.lipsync.subprocess.run", fake_run)

    with pytest.raises(ProviderFailed, match="invalid lip-sync JSON"):
        RhubarbLipSyncGenerator(
            LipSyncConfig(enabled=True, executable=executable)
        ).run(audio, dialog, tmp_path / "out.json")
