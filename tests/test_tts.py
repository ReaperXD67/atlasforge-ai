from daily_video_factory.providers.tts import apply_pronunciations


def test_pronunciation_hints_are_speech_only_and_word_bounded() -> None:
    written = "Atomy USA explains Atomy, but not atomized products."

    spoken = apply_pronunciations(written, {"Atomy": "A-tomy"})

    assert spoken == "A-tomy USA explains A-tomy, but not atomized products."
    assert written == "Atomy USA explains Atomy, but not atomized products."
