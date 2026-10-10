"""Preparation contracts with fake local media tools: no optional models or synthesis."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_production_batch.py"


class _Samples:
    ndim = 1

    def __init__(self, count: int) -> None:
        self.count = count

    def __len__(self) -> int:
        return self.count


@pytest.fixture
def preparation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Load the real script with cheap media stubs; exercise its IO only in tmp_path."""
    root = tmp_path / "repo"
    source = root / "source-assets"
    (source / "sfx").mkdir(parents=True)
    (source / "sfx" / "chime.wav").write_bytes(b"owned sfx")
    (source / "bgm").mkdir()
    (source / "bgm" / "track.wav").write_bytes(b"owned music")
    generated: list[dict[str, Any]] = []
    transcribed: list[tuple[Path, str]] = []
    writes: list[tuple[Path, int, int]] = []
    commands: list[list[str]] = []
    numpy = ModuleType("numpy")
    numpy.float32 = "float32"
    numpy.isfinite = math.isfinite
    numpy.zeros = lambda count, **kwargs: _Samples(count)
    numpy.concatenate = lambda chunks: _Samples(sum(len(chunk) for chunk in chunks))
    soundfile = ModuleType("soundfile")

    def fake_write(path: Path, samples: _Samples, rate: int) -> None:
        writes.append((Path(path), len(samples), rate))
        Path(path).write_bytes(f"samples={len(samples)};rate={rate}".encode())

    soundfile.write = fake_write
    soundfile.read = lambda *args, **kwargs: (_Samples(240000), 24000)
    helper = ModuleType("prepare_local_shorts_batch")
    helper.ROOT = root
    helper.ASSET_SOURCE = source
    helper.local_whisper = lambda: object()

    def measured_words(source: str) -> list[dict[str, Any]]:
        tokens = source.split()
        return [
            {"text": token, "start": i * 0.6, "end": i * 0.6 + 0.45}
            for i, token in enumerate(tokens)
        ]

    def fake_transcribe(whisper: object, path: Path, text: str) -> list[dict[str, Any]]:
        transcribed.append((path, text))
        return measured_words(text)

    helper.transcribe_words = fake_transcribe
    kokoro = ModuleType("kokoro_onnx")

    class FakeKokoro:
        def __init__(self, *args: Any) -> None:
            pass

        def create(self, text: str, **kwargs: Any) -> tuple[_Samples, int]:
            generated.append({"text": text, **kwargs})
            return _Samples(240000), 24000

    kokoro.Kokoro = FakeKokoro
    for name, module in (
        ("numpy", numpy),
        ("soundfile", soundfile),
        ("prepare_local_shorts_batch", helper),
        ("kokoro_onnx", kokoro),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    loader = importlib.util.spec_from_file_location("production_preparation_under_test", _SCRIPT)
    assert loader is not None and loader.loader is not None
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    original_measured_words = module.measured_words
    monkeypatch.setattr(module, "measured_words", fake_transcribe)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command),
    )
    return SimpleNamespace(
        root=root,
        module=module,
        generated=generated,
        transcribed=transcribed,
        writes=writes,
        commands=commands,
        measured_words=measured_words,
        original_measured_words=original_measured_words,
    )


def _episode() -> dict[str, Any]:
    return {
        "id": "message-repair",
        "project": "videos/message-repair",
        "format": "shorts",
        "title": "Repair one unclear message",
        "audience_problem": "A vague service pitch is hard to understand",
        "packaging_promise": "Show one useful rewrite without promising replies",
        "thumbnail_headline": "CLEARER MESSAGE",
        "description": "An original educational example; replies are not guaranteed.",
        "hashtags": ["#Freelancing", "#Business", "#Shorts"],
        "sources": [{"claim": "The example is an original heuristic", "url": "https://www.sba.gov/", "checked_on": "2026-10-10"}],
        "segments": [
            {"id": "01-before", "title": "Before", "kind": "message", "text": "First vague example.", "display": ["Vague", "Example"], "beat_phrases": ["First", "example"]},
            {"id": "02-after", "title": "After", "kind": "message", "text": "Second clearer example.", "display": ["Clearer", "Example"], "beat_phrases": ["Second", "example"]},
        ],
    }


def _spec(preparation: SimpleNamespace) -> tuple[Path, dict[str, Any]]:
    spec = {"schema_version": 1, "batch_id": "test-repair", "voice": "af_heart", "speed": 1.0, "episodes": [_episode()]}
    project = preparation.root / "videos/message-repair"
    project.mkdir(parents=True)
    (project / "BRIEF.md").write_text("Initialized authorized project")
    (project / "hyperframes.json").write_text("{}")
    (project / "package.json").write_text('{"scripts":{"render":"npx hyperframes@0.8.127"}}')
    path = preparation.root / "creative.json"
    path.write_text(json.dumps(spec))
    return path, spec


def _invoke(preparation: SimpleNamespace, path: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> None:
    monkeypatch.setattr(sys, "argv", [str(_SCRIPT), "--creative", str(path), *extra])
    preparation.module.main()


@pytest.mark.parametrize(
    "source,transcript",
    [
        ("One small question.", "1 small question!"),
        ("A café's menu — mobile-friendly.", "A cafe's menu: mobile friendly."),
        ("Before: ask. After: show.", "BEFORE ASK AFTER SHOW"),
        ("Three steps, not three promises", "3 steps not 3 promises"),
        ("Tea at eighty rupees", "Tea at 80 rupees"),
        ("A hundred items", "A hundred items"),
        ("One hundred twenty", "120"),
    ],
)
def test_canonical_allows_only_formatting_or_single_digit_equivalence(
    preparation: SimpleNamespace, source: str, transcript: str,
) -> None:
    assert preparation.module.canonical(source) == preparation.module.canonical(transcript)


@pytest.mark.parametrize("transcript", ["A clearer message", "Not a clearer message", "A better message"])
def test_canonical_detects_omitted_added_and_replaced_words(
    preparation: SimpleNamespace, transcript: str,
) -> None:
    assert preparation.module.canonical("A much clearer message") != preparation.module.canonical(transcript)


def test_phrase_time_uses_the_first_measured_matching_token_not_uniform_spacing(
    preparation: SimpleNamespace,
) -> None:
    words = [
        {"text": "One", "start": 0.12, "end": 0.36},
        {"text": "small", "start": 0.57, "end": 0.81},
        {"text": "question.", "start": 1.91, "end": 2.8},
    ]
    assert preparation.module.phrase_time(words, "small question") == 0.57
    assert preparation.module.phrase_time(words, "1 small") == 0.12
    assert preparation.module.phrase_time(words, "question") == 1.91
    assert words[1]["start"] == 0.57


def test_phrase_time_refuses_an_unspoken_anchor(preparation: SimpleNamespace) -> None:
    with pytest.raises(ValueError, match="locate spoken beat"):
        preparation.module.phrase_time([{"text": "Hello", "start": 1.4, "end": 2.0}], "missing phrase")


@pytest.mark.parametrize("phrase", ["", "  ", "?!"])
def test_phrase_time_rejects_empty_canonical_anchors(preparation: SimpleNamespace, phrase: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        preparation.module.phrase_time([{"text": "Hello", "start": 1.4, "end": 2.0}], phrase)


def test_phrase_time_respects_word_boundaries_instead_of_matching_inside_a_word(
    preparation: SimpleNamespace,
) -> None:
    words = [{"text": "Offering", "start": 0.1, "end": 0.8}, {"text": "offer", "start": 1.8, "end": 2.1}]
    assert preparation.module.phrase_time(words, "offer") == 1.8
    with pytest.raises(ValueError, match="locate spoken beat"):
        preparation.module.phrase_time(words[:1], "offer")


@pytest.mark.parametrize(
    "words,source,message",
    [
        ([], "Hello", "coverage"),
        ([{"text": "Hello", "start": 0.0, "end": 0.5}], "Hello again", "coverage"),
        ([{"text": "Hello", "start": -0.1, "end": 0.5}], "Hello", "outside"),
        ([{"text": "Hello", "start": 0.2, "end": 0.2}], "Hello", "outside"),
        ([{"text": "Hello", "start": float("nan"), "end": 0.5}], "Hello", "outside"),
        ([{"text": "Hello", "start": 0.1, "end": float("inf")}], "Hello", "outside"),
        ([{"text": "Hello", "start": 9.9, "end": 10.1}], "Hello", "outside"),
        ([{"text": "Hello", "start": 0.0, "end": 1.0}, {"text": "again", "start": 0.8, "end": 1.2}], "Hello again", "overlap"),
    ],
)
def test_alignment_gate_rejects_missing_words_invalid_bounds_and_overlap(
    preparation: SimpleNamespace, words: list[dict[str, Any]], source: str, message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        preparation.module.validate_alignment(words, source, 10.0)


def test_alignment_gate_allows_only_small_estimated_boundary_tolerance(preparation: SimpleNamespace) -> None:
    words = [{"text": "Hello", "start": 0.0, "end": 1.0}, {"text": "again", "start": 0.99, "end": 10.04}]
    preparation.module.validate_alignment(words, "Hello again", 10.0)


def test_measured_word_bundles_preserve_real_interval_when_asr_token_has_zero_duration(
    preparation: SimpleNamespace,
) -> None:
    options: dict[str, Any] = {}

    class FakeWhisper:
        def transcribe(self, wav: str, **kwargs: Any) -> tuple[list[Any], None]:
            options.update(kwargs)
            return [SimpleNamespace(words=[
                SimpleNamespace(word=" I", start=0.0, end=0.0),
                SimpleNamespace(word=" made", start=0.23, end=0.78),
                SimpleNamespace(word=" it", start=0.78, end=0.78),
            ])], None

    words = preparation.original_measured_words(FakeWhisper(), Path("existing.wav"), "I made it")
    assert words == [{"text": "I made it", "start": 0.23, "end": 0.78}]
    assert options["word_timestamps"] is True
    assert options["initial_prompt"] == "I made it"
    assert options["condition_on_previous_text"] is False


def test_cached_rerun_reuses_voice_and_alignment_but_rebuilds_measured_planning(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, spec = _spec(preparation)
    _invoke(preparation, path, monkeypatch)
    assert len(preparation.generated) == 2
    assert len(preparation.transcribed) == 2
    first_request = preparation.generated[0]
    assert first_request["voice"] == "af_heart"
    assert first_request["speed"] == 1.0
    assert first_request["lang"] == "en-us"
    project = preparation.root / spec["episodes"][0]["project"]
    meta = json.loads((project / "audio_meta.json").read_text())
    assert meta["total_duration_s"] == 20.52
    assert meta["cues"][0]["beats"] == [0.0, 1.2]
    assert meta["cues"][1]["start"] == 10.1
    assert meta["voices"][0]["words"][3]["start"] == 10.1
    assert meta["voices"][0]["words"][5]["end"] == 11.75
    assert "estimated, not native timestamps" in meta["timing_source"]
    preparation.generated.clear()
    preparation.transcribed.clear()
    _invoke(preparation, path, monkeypatch)
    assert preparation.generated == []
    assert preparation.transcribed == []
    assert json.loads((project / "audio_meta.json").read_text())["cues"] == meta["cues"]


def test_changed_cached_waveform_refuses_stale_asr_alignment(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, spec = _spec(preparation)
    _invoke(preparation, path, monkeypatch)
    project = preparation.root / spec["episodes"][0]["project"]
    wav = next((project / ".production-cache").glob("*.wav"))
    wav.write_bytes(b"a different waveform")
    preparation.generated.clear()
    preparation.transcribed.clear()
    with pytest.raises(ValueError, match="changed after word alignment"):
        _invoke(preparation, path, monkeypatch)
    assert preparation.generated == []
    assert preparation.transcribed == []


@pytest.mark.parametrize("change", ["rate", "channels"])
def test_cached_narration_must_remain_mono_24_khz(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    path, _ = _spec(preparation)
    if change == "rate":
        monkeypatch.setattr(preparation.module.sf, "read", lambda *args, **kwargs: (_Samples(240000), 22050))
    else:
        monkeypatch.setattr(_Samples, "ndim", 2)
    with pytest.raises(ValueError, match="24 kHz mono"):
        _invoke(preparation, path, monkeypatch)
    assert preparation.transcribed == []


@pytest.mark.parametrize("change", ["text", "speed"])
def test_cache_key_changes_for_narration_text_or_speed(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    path, spec = _spec(preparation)
    _invoke(preparation, path, monkeypatch)
    preparation.generated.clear()
    preparation.transcribed.clear()
    if change == "text":
        spec["episodes"][0]["segments"][0]["text"] = "First useful example."
    else:
        spec["speed"] = 1.02
    path.write_text(json.dumps(spec))
    _invoke(preparation, path, monkeypatch)
    assert len(preparation.generated) == (1 if change == "text" else 2)
    assert len(preparation.transcribed) == len(preparation.generated)


def test_cached_alignment_omission_blocks_new_delivery(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, spec = _spec(preparation)
    _invoke(preparation, path, monkeypatch)
    project = preparation.root / spec["episodes"][0]["project"]
    alignment = next((project / ".production-cache").glob("*.json"))
    cached = json.loads(alignment.read_text())
    cached["words"] = cached["words"][:-1]
    alignment.write_text(json.dumps(cached))
    monkeypatch.setattr(
        preparation.module, "measured_words",
        lambda whisper, wav, text: preparation.measured_words(text)[:-1],
    )
    with pytest.raises(ValueError, match="ASR coverage"):
        _invoke(preparation, path, monkeypatch)


@pytest.mark.parametrize("project_path", ["../outside", "videos/../../outside"])
def test_preparation_rejects_paths_outside_video_workspace_before_voice_work(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, project_path: str,
) -> None:
    path, spec = _spec(preparation)
    spec["episodes"][0]["project"] = project_path
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        _invoke(preparation, path, monkeypatch)
    assert preparation.generated == []


@pytest.mark.parametrize("path_kind", ["absolute", "videos_root"])
def test_preparation_requires_a_relative_project_below_videos_not_a_broad_root(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, path_kind: str,
) -> None:
    path, spec = _spec(preparation)
    spec["episodes"][0]["project"] = (
        str(preparation.root / "videos/message-repair") if path_kind == "absolute" else "videos"
    )
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        _invoke(preparation, path, monkeypatch)
    assert preparation.generated == []


def test_unknown_episode_selector_is_not_a_silent_noop(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _ = _spec(preparation)
    with pytest.raises(ValueError, match="Unknown episode"):
        _invoke(preparation, path, monkeypatch, "--only", "does-not-exist")
    assert preparation.generated == []


def test_unknown_format_is_rejected_before_voice_work(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, spec = _spec(preparation)
    spec["episodes"][0]["format"] = "square"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="format"):
        _invoke(preparation, path, monkeypatch)
    assert preparation.generated == []


def test_normalized_duplicate_projects_are_rejected_before_media_work(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, spec = _spec(preparation)
    spec["episodes"].append({**spec["episodes"][0], "id": "different-id", "project": "./videos/message-repair"})
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="Duplicate project"):
        _invoke(preparation, path, monkeypatch)
    assert preparation.generated == []


def test_spoken_beat_phrases_must_follow_measured_order_not_get_silently_sorted(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, spec = _spec(preparation)
    spec["episodes"][0]["segments"][0]["beat_phrases"] = ["example", "First"]
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="out of order"):
        _invoke(preparation, path, monkeypatch)
    assert preparation.commands == []


@pytest.mark.parametrize("change", ["voice", "duplicate_id"])
def test_preparation_rejects_unapproved_voice_or_duplicate_ids_before_synthesis(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    path, spec = _spec(preparation)
    if change == "voice":
        spec["voice"] = "af_sky"
    else:
        spec["episodes"].append(dict(spec["episodes"][0]))
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        _invoke(preparation, path, monkeypatch)
    assert preparation.generated == []


def test_production_manifest_has_runner_identity_and_direct_voice_manifest(
    preparation: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, spec = _spec(preparation)
    _invoke(preparation, path, monkeypatch)
    manifest = json.loads(path.with_suffix(".production.json").read_text())
    assert manifest["batch_id"] == spec["batch_id"]
    assert manifest["episodes"][0]["voice_manifest"] == "audio_request.json"
    assert manifest["episodes"][0]["format"] == "shorts"
    assert manifest["episodes"][0]["min_seconds"] == 20
    assert manifest["episodes"][0]["max_seconds"] == 35


def test_longform_plans_supply_measured_chapters_and_frequent_retention_beats(
    preparation: SimpleNamespace,
) -> None:
    _, spec = _spec(preparation)
    episode = spec["episodes"][0]
    episode["format"] = "youtube"
    base = episode["segments"][0]
    episode["segments"] = [
        {**base, "id": f"{i + 1:02d}-scene", "title": f"Scene {i + 1}", "text": f"First useful example. Step {i + 1}."}
        for i in range(18)
    ]
    cues = [{**segment, "start": i * 18.0, "end": (i + 1) * 18.0, "beats": [0.0, 1.2]} for i, segment in enumerate(episode["segments"])]
    project = preparation.root / episode["project"]
    preparation.module.document_plans(project, spec, episode, {"cues": cues, "total_duration_s": 324.0})
    upload = (project / "UPLOAD_PACKAGE.md").read_text(encoding="utf-8")
    assert "00:00 Scene 1" in upload
    assert "00:54 Scene 4" in upload
    assert "04:48 Scene 17" in upload
    editorial = json.loads((project / "EDITORIAL.json").read_text())
    times = [beat["at_seconds"] for beat in editorial["retention_beats"]]
    assert times[0] == 0
    assert len(times) == 18
    assert max(b - a for a, b in zip(times, times[1:], strict=False)) <= 45
    assert 324.0 - times[-1] <= 45
    assert editorial["payoff"]["at_seconds"] == cues[1]["start"]
    assert "1920x1080" in (project / "BRIEF.md").read_text(encoding="utf-8")


def test_json_writer_preserves_unicode_in_reproducible_planning(preparation: SimpleNamespace) -> None:
    path = preparation.root / "nested" / "metadata.json"
    payload = {"copy": "Fictional café — not client work", "amount": "₹80"}
    preparation.module.write_json(path, payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    first = path.read_bytes()
    preparation.module.write_json(path, payload)
    assert path.read_bytes() == first
