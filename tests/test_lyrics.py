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
