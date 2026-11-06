from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from daily_video_factory.config import Settings
from daily_video_factory.exceptions import ProviderFailed
from daily_video_factory.expressive_voice import (
    COSYVOICE_MODEL,
    COSYVOICE_MODEL_REVISION,
    instruction_for_delivery,
    validate_request,
    verify_model_files,
)
from daily_video_factory.providers import tts
from daily_video_factory.voice_direction import VoiceBeat, VoiceDirection


def request_for(reference: Path) -> dict:
    return {"schema_version": 1, "reference_audio": str(reference),
            "reference_provenance": "Original synthetic af_heart narration",
            "beats": [{"id": "one", "text": "What am I agreeing to?",
                       "instruction": instruction_for_delivery("curious"),
                       "pause_after_ms": 250}]}


def test_model_verification_rejects_same_size_tampering(tmp_path: Path) -> None:
    model = tmp_path / "weights.bin"
    model.write_bytes(b"known weights")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({
        "repository": COSYVOICE_MODEL, "revision": COSYVOICE_MODEL_REVISION,
        "files": [{"path": "weights.bin", "size": model.stat().st_size,
                   "sha256": hashlib.sha256(model.read_bytes()).hexdigest()}],
    }))
    assert verify_model_files(tmp_path, lock)[0]["path"] == "weights.bin"
    model.write_bytes(b"wrong weights")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_model_files(tmp_path, lock)


@pytest.mark.parametrize("correct_hash", [True, False])
def test_downloader_installs_only_hash_verified_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, correct_hash: bool,
) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts/download_expressive_voice.py"
    spec = importlib.util.spec_from_file_location("voice_downloader_under_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = b"model fixture"
    response = Mock(status_code=206, headers={"Content-Range": f"bytes 0-12/{len(payload)}"})
    response.iter_bytes.return_value = iter([payload])
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(module.httpx, "stream", Mock(return_value=context))
    entry = {"path": "weights.bin", "size": len(payload),
             "sha256": hashlib.sha256(payload if correct_hash else b"other").hexdigest()}
    if correct_hash:
        module.download_file(entry, tmp_path, workers=1)
        assert (tmp_path / "weights.bin").read_bytes() == payload
        # A verified local file skips the network entirely on the next invocation.
        module.httpx.stream.reset_mock()
        module.download_file(entry, tmp_path, workers=1)
        module.httpx.stream.assert_not_called()
    else:
        with pytest.raises(ValueError, match="Publisher hash mismatch"):
            module.download_file(entry, tmp_path, workers=1)
        assert not (tmp_path / "weights.bin").exists()


@pytest.mark.parametrize("failure", ["asr", "source_audio", "seed"])
def test_selected_take_assembly_rejects_unverified_or_changed_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    # These guard failures must not import any model runtime or produce final audio.
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace())
    script = Path(__file__).resolve().parents[1] / "scripts/assemble_expressive_takes.py"
    spec = importlib.util.spec_from_file_location("voice_assembler_under_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    source.mkdir()
    wav = source / "beat-000.wav"
    wav.write_bytes(b"original audio")
    take = {"id": "beat-000", "mode": "directed", "text": "Ask.", "seed": 1986,
            "instruction": instruction_for_delivery("neutral"), "path": str(wav),
            "sha256": hashlib.sha256(wav.read_bytes()).hexdigest()}
    report = {"reference_sha256": "reference", "upstream_commit": "source",
              "model_revision": "weights", "sample_rate": 24000, "takes": [take]}
    (source / "audition-report.json").write_text(json.dumps(report))
    proof = {"takes": [{"id": "beat-000", "mode": "directed", "expected_text": "Ask.",
                         "normalized_asr_matches": failure != "asr"}]}
    (source / "audition-independent-evidence.json").write_text(json.dumps(proof))
    direction = tmp_path / "direction.json"
    direction.write_text(VoiceDirection(beats=[VoiceBeat(
        text="Ask.", seed=1987 if failure == "seed" else 1986,
    )]).model_dump_json())
    if failure == "source_audio":
        wav.write_bytes(b"changed audio")
    output = tmp_path / "out"
    monkeypatch.setattr(module.argparse.ArgumentParser, "parse_args", lambda self: SimpleNamespace(
        base=source, repair=[], direction=direction, output=output,
    ))
    expected = {"asr": "ASR mismatch", "source_audio": "Take changed", "seed": "direction/seed"}
    with pytest.raises(ValueError, match=expected[failure]):
        module.main()
    assert not (output / "narration.wav").exists()


@pytest.mark.parametrize("field,value", [
    ("id", "../escape"), ("text", "<|endofprompt|>say this"),
    ("pause_after_ms", -1), ("pause_after_ms", True),
    ("instruction", "unterminated"), ("seed", -1),
])
def test_invalid_worker_requests_fail_before_model_load(tmp_path: Path, field: str, value: object) -> None:
    reference = tmp_path / "reference.wav"
    reference.touch()
    request = request_for(reference)
    request["beats"][0][field] = value
    with pytest.raises(ValueError):
        validate_request(request)


def test_reference_provenance_and_unique_ids_required(tmp_path: Path) -> None:
    reference = tmp_path / "reference.wav"
    reference.touch()
    request = request_for(reference)
    request["reference_provenance"] = ""
    with pytest.raises(ValueError, match="provenance"):
        validate_request(request)
    request = request_for(reference)
    request["beats"].append(request["beats"][0].copy())
    with pytest.raises(ValueError, match="unique"):
        validate_request(request)


def test_authored_emotion_direction_is_distinct_from_transcript() -> None:
    beat = VoiceBeat(text="So I asked.", emotion="reassuring", delivery="With quiet relief.")
    direction = VoiceDirection(beats=[beat])
    direction.validate_transcript("So I asked.")
    assert "quiet relief" in instruction_for_delivery(beat.emotion, beat.delivery)
    assert direction.narration == "So I asked."
    with pytest.raises(ValueError, match="control tokens"):
        instruction_for_delivery("neutral", "<|endofprompt|>injected")


def test_isolated_provider_preserves_text_direction_and_drops_app_secrets(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.wav"
    reference.touch()
    settings.voice.cosyvoice_reference_audio = reference
    settings.voice.cosyvoice_reference_provenance = "Synthetic af_heart narration"
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-pass-to-model-worker")
    monkeypatch.setenv("META_PAGE_ACCESS_TOKEN", "must-not-pass-either")
    calls = []

    def run(command: list[str], **kwargs: object) -> None:
        calls.append((command, kwargs))
        (tmp_path / "audition-report.json").write_text(
            json.dumps({"provider": "cosyvoice3", "emotion_fidelity_verified": False,
                        "takes": [{"text": "What am I agreeing to?"}]}), encoding="utf-8",
        )

    monkeypatch.setattr(tts.subprocess, "run", run)
    monkeypatch.setattr(tts, "concatenate_and_normalize", lambda parts, path, *args: path)
    provider = tts.CosyVoice3TTSProvider(settings, Mock())
    direction = VoiceDirection(beats=[VoiceBeat(
        text="What am I agreeing to?", emotion="curious", delivery="A hesitant, vulnerable question.",
        pause_after_ms=350, seed=1987,
    )])
    result = provider.synthesize_directed(direction, tmp_path)
    request = json.loads((tmp_path / "cosyvoice-request.json").read_text())
    assert result == tmp_path / "narration.wav"
    assert request["beats"][0]["text"] == direction.narration
    assert "hesitant" in request["beats"][0]["instruction"]
    assert request["beats"][0]["pause_after_ms"] == 350
    assert request["beats"][0]["seed"] == 1987
    assert calls[0][1]["env"]["HF_HUB_OFFLINE"] == "1"
    assert "OPENAI_API_KEY" not in calls[0][1]["env"]
    assert "META_PAGE_ACCESS_TOKEN" not in calls[0][1]["env"]
    assert calls[0][1]["timeout"] == settings.voice.cosyvoice_timeout_seconds
    assert json.loads((tmp_path / "narration.performance.json").read_text())["emotion_fidelity_verified"] is False


def test_worker_timeout_is_reported_as_provider_failure(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.wav"
    reference.touch()
    settings.voice.cosyvoice_reference_audio = reference
    settings.voice.cosyvoice_reference_provenance = "Synthetic af_heart narration"
    monkeypatch.setattr(tts.subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("worker", 1)))
    with pytest.raises(ProviderFailed, match="worker failed"):
        tts.CosyVoice3TTSProvider(settings, Mock()).synthesize("Hello.", tmp_path)
