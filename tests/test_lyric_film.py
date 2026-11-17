from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_video_factory.lyric_cues import Cue
from daily_video_factory.lyric_film import Edit, subtitle_script


def test_default_lyric_film_preserves_cinematic_cue_motion() -> None:
    edit = Edit(shots=[{"at": 0, "image": "frame.jpg"}], accent_sections=["Chorus"])
    cue = Cue(text="两年七个月", start=2.0, end=3.0, section="Chorus")
    script = subtitle_script(edit, [cue])

    assert "Kinetic" not in script
    assert (
        r"Dialogue: 0,0:00:02.00,0:00:03.00,Refrain,,0,0,0,,"
        r"{\move(960,902,960,892,0,210)\fad(210,210)\blur0.65}两年七个月"
    ) in script


def test_kinetic_treatment_uses_original_cue_times_and_literal_highlights() -> None:
    font = Path(__file__).resolve().parents[1] / "assets/fonts/BarlowCondensed-Black.ttf"
    edit = Edit(
        shots=[{"at": 0, "image": "frame.jpg"}],
        lyric_style="kinetic",
        font_family="Barlow Condensed Black",
        accent_sections=["Final Chorus"],
        highlight_phrases=["D’Blue", "D’Blue Family Wellness"],
    )
    cues = [
        Cue(text="A nonmatching D’Bluebell {string}", start=0.0, end=2.0),
        Cue(
            text="D’BLUE FAMILY WELLNESS, LET THE GOOD VIBES FLOW!",
            start=2.25,
            end=3.87,
            section="Final Chorus",
        ),
    ]
    script = subtitle_script(edit, cues, font)

    verse, chorus = [line for line in script.splitlines() if line.startswith("Dialogue")]
    assert "0:00:00.00,0:00:02.00,KineticLyric" in verse
    assert "D’Bluebell ｛string｝" in verse
    assert r"\1c" not in verse
    assert "0:00:02.25,0:00:03.87,KineticRefrain" in chorus
    assert r"\t(0,125,0.55,\fscx107\fscy107)" in chorus
    assert r"{\1c&HFFEB95&}D’BLUE FAMILY WELLNESS{\1c&HA4E0FF&}," in chorus
    assert r"\fs73" in chorus or r"\fs72" in chorus


def test_kinetic_treatment_rejects_invalid_color() -> None:
    with pytest.raises(ValidationError, match="accent_color"):
        Edit(shots=[{"at": 0, "image": "frame.jpg"}], accent_color="royal-blue")
