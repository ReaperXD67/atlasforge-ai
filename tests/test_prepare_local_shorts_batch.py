import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_local_shorts_batch.py"
_SPEC = importlib.util.spec_from_file_location("prepare_local_shorts_batch", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_PREPARE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PREPARE)


def test_caption_normalization_preserves_union_of_measured_token_intervals() -> None:
    words = [
        {"text": "U", "start": 1.0, "end": 1.1},
        {"text": ".S", "start": 1.1, "end": 1.3},
        {"text": ".A.", "start": 1.3, "end": 1.5},
        {"text": "10", "start": 2.0, "end": 2.4},
        {"text": ",000", "start": 2.4, "end": 2.8},
        {"text": "44", "start": 3.0, "end": 3.5},
        {"text": "%", "start": 3.5, "end": 3.9},
    ]
    assert _PREPARE.normalize_caption_words(words, "U S A ten thousand forty four percent") == [
        {"id": "w0", "text": "U.S.A.", "start": 1.0, "end": 1.5},
        {"id": "w1", "text": "10,000", "start": 2.0, "end": 2.8},
        {"id": "w2", "text": "44%", "start": 3.0, "end": 3.9},
    ]
    assert words[0]["text"] == "U"


def test_caption_correction_requires_the_matching_source_context() -> None:
    words = [
        {"text": "promises", "start": 19.76, "end": 20.26},
        {"text": "and", "start": 20.26, "end": 20.48},
        {"text": "comments.", "start": 20.48, "end": 20.94},
    ]
    corrected = _PREPARE.normalize_caption_words(words, "not random promises in comments")
    assert corrected[1] == {"id": "w1", "text": "in", "start": 20.26, "end": 20.48}
    unchanged = _PREPARE.normalize_caption_words(words, "promises and comments")
    assert unchanged[1]["text"] == "and"


def test_caption_hyphen_cleanup_handles_punctuated_source_words() -> None:
    words = [
        {"text": "-open,", "start": 1.0, "end": 1.4},
        {"text": "-guaranteed.", "start": 2.0, "end": 2.6},
    ]
    cleaned = _PREPARE.normalize_caption_words(words, "open, not guaranteed.")
    assert [word["text"] for word in cleaned] == ["open,", "guaranteed."]
    assert cleaned[1]["start"] == 2.0


@pytest.mark.parametrize("source,transcript,matches", [
    ("It is not a dollar balance.", "It is not a balance.", False),
    ("Remember: shared pool.", "shared pool.", False),
    ("U S A ten thousand P V and forty four percent", "U.S.A. 10,000 PV and 44%", True),
])
def test_caption_coverage_accepts_formatting_but_rejects_omitted_words(
    source: str, transcript: str, matches: bool,
) -> None:
    words = [{"text": word} for word in transcript.split()]
    assert _PREPARE.caption_coverage_matches(words, source) is matches


def test_bounded_retranscription_preserves_absolute_asr_word_times() -> None:
    observed = {}

    class FakeWhisper:
        def transcribe(self, path, **options):
            observed.update(path=path, options=options)
            return iter([SimpleNamespace(words=[
                SimpleNamespace(word=" dollar", start=11.167, end=11.307),
            ])]), None

    words = _PREPARE.transcribe_words(
        FakeWhisper(), Path("existing.wav"), "a dollar balance", clip=(10.547, 16.221),
    )
    assert words == [{"id": "w0", "text": "dollar", "start": 11.167, "end": 11.307}]
    assert observed["options"]["initial_prompt"] == "a dollar balance"
    assert observed["options"]["clip_timestamps"] == [10.547, 16.221]
