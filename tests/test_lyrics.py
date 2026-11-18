from pathlib import Path

import pytest

from daily_video_factory import lyrics
from daily_video_factory.config import Settings


def test_parse_chinese_section_and_singer_directions() -> None:
    lines = lyrics.parse_lyrics(
        "\ufeff【开场 · 俏皮男女互动】\\\n"
        "男：咩——咩！\\\n"
        "女: 什么好事要来啦？\n"
        "合：Bosston！Pragon！\n"
        "【主歌一 · 男声】\n"
        "红灯笼挂满大街小巷\n"
    )

    assert [line.section for line in lines] == ["开场", "开场", "开场", "主歌一"]
    assert [line.singer for line in lines] == ["male", "female", "ensemble", "male"]
    assert lines[0].text == "咩——咩！"
    assert lines[0].words == ["咩", "咩"]
    assert lines[2].words == ["Bosston", "Pragon"]


@pytest.mark.parametrize("post_chorus", ["Post-Chorus", "Post Chorus"])
def test_parse_song_sections_after_a_chorus(post_chorus: str) -> None:
    lines = lyrics.parse_lyrics(
        "[Chorus]\nBoston，Pragon，跟着我们一起冲\n"
        f"[{post_chorus}]\n嘿！一起走\n"
        "[Bridge]\n你一句，我一句\n"
        "[Final Chorus]\nBoston，Pragon，今天全场都跟我唱\n"
    )

    assert [line.section for line in lines] == [
        "Chorus", post_chorus, "Bridge", "Final Chorus"
    ]
    assert all(line.singer == "ensemble" for line in lines)
    assert lines[1].text == "嘿！一起走"
    assert lines[3].words[:2] == ["Boston", "Pragon"]


def test_song_section_parsing_preserves_vocal_and_stage_directions() -> None:
    lines = lyrics.parse_lyrics(
        "[Verse 1]\n[Female Vocal]\n向前一步\n"
        "[Build energy]\n现在出发\n"
        "[Bridge]\n你一句\n"
        "[Male Vocal]\n我一句\n"
    )

    assert [line.section for line in lines] == ["Verse 1", "Verse 1", "Bridge", "Bridge"]
    assert [line.singer for line in lines] == ["female", "female", "ensemble", "male"]
    assert [line.text for line in lines] == ["向前一步", "现在出发", "你一句", "我一句"]


def test_align_chinese_phrases_from_grouped_asr_timestamps(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(
        lyrics,
        "_transcribe_words",
        lambda *_: (
            [
                ("红灯笼", 1.0, 2.5, 0.9),
                ("挂满", 2.5, 3.5, 0.9),
                ("Bosston", 5.0, 5.5, 0.9),
                ("Pragon", 5.7, 6.2, 0.9),
            ],
            "zh",
        ),
    )

    report = lyrics.align_supplied_lyrics(
        Path("song.wav"),
        "【主歌一 · 男声】\n红灯笼，挂满！\nBosston！ Pragon！",
        settings,
        duration_seconds=7.0,
        language="zh",
    )

    assert report.analysis_backend == "faster_whisper_dtw"
    assert report.matched_word_count == report.supplied_word_count == 7
    assert report.anchor_coverage == 1.0
    line = report.lines[0]
    assert (line.start_seconds, line.end_seconds) == (1.0, 3.5)
    assert all(word.matched and word.estimated_timing for word in line.words)
    assert all(not word.estimated_timing for word in report.lines[1].words)
    assert "interpolated timing" in report.warnings[0]
    assert "".join(str(cue["text"]) for cue in lyrics.remotion_captions(report)) == (
        "红灯笼，挂满！ Bosston！ Pragon！"
    )
    assert lyrics.lrc_text(report).startswith("[00:01.00]红灯笼，挂满！")


def test_cjk_alignment_ignores_isolated_character_hits(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(
        lyrics,
        "_transcribe_words",
        lambda *_: ([("下雨好冷", 0.1, 0.8, 0.9)], "zh"),
    )

    report = lyrics.align_supplied_lyrics(
        Path("song.wav"),
        "好运\n发财\n喜洋洋",
        settings,
        duration_seconds=0.9,
        language="zh",
    )

    assert report.analysis_backend == "estimated"
    assert report.matched_word_count == 0
    for line in report.lines:
        assert 0 <= line.start_seconds < line.end_seconds <= 0.9
        assert all(
            word.estimated_timing and line.start_seconds <= word.start_seconds <= word.end_seconds
            <= line.end_seconds
            for word in line.words
        )


def test_latin_word_caps_keep_the_existing_remotion_spacing(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(
        lyrics,
        "_transcribe_words",
        lambda *_: (
            [("Cafe", 0.1, 0.5, 0.9), ("stay", 0.6, 0.9, 0.9), ("close.", 1.0, 1.4, 0.9)],
            "en",
        ),
    )

    report = lyrics.align_supplied_lyrics(
        Path("song.wav"),
        "[Verse 2]\nCafé, stay close.",
        settings,
        duration_seconds=2.0,
        language="en",
    )

    assert report.anchor_coverage == 1.0
    assert report.lines[0].singer == "female"
    assert [cue["text"] for cue in lyrics.remotion_captions(report)] == ["Café", " stay", " close"]


def test_split_latin_names_retain_first_syllable_onsets_and_conservative_confidence(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(
        lyrics,
        "_transcribe_words",
        lambda *_: (
            [
                (" B", 2.0, 2.1, 0.31),
                ("oston", 2.14, 2.6, 0.95),
                ("P", 2.8, 2.9, 0.92),
                ("rag", 2.94, 3.1, 0.44),
                ("on!", 3.14, 3.4, 0.88),
            ],
            "zh",
        ),
    )

    report = lyrics.align_supplied_lyrics(
        Path("song.wav"), "[Chorus]\nBoston！ Pragon！", settings,
        duration_seconds=4.0, language="zh",
    )

    assert report.anchor_coverage == 1.0
    first, second = report.lines[0].words
    assert (first.text, first.start_seconds, first.end_seconds) == ("Boston", 2.0, 2.6)
    assert (second.text, second.start_seconds, second.end_seconds) == ("Pragon", 2.8, 3.4)
    assert (first.confidence, second.confidence) == (0.31, 0.44)
    assert first.matched and second.matched
    assert not first.estimated_timing and not second.estimated_timing
    assert "fragments were joined" in report.warnings[0]


def test_complete_english_words_are_not_consumed_by_a_longer_supplied_word() -> None:
    observed = [("a", 0.0, 0.2, 0.9), ("way", 0.2, 0.5, 0.9),
                ("to", 0.6, 0.8, 0.9), ("get", 0.8, 1.0, 0.9), ("her", 1.0, 1.3, 0.9)]
    supplied = ["a", "way", "away", "to", "get", "her", "together"]

    assert lyrics._coalesce_latin_fragments(observed, supplied) == observed


@pytest.mark.parametrize("gap", [0.151, 1.0, -0.01])
def test_split_names_are_not_merged_across_large_gaps_or_overlaps(gap: float) -> None:
    observed = [("B", 0.1, 0.3, 0.9), ("oston", 0.3 + gap, 1.5, 0.9)]

    assert lyrics._coalesce_latin_fragments(observed, ["Boston"]) == observed


def test_fragment_joining_requires_an_exact_supplied_latin_word() -> None:
    unrelated_name = [("P", 0.1, 0.2, 0.9), ("ram", 0.2, 0.4, 0.9), ("on", 0.4, 0.7, 0.9)]
    mixed_script = [("B", 0.1, 0.2, 0.9), ("波", 0.2, 0.4, 0.9), ("oston", 0.4, 0.7, 0.9)]

    assert lyrics._coalesce_latin_fragments(unrelated_name, ["Pragon"]) == unrelated_name
    assert lyrics._coalesce_latin_fragments(mixed_script, ["Boston"]) == mixed_script


def test_fragment_joining_does_not_cross_sentence_punctuation() -> None:
    observed = [("B.", 0.1, 0.3, 0.9), ("oston", 0.3, 0.8, 0.9)]

    assert lyrics._coalesce_latin_fragments(observed, ["Boston"]) == observed
