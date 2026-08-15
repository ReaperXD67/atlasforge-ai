from __future__ import annotations

import wave
from pathlib import Path

from daily_video_factory.media.audio import generate_original_music, generate_sfx_track
from daily_video_factory.media.subtitles import write_subtitles
from daily_video_factory.models import Scene, ScriptDocument, Storyboard


def _script() -> ScriptDocument:
    text = (
        "A clear plan starts with a real customer problem. Compare options before choosing Atomy."
    )
    return ScriptDocument(
        title="A clear decision framework",
        hook=text,
        body=[text],
        cta="Share your approach.",
        full_text=text,
        word_count=len(text.split()),
        estimated_minutes=0.1,
        facts_to_verify=[],
        disclosures=["AI voice", "not financial advice"],
        provider="test",
    )


def _storyboard() -> Storyboard:
    scenes = [
        Scene(
            index=index,
            duration_seconds=2,
            narration="Example narration.",
            video_prompt="cinematic example",
            visual_search_query="business planning",
        )
        for index in range(1, 4)
    ]
    return Storyboard(title="Test", total_duration_seconds=6, scenes=scenes, provider="test")


def test_procedural_audio_has_expected_duration(tmp_path: Path) -> None:
    music = generate_original_music(2, tmp_path / "music.wav")
    sfx = generate_sfx_track(_storyboard(), 6, tmp_path / "sfx.wav")
    with wave.open(str(music), "rb") as source:
        assert source.getnframes() == 2 * source.getframerate()
    with wave.open(str(sfx), "rb") as source:
        assert source.getnframes() == 6 * source.getframerate()


def test_subtitle_outputs(settings, tmp_path: Path) -> None:
    cues = write_subtitles(
        _script(), 10, tmp_path / "captions.srt", tmp_path / "captions.ass", settings
    )
    assert cues[0].start_seconds == 0
    assert abs(cues[-1].end_seconds - 10) < 0.001
    assert "Dialogue:" in (tmp_path / "captions.ass").read_text(encoding="utf-8-sig")
