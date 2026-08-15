from __future__ import annotations

import pytest

from daily_video_factory.exceptions import QualityGateFailed
from daily_video_factory.models import ScriptDocument
from daily_video_factory.quality import validate_script
from daily_video_factory.storyboard import StoryboardBuilder


def make_script(text: str, disclosures: list[str] | None = None) -> ScriptDocument:
    words = len(text.split())
    return ScriptDocument(
        title="How to Evaluate an Online Business Without the Hype",
        hook=text[:200],
        body=[text],
        cta="Share the criterion you find most useful and subscribe for more grounded breakdowns.",
        full_text=text,
        word_count=words,
        estimated_minutes=words / 145,
        facts_to_verify=[],
        disclosures=disclosures
        or ["AI-generated narration voice", "Educational, not financial advice"],
        provider="test",
    )


def test_storyboard_is_deterministic_and_varied(settings) -> None:
    first = " ".join(
        ["Start with the customer problem and test demand before spending money."] * 12
    )
    second = " ".join(["Compare time, margin, skill growth, and downside honestly."] * 12)
    third = " ".join(
        ["Atomy can then be evaluated as one optional case study among alternatives."] * 12
    )
    script = make_script(f"{first} {second} {third}")
    board = StoryboardBuilder(settings).run(script)
    assert len(board.scenes) >= 3
    assert board.scenes[0].camera_angle != board.scenes[1].camera_angle
    assert board.total_duration_seconds > 0


def test_quality_gate_rejects_earnings_promises(settings) -> None:
    safe_prefix = " ".join(["Evaluate the business model carefully before deciding."] * 20)
    unsafe = "You are guaranteed to earn $1000 per day."
    tail = " ".join(
        ["Atomy is one optional example and should be compared with alternatives."] * 20
    )
    with pytest.raises(QualityGateFailed):
        validate_script(make_script(f"{safe_prefix} {unsafe} {tail}"), settings)


def test_quality_gate_accepts_education_first_script(settings) -> None:
    prefix = " ".join(
        ["Evaluate demand, time, skills, costs, and risk before choosing a model."] * 18
    )
    suffix = " ".join(
        ["Atomy is one optional example to compare against retail and service alternatives."] * 14
    )
    assert validate_script(make_script(f"{prefix} {suffix}"), settings) == []


def test_quality_gate_allows_direct_brand_topic_when_grounded(settings) -> None:
    text = " ".join(
        ["Atomy registration should be evaluated carefully against official requirements."] * 24
    )
    script = make_script(text)
    script.brand_focused = True
    script.source_urls = [settings.research.official_sources[0].url]
    assert validate_script(script, settings) == []


def test_quality_gate_supports_brand_free_profiles(settings) -> None:
    settings.channel.brand_required = False
    settings.channel.brand_name = ""
    text = " ".join(["Explain the idea with examples, limitations, and practical tradeoffs."] * 30)
    assert validate_script(make_script(text), settings) == []
