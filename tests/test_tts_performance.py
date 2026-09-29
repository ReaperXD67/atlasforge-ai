from daily_video_factory.providers.tts import split_for_expressive_tts


def test_expressive_tts_split_preserves_paragraph_beats() -> None:
    beats = split_for_expressive_tts(
        "Would you know what to check first? This is the promise.\n\nHere is the proof."
    )

    assert beats == [
        ("Would you know what to check first? This is the promise.", True),
        ("Here is the proof.", True),
    ]
