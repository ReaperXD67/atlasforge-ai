"""Small, dependency-free boundary for an isolated CosyVoice worker.

This module deliberately imports no model framework or credentials. Instructions
condition generation; they are never appended to the spoken transcript.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

COSYVOICE_COMMIT = "074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc"
COSYVOICE_MODEL = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
COSYVOICE_MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"
NEUTRAL_INSTRUCTION = "You are a helpful assistant.<|endofprompt|>"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_files(model_dir: Path, lock_path: Path) -> list[dict[str, str]]:
    """Verify every local model/config file against pinned publisher metadata."""
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("repository") != COSYVOICE_MODEL or lock.get("revision") != COSYVOICE_MODEL_REVISION:
        raise ValueError("Unexpected model lock revision")
    verified = []
    for entry in lock["files"]:
        path = (model_dir / entry["path"]).resolve()
        if not path.is_relative_to(model_dir.resolve()):
            raise ValueError("Model lock path escapes model directory")
        if not path.is_file() or path.stat().st_size != entry["size"]:
            raise ValueError(f"Missing or incomplete model file: {entry['path']}")
        if entry.get("sha256"):
            actual = sha256_file(path)
            expected = entry["sha256"]
        else:
            payload = path.read_bytes()
            actual = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
            expected = entry["git_blob_sha1"]
        if actual != expected:
            raise ValueError(f"Model file hash mismatch: {entry['path']}")
        verified.append({"path": entry["path"], "hash": actual})
    return verified


def validate_request(request: dict[str, Any]) -> None:
    if request.get("schema_version") != 1:
        raise ValueError("Unsupported expressive voice request version")
    reference = Path(request.get("reference_audio", ""))
    if not reference.is_file():
        raise ValueError("Reference audio must be a local, authorized file")
    if not str(request.get("reference_provenance", "")).strip():
        raise ValueError("Reference audio provenance is required")
    beats = request.get("beats")
    if not isinstance(beats, list) or not 1 <= len(beats) <= 100:
        raise ValueError("Expected 1 to 100 performance beats")
    ids: set[str] = set()
    for beat in beats:
        identifier = beat.get("id", "")
        if not identifier or not all(c.isalnum() or c in "-_" for c in identifier):
            raise ValueError("Beat IDs must be safe file basenames")
        if identifier in ids:
            raise ValueError("Beat IDs must be unique")
        ids.add(identifier)
        text = beat.get("text", "")
        if not isinstance(text, str) or not text.strip() or len(text) > 600:
            raise ValueError("Each beat must contain 1 to 600 spoken characters")
        if "<|" in text or "|>" in text:
            raise ValueError("Control tokens belong in instructions, not the transcript")
        instruction = beat.get("instruction", NEUTRAL_INSTRUCTION)
        if not isinstance(instruction, str) or not instruction.endswith("<|endofprompt|>"):
            raise ValueError("CosyVoice instructions must end with <|endofprompt|>")
        if len(instruction) > 1000:
            raise ValueError("Instruction is too long")
        pause = beat.get("pause_after_ms", 0)
        if not isinstance(pause, int) or isinstance(pause, bool) or not 0 <= pause <= 1500:
            raise ValueError("Pause must be an integer between 0 and 1500 ms")
        seed = beat.get("seed", 1986)
        if not isinstance(seed, int) or not 0 <= seed < 2**32:
            raise ValueError("Seed must be an unsigned 32-bit integer")


def instruction_for_delivery(emotion: str, delivery: str = "") -> str:
    """Use explicit supported controls, allowing an authored semantic direction.

    Free-form directions are experimental and need listening review. Unlike DSP
    tempo or pitch effects, this text enters the model's instruction conditioning.
    """
    if delivery.strip():
        content = delivery.strip()
        if "<|" in content or "|>" in content:
            raise ValueError("Delivery must not contain model control tokens")
    else:
        content = {
            "neutral": "",
            "curious": "Speak with gentle curiosity and a questioning tone.",
            "serious": "Speak seriously and thoughtfully, with restrained emotion.",
            "reassuring": "Please say a sentence in a very soft voice.",
            "excited": "请非常开心地说一句话。",
        }[emotion]
    return f"You are a helpful assistant. {content}<|endofprompt|>" if content else NEUTRAL_INSTRUCTION
