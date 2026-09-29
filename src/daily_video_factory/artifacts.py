from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def slugify(value: str, max_length: int = 64) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (value or "untitled")[:max_length].rstrip("-")


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    encoding = None if isinstance(data, bytes) else "utf-8"
    with tempfile.NamedTemporaryFile(
        mode=mode, encoding=encoding, delete=False, dir=path.parent
    ) as tmp:
        tmp.write(data)
        temp_path = Path(tmp.name)
    os.replace(temp_path, path)


@dataclass(frozen=True)
class RunPaths:
    root: Path
    scripts: Path
    audio: Path
    storyboards: Path
    scenes: Path
    videos: Path
    music: Path
    sfx: Path
    subtitles: Path
    thumbnails: Path
    final: Path
    logs: Path
    research: Path
    metadata: Path

    @classmethod
    def create(cls, output_root: Path, publication_date: date, topic: str) -> RunPaths:
        root = output_root / f"{publication_date.isoformat()}-{slugify(topic)}"
        names = [
            "scripts",
            "audio",
            "storyboards",
            "scenes",
            "videos",
            "music",
            "sfx",
            "subtitles",
            "thumbnails",
            "final",
            "logs",
            "research",
            "metadata",
        ]
        paths = {name: root / name for name in names}
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        return cls(root=root, **paths)

    @classmethod
    def from_root(cls, root: Path) -> RunPaths:
        names = [
            "scripts",
            "audio",
            "storyboards",
            "scenes",
            "videos",
            "music",
            "sfx",
            "subtitles",
            "thumbnails",
            "final",
            "logs",
            "research",
            "metadata",
        ]
        paths = {name: root / name for name in names}
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        return cls(root=root, **paths)

    def write_json(
        self, relative: str | Path, value: BaseModel | dict[str, Any] | list[Any]
    ) -> Path:
        path = self.root / relative
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return path

    def write_text(self, relative: str | Path, value: str) -> Path:
        path = self.root / relative
        atomic_write(path, value)
        return path
