import json
from pathlib import Path

from daily_video_factory.media.subtitles import (
    rebuild_exact_caption_sidecars,
    scale_exact_caption_sidecars,
    write_exact_caption_sidecars,
)
from daily_video_factory.providers.tts import EdgeTTSProvider, apply_pronunciations


def test_pronunciation_hints_are_speech_only_and_word_bounded() -> None:
    written = "Atomy USA explains Atomy, but not atomized products."

    spoken = apply_pronunciations(written, {"Atomy": "A-tomy"})

    assert spoken == "A-tomy USA explains A-tomy, but not atomized products."
    assert written == "Atomy USA explains Atomy, but not atomized products."


def test_edge_prosody_variation_preserves_signed_values() -> None:
    assert EdgeTTSProvider._adjust_signed("+4%", -2, "%") == "+2%"
    assert EdgeTTSProvider._adjust_signed("-1%", 3, "%") == "+2%"
    assert EdgeTTSProvider._adjust_signed("+0Hz", -1, "Hz") == "-1Hz"


def test_exact_caption_sidecars_keep_authored_text_and_real_timing(tmp_path: Path) -> None:
    text = "Nexa explains it clearly. Then the proof appears."
    timed = [
        ("Nexa", 0.2, 0.5),
        ("explains", 0.55, 0.95),
        ("it", 1.0, 1.1),
        ("clearly", 1.15, 1.6),
        ("Then", 1.9, 2.2),
        ("the", 2.25, 2.35),
        ("proof", 2.4, 2.8),
        ("appears", 2.85, 3.3),
    ]
    cues = write_exact_caption_sidecars(
        text,
        timed,
        tmp_path,
        max_words=4,
        minimum_seconds=0.5,
    )
    assert " ".join(cue.text for cue in cues) == text
    assert cues[0].start_seconds == 0.2
    assert cues[-1].end_seconds == 3.3
    words = json.loads((tmp_path / "narration.words.json").read_text(encoding="utf-8"))
    assert words[0] == {"text": "Nexa", "start": 0.2, "end": 0.5}
    verification = json.loads(
        (tmp_path / "narration.caption-verification.json").read_text(encoding="utf-8")
    )
    assert verification["exact_authored_text"] is True
    assert verification["monotonic_word_timings"] is True
    assert verification["maximum_words_per_cue"] == 4

    scale_exact_caption_sidecars(tmp_path, 2)
    scaled = json.loads((tmp_path / "narration.words.json").read_text(encoding="utf-8"))
    assert scaled[0]["start"] == 0.4
    assert scaled[-1]["end"] == 6.6
    scaled_verification = json.loads(
        (tmp_path / "narration.caption-verification.json").read_text(encoding="utf-8")
    )
    assert scaled_verification["last_word_end"] == 6.6

    rebuilt = rebuild_exact_caption_sidecars(
        text,
        tmp_path,
        max_words=3,
        minimum_seconds=0.5,
    )
    assert " ".join(cue.text for cue in rebuilt) == text
    assert max(len(cue.text.split()) for cue in rebuilt) <= 3
