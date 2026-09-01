from pathlib import Path

from scripts.add_music_brand_lockups import _build_filter


def test_brand_lockup_filter_keeps_the_camera_locked() -> None:
    graph = _build_filter(
        width=1920,
        height=1080,
        fps=60,
        font_path=Path("assets/fonts/BarlowCondensed-Black.ttf"),
        opening_text="PRAGON",
        opening_duration=1.3,
        endcard_duration=3.6,
    )

    assert "text='PRAGON'" in graph
    assert "colorkey=0x000000" in graph
    assert "concat=n=2:v=1:a=0" in graph
    assert "zoompan" not in graph
    assert "xfade" not in graph
    assert "minterpolate" not in graph


def test_client_opening_logo_replaces_generated_wordmark() -> None:
    graph = _build_filter(
        width=1920,
        height=1080,
        fps=60,
        font_path=Path("assets/fonts/BarlowCondensed-Black.ttf"),
        opening_text="PRAGON",
        opening_duration=1.3,
        endcard_duration=3.6,
        opening_logo_input=1,
    )

    assert "[1:v]trim=duration=1.300" in graph
    assert "[2:v]trim=duration=3.600" in graph
    assert "pragonwhite" in graph
    assert "drawtext=" not in graph
    assert "trim=end_frame=216" in graph
    assert "eof_action=pass" in graph
    assert "zoompan" not in graph


def test_client_closing_poster_replaces_the_baked_outro_in_the_same_pass() -> None:
    graph = _build_filter(
        width=1920,
        height=1080,
        fps=60,
        font_path=Path("assets/fonts/BarlowCondensed-Black.ttf"),
        opening_text="PRAGON",
        opening_duration=1.3,
        endcard_duration=3.6,
        opening_logo_input=1,
        closing_poster_input=3,
        closing_poster_start=206.767,
        closing_poster_end=208.8,
    )

    assert "[3:v]trim=duration=2.033" in graph
    assert "setpts=PTS-STARTPTS" in graph
    assert "setpts=PTS+206.767/TB[closingposter]" in graph
    assert "fade=t=out:st=0.833:d=1.200" in graph
    assert "[baseplate][closingposter]overlay=x=0:y=0" in graph
    assert "[posterplate][pragonshadow]overlay" in graph
    assert "zoompan" not in graph
