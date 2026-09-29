from datetime import date

from daily_video_factory.models import ResearchReport
from daily_video_factory.providers.base import ProviderResult
from daily_video_factory.script import (
    ScriptGenerator,
    _enforce_engagement_structure,
    _engagement_issues,
    _fit_segments_to_budget,
    _reclaim_body_budget,
    _word_count,
)


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


def test_script_prompt_requires_an_earned_retention_open(settings) -> None:
    prompt = ScriptGenerator(settings)._prompt(
        ResearchReport(
            query_date=date(2026, 8, 18),
            selected_title="How to join Atomy USA",
            selected_angle="A practical walkthrough",
            candidates=[],
            evidence=[],
            brand_focused=True,
        )
    )
    assert "No greeting" in prompt
    assert "first 75 spoken words" in prompt
    assert "Resolve the opening loop" in prompt


def test_engagement_gate_rejects_generic_brochure_copy() -> None:
    payload = {
        "hook": (
            "Considering Atomy USA? You might be wondering which membership is right, "
            "and the registration process has two paths with different requirements."
        ),
        "body": [
            "Atomy has two membership paths and each one has a different purpose.",
            "The first decision involves the type of account you want to create.",
            "The second decision involves selecting a sponsor during registration.",
            "Finally, applicants review the agreement and confirm their information.",
            "The registration flow also includes mobile verification and personal details.",
        ],
    }

    issues = _engagement_issues(payload)

    assert "the cold open uses a generic YouTube opener" in issues
    assert "the first 75 words do not make a concrete viewer promise" in issues
    assert any("too few teaching sections" in issue for issue in issues)


def test_engagement_gate_accepts_specific_retention_structure() -> None:
    payload = {
        "hook": (
            "Choose the wrong Atomy account first, and fixing it later can add friction. "
            "Three checks separate a simple product account from a business decision."
        ),
        "body": [
            "By the end, you'll know which path fits your goal and what to verify before submitting.",
            "What are you actually joining for? Start with the outcome, not the application form.",
            "But the account type is only the first trade-off. Your sponsor choice also matters.",
            "Here's the part people miss: read the member agreement before entering tax details.",
            "If any answer is unclear, stop and ask for a guided walkthrough before confirming.",
        ],
        "cta": "Ask for a guided walkthrough if you want help checking the path before registering.",
    }

    assert _engagement_issues(payload) == []


def test_local_engagement_guard_repairs_remaining_model_misses() -> None:
    payload = {
        "hook": (
            "Considering Atomy USA? You might be wondering which account is right before you "
            "complete the registration form and accept the agreement."
        ),
        "body": [
            "The registration guide separates consumer and distributor paths.",
            "The sponsor decision appears later in the registration process.",
            "The agreement explains member responsibilities and terms.",
            "The final screen asks applicants to review their information.",
            "The official plan explains Personal PV, or PV, and qualification rules.",
        ],
        "cta": "Clarity makes the process easier.",
    }

    polished = _enforce_engagement_structure(payload, "Atomy")

    assert _engagement_issues(polished) == []
    assert polished["hook"].startswith("The easiest-looking Atomy choice")
    assert "next two minutes" not in " ".join(polished["body"])
    assert "Personal PV, or PV" not in " ".join(polished["body"])
    assert polished["cta"].startswith("If you want help")


def test_local_engagement_guard_uses_duration_neutral_promise() -> None:
    payload = {
        "hook": (
            "Choose the wrong Atomy account, and the registration form can create avoidable "
            "friction before you understand the trade-off."
        ),
        "body": [
            "The official guide separates two registration paths.",
            "A sponsor appears in both paths.",
            "The member agreement explains responsibilities.",
            "The compensation plan needs careful review.",
            "The final decision should match your actual goal.",
        ],
        "cta": "Ask for a guided walkthrough if you want help checking the official sources.",
    }

    polished = _enforce_engagement_structure(payload, "Atomy")

    assert "By the end, you'll know" in polished["body"][0]
    assert "next two minutes" not in polished["body"][0]


def test_retention_anchors_survive_hard_word_budget() -> None:
    hook = " ".join(f"hook{index}" for index in range(24))
    body = [
        "In two minutes, you'll know what to decide and what to verify. "
        + " ".join(f"first{index}" for index in range(40)),
        *[" ".join(f"section{section}word{index}" for index in range(48)) for section in range(5)],
    ]
    cta = "If you want help, ask for a guided walkthrough. " + " ".join(
        f"cta{index}" for index in range(25)
    )

    fitted_hook, fitted_body, fitted_cta = _reclaim_body_budget(hook, body, cta, 240)

    assert sum(_word_count(part) for part in [fitted_hook, *fitted_body, fitted_cta]) <= 240
    assert fitted_body[0].startswith("In two minutes, you'll know")
    assert fitted_cta.startswith("If you want help")


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
            "title_variants": [
                "Atomy Registration: What to Check First",
                "Before Joining Atomy, Verify These Details",
            ],
            "thumbnail_text_options": ["BEFORE YOU JOIN", "CHECK THIS FIRST", "TWO PATHS"],
            "packaging_hypothesis": "The pairing targets high-intent viewers comparing account paths.",
            "description_summary": "A concise summary of the membership decision and official sources.",
            "chapter_titles": [
                "Two Membership Paths",
                "Registration Requirements",
                "Sponsor Choice",
                "Questions Before You Join",
            ],
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
    assert 260 <= document.word_count <= settings.script.max_words


def test_script_normalization_honors_approved_packaging(settings) -> None:
    settings.script.title_override = "Atomy in 2026: What to Know Before You Join"
    settings.script.title_variants = ["Before Joining Atomy in 2026, Watch This"]
    settings.script.thumbnail_text_options = ["BEFORE YOU JOIN"]
    settings.script.packaging_hypothesis = "A researched launch package is locked for production."
    generator = ScriptGenerator.__new__(ScriptGenerator)
    generator.settings = settings
    payload = {
        "title": "A weaker model title",
        "title_variants": ["Another generated title"],
        "thumbnail_text_options": ["MODEL COPY"],
        "packaging_hypothesis": "A model-generated packaging idea.",
        "hook": (
            "Choose the wrong account first, and you may create avoidable friction. "
            "Three checks separate the paths before registration."
        ),
        "body": [
            "By the end, you'll know what to decide and verify before submitting the form.",
            "What are you joining for? Start with the intended outcome.",
            "But the account type is only the first trade-off.",
            "Here's the useful part: read the official agreement.",
            "If details remain unclear, pause before confirming.",
        ],
        "cta": "Ask for a guided walkthrough if you want help checking the official sources.",
        "facts_to_verify": [],
        "disclosures": [],
    }
    report = ResearchReport(
        query_date=date(2026, 8, 25),
        candidates=[],
        selected_title="Atomy in 2026",
        selected_angle="A decision guide",
        brand_focused=True,
    )

    document = generator._normalize(payload, "test", 145, report)

    assert document.title == settings.script.title_override
    assert document.title_variants == settings.script.title_variants
    assert document.thumbnail_text_options == settings.script.thumbnail_text_options
    assert document.packaging_hypothesis == settings.script.packaging_hypothesis
