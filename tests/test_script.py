from daily_video_factory.script import _fit_segments_to_budget, _word_count


def test_script_segments_are_compacted_to_hard_word_budget() -> None:
    segments = [
        " ".join([f"hook{index}/detail{index}" for index in range(60)]),
        *[
            " ".join([f"section{section}word{index}" for index in range(70)])
            for section in range(5)
        ],
        " ".join([f"cta{index}" for index in range(45)]),
    ]

    fitted = _fit_segments_to_budget(segments, 240)

    assert sum(_word_count(segment) for segment in fitted) <= 240
    assert len(fitted) == len(segments)
    assert all(segment.endswith(".") for segment in fitted)


def test_script_compaction_does_not_append_a_sentence_fragment() -> None:
    first = "This complete sentence explains the decision clearly."
    second = "This trailing sentence contains several extra words that should never be chopped."

    fitted = _fit_segments_to_budget([f"{first} {second}", first], 16)

    assert fitted[0] == first
    assert "should never" not in fitted[0]


def test_script_compaction_does_not_treat_us_abbreviation_as_sentence_end() -> None:
    text = (
        "The registration flow is guided online. "
        "Verify your U.S. mobile number before continuing to the next step."
    )

    fitted = _fit_segments_to_budget([text, "Keep every detail accurate."], 15)

    assert fitted[0] == "The registration flow is guided online."
    assert not fitted[0].endswith("U.S.")
