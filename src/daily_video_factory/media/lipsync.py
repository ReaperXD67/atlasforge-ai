from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..artifacts import atomic_write
from ..config import LipSyncConfig
from ..exceptions import ProviderFailed, ProviderUnavailable


class RhubarbLipSyncGenerator:
    """Generate deterministic 2D mouth cues from narration with the free Rhubarb CLI."""

    def __init__(self, config: LipSyncConfig) -> None:
        self.config = config

    def run(self, audio: Path, dialog: Path, output: Path) -> Path:
        executable = self.config.executable
        if not executable.is_file():
            raise ProviderUnavailable(
                "Rhubarb executable is unavailable. Install the official MIT-licensed "
                f"Windows release at {executable}."
            )
        if not audio.is_file():
            raise ProviderUnavailable(f"Lip-sync audio is unavailable: {audio}")
        if not dialog.is_file():
            raise ProviderUnavailable(f"Lip-sync dialog is unavailable: {dialog}")

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.stem}.rhubarb.tmp.json")
        temporary.unlink(missing_ok=True)
        command = [
            str(executable),
            "--recognizer",
            self.config.recognizer,
            "--dialogFile",
            str(dialog),
            "--exportFormat",
            "json",
            "--output",
            str(temporary),
        ]
        if self.config.extended_shapes:
            command.extend(["--extendedShapes", self.config.extended_shapes])
        command.append(str(audio))

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            temporary.unlink(missing_ok=True)
            raise ProviderFailed(
                f"Rhubarb exceeded the {self.config.timeout_seconds}s timeout."
            ) from exc
        if completed.returncode != 0 or not temporary.is_file():
            temporary.unlink(missing_ok=True)
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            raise ProviderFailed(f"Rhubarb lip-sync generation failed: {detail[-1000:]}")

        try:
            payload = json.loads(temporary.read_text(encoding="utf-8"))
            cues = payload.get("mouthCues")
            duration = float(payload.get("metadata", {}).get("duration", 0))
            if not isinstance(cues, list) or not cues or duration <= 0:
                raise ValueError("missing duration or mouth cues")
            allowed = set("ABCDEFGHX")
            previous_start = -1.0
            for cue in cues:
                start = float(cue["start"])
                end = float(cue["end"])
                value = str(cue["value"])
                if start < previous_start or end <= start or value not in allowed:
                    raise ValueError(f"invalid mouth cue: {cue}")
                previous_start = start
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            temporary.unlink(missing_ok=True)
            raise ProviderFailed(f"Rhubarb produced invalid lip-sync JSON: {exc}") from exc

        atomic_write(output, json.dumps(payload, indent=2, ensure_ascii=False))
        temporary.unlink(missing_ok=True)
        return output
