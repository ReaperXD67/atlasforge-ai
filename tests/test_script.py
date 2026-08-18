from datetime import date

from daily_video_factory.models import ResearchReport
from daily_video_factory.providers.base import ProviderResult
from daily_video_factory.script import ScriptGenerator, _fit_segments_to_budget, _word_count


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


def test_script_prompt_includes_channel_content_goal(settings) -> None:
    generator = ScriptGenerator(settings)
    assert settings.channel.content_goal in generator._prompt(
        ResearchReport(
            query_date=date(2026, 8, 17),
            candidates=[],
            selected_title="How to join Atomy USA",
            selected_angle="A factual walkthrough",
            brand_focused=True,
        )
    )


def test_short_script_gets_one_focused_length_repair(settings) -> None:
    settings.script.target_minutes = 2
    settings.script.words_per_minute = 140
    settings.script.min_words = 224
    settings.script.max_words = 308

    def payload(prefix: str, hook_words: int, body_words: int, cta_words: int) -> dict:
        def words(label: str, count: int) -> str:
            return " ".join(f"{prefix}{label}{index}" for index in range(count))

        return {
            "title": "A careful Atomy registration walkthrough",
            "hook": words("hook", hook_words),
            "body": [words(f"body{section}", body_words) for section in range(5)],
            "cta": words("cta", cta_words),
            "facts_to_verify": [],
            "disclosures": ["AI voice; educational, not financial or medical advice"],
        }

    class FakeChain:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.payloads = [payload("short", 30, 35, 30), payload("repaired", 35, 38, 35)]

        def run(self, operation, invoke) -> ProviderResult[dict]:
            del invoke
            self.calls.append(operation)
            return ProviderResult(provider="fake", value=self.payloads[len(self.calls) - 1])

    generator = ScriptGenerator.__new__(ScriptGenerator)
    generator.settings = settings
    generator.chain = FakeChain()
    report = ResearchReport(
        query_date=date(2026, 8, 17),
        candidates=[],
        selected_title="How to join Atomy USA",
        selected_angle="A factual walkthrough",
        brand_focused=True,
    )

    document = generator.run(report)

    assert generator.chain.calls == ["script_generation", "script_length_repair"]
    assert document.word_count == 260
