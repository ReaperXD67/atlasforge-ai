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
