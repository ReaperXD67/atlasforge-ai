from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from pydantic import ValidationError

from daily_video_factory.config import Settings
from daily_video_factory.exceptions import ProviderFailed
from daily_video_factory.providers import tts
from daily_video_factory.providers.base import ProviderChain
from daily_video_factory.voice_direction import VoiceBeat, VoiceDirection, directed_speech_chunks


def test_long_sentence_is_bounded_without_dropping_words() -> None:
    text = " ".join(f"word{index}" for index in range(200)) + ". lowercase sentence follows."
    chunks = tts.split_for_tts(text, max_chars=80)
    assert all(len(chunk) <= 80 for chunk in chunks)
    assert " ".join(chunks) == text
    expressive = tts.split_for_expressive_tts(text + "\n\nAnother paragraph.", max_chars=80)
    assert sum(paragraph_end for _, paragraph_end in expressive) == 2
    assert " ".join(beat for beat, _ in expressive) == text + " Another paragraph."


def test_oversized_token_fails_without_silent_truncation() -> None:
    with pytest.raises(ValueError, match="token exceeds"):
        tts.split_for_tts("x" * 100, max_chars=80)


def test_direction_preserves_transcript_and_rejects_invalid_controls() -> None:
    plan = VoiceDirection(beats=[VoiceBeat(text="Check first.", emotion="curious")])
    plan.validate_transcript(" Check\n first. ")
    with pytest.raises(ValueError, match="exact approved"):
        plan.validate_transcript("Check first!")
    with pytest.raises(ValidationError):
        VoiceBeat(text="  ")
    with pytest.raises(ValidationError):
        VoiceBeat(text="Hello", emotion="fake-emotion")
    with pytest.raises(ValidationError):
        VoiceBeat(text="Hello", pace=2.0)


def test_provider_chunking_preserves_directed_pause_after_complete_beat() -> None:
    plan = VoiceDirection(
        beats=[
            VoiceBeat(text=" ".join(["word"] * 90), emotion="serious", pause_after_ms=430),
        ]
    )
    chunks = directed_speech_chunks(plan, max_chars=280)
    assert len(chunks) == 2
    assert all(len(beat.text) <= 280 for beat in chunks)
    assert all(beat.emotion == "serious" for beat in chunks)
    assert [beat.pause_after_ms for beat in chunks] == [0, 430]
    assert " ".join(beat.text for beat in chunks) == plan.narration


def test_openai_direction_goes_to_instruction_not_spoken_text(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[dict] = []
    pauses: list[int] = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def post(url: str, **kwargs: object) -> SimpleNamespace:
        requests.append(kwargs["json"])
        return SimpleNamespace(status_code=200, content=b"wav")

    def normalize(parts: list[Path], output: Path, *args: object, **kwargs: object) -> Path:
        pauses.extend(kwargs["pauses_ms"])
        output.write_bytes(b"normalized")
        return output

    monkeypatch.setattr(tts.httpx, "post", post)
    monkeypatch.setattr(tts, "concatenate_and_normalize", normalize)
    plan = VoiceDirection(
        beats=[
            VoiceBeat(text="Look closer.", emotion="curious", pause_after_ms=400),
            VoiceBeat(text="Read the label.", emotion="serious", energy=0.3),
        ]
    )
    provider = tts.OpenAITTSProvider(settings, Mock())
    provider.synthesize_directed(plan, tmp_path)
    assert [item["input"] for item in requests] == ["Look closer.", "Read the label."]
    assert "curious" in requests[0]["instructions"]
    assert "serious" in requests[1]["instructions"]
    assert pauses == [400, 0]


def test_chatterbox_directions_control_each_beat_and_pause(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waveform = np.ones(240, dtype=np.float32) * 0.1
    tensor = Mock()
    tensor.squeeze.return_value.detach.return_value.cpu.return_value.numpy.return_value = waveform
    model = Mock(sr=24000)
    model.generate.return_value = tensor
    factory = Mock()
    factory.from_pretrained.return_value = model
    written: list[np.ndarray] = []
    monkeypatch.setitem(sys.modules, "chatterbox", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "chatterbox.tts", SimpleNamespace(ChatterboxTTS=factory))
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    )
    monkeypatch.setitem(
        sys.modules, "soundfile", SimpleNamespace(write=lambda path, data, sr: written.append(data))
    )
    monkeypatch.setattr(tts, "concatenate_and_normalize", lambda parts, output, *args: output)
    plan = VoiceDirection(
        beats=[
            VoiceBeat(text="A surprise.", emotion="excited", energy=0.9, pause_after_ms=500),
            VoiceBeat(text="Check the source.", emotion="serious", energy=0.2),
        ]
    )
    ffmpeg = Mock()
    ffmpeg.duration.return_value = 0.52
    provider = tts.ChatterboxTTSProvider(settings, ffmpeg)
    provider.synthesize_directed(plan, tmp_path)
    assert factory.from_pretrained.call_count == 1
    assert model.generate.call_count == 2
    assert (
        model.generate.call_args_list[0].kwargs["exaggeration"]
        > model.generate.call_args_list[1].kwargs["exaggeration"]
    )
    assert written[0].size == 240 + 12000 + 240
    ffmpeg.run.assert_not_called()  # No global WPM fitting destroys directed pauses.


def test_kokoro_direction_keeps_voice_and_applies_only_pace_and_pauses(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str, float]] = []
    written: list[np.ndarray] = []

    def pipeline(text: str, *, voice: str, speed: float) -> list[tuple]:
        calls.append((text, voice, speed))
        return [(text, "phonemes", np.ones(240, dtype=np.float32))]

    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KPipeline=lambda **kwargs: pipeline))
    monkeypatch.setitem(
        sys.modules, "soundfile", SimpleNamespace(write=lambda path, data, sr: written.append(data))
    )
    monkeypatch.setattr(tts, "concatenate_and_normalize", lambda parts, output, *args: output)
    settings.voice.kokoro_voice = "af_heart"
    settings.voice.kokoro_speed = 0.97
    plan = VoiceDirection(
        beats=[
            VoiceBeat(
                text="First beat.", emotion="excited", energy=1, pace=0.9, pause_after_ms=400
            ),
            VoiceBeat(text="Second beat.", emotion="serious", pace=1.1, pause_after_ms=500),
        ]
    )
    provider = tts.KokoroTTSProvider(settings, Mock())
    provider.synthesize_directed(plan, tmp_path)
    assert calls == [
        ("First beat.", "af_heart", 0.97 * 0.9),
        ("Second beat.", "af_heart", 0.97 * 1.1),
    ]
    assert written[0].size == 240 + 9600 + 240
    assert np.count_nonzero(written[0][240:9840]) == 0
    performance = json.loads((tmp_path / "narration.performance.json").read_text())
    assert performance["semantic_emotion_supported"] is False
    assert performance["ignored_controls"] == ["emotion", "energy"]
    assert performance["beats"][-1]["appended_pause_samples"] == 0
    assert provider.direction_mode == "pace_and_pauses_only"


def test_fallback_report_does_not_claim_emotion_and_removes_failed_timing(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Failed(tts.TTSProvider):
        name = "first"

        def available(self) -> bool:
            return True

        def synthesize(self, text: str, output_dir: Path) -> Path:
            (output_dir / "narration.words.json").write_text('[{"text":"WRONG"}]')
            raise ProviderFailed("Transport failed")

    class Fallback(tts.TTSProvider):
        name = "second"

        def available(self) -> bool:
            return True

        def synthesize(self, text: str, output_dir: Path) -> Path:
            assert not (output_dir / "narration.words.json").exists()
            result = output_dir / "narration.wav"
            result.write_bytes(b"audio")
            return result

    settings.voice.providers = ["first", "second"]
    ffmpeg = Mock()
    ffmpeg.duration.return_value = 2.0
    narrator = tts.NarrationGenerator(settings, ffmpeg)
    narrator.chain = ProviderChain([Failed(), Fallback()])
    align = Mock()
    monkeypatch.setattr(tts, "write_forced_aligned_caption_sidecars", align)
    plan = VoiceDirection(beats=[VoiceBeat(text="Look closer.", emotion="curious")])
    result = narrator.run(plan.narration, tmp_path, direction=plan)
    report = json.loads((tmp_path / "narration.direction-report.json").read_text())
    assert result.provider == "second"
    assert report["fallback_used"] is True
    assert report["direction_requested"] is True
    assert report["direction_applied"] is False
    assert report["emotion_fidelity_verified"] is False
    assert report["semantic_emotion_supported"] is False
    assert report["attempts"] == [
        {"provider": "first", "status": "failed"},
        {"provider": "second", "status": "succeeded"},
    ]
    align.assert_called_once()
