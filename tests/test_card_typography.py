from daily_video_factory.providers.images import _wrap_text


def test_card_copy_keeps_hyphenated_words_together() -> None:
    wrapped = _wrap_text("Compare the trade-offs", width=20, max_lines=4)

    assert "trade-\noffs" not in wrapped
    assert wrapped == "Compare the\ntrade-offs"
