from daily_video_factory.metadata import _thumbnail_copy, build_metadata
from daily_video_factory.models import Scene, ScriptDocument, Storyboard


def _script(**overrides) -> ScriptDocument:
    values = {
        "title": "Atomy in 2026: What to Know Before You Join",
        "title_variants": [
            "Before Joining Atomy in 2026, Watch This",
            "Atomy Business Explained: Consumer or Distributor?",
        ],
        "thumbnail_text_options": ["Before You Join", "Know This First", "Two Different Paths"],
        "packaging_hypothesis": "The package targets high-intent viewers researching membership.",
        "description_summary": "A concise description of the consumer and distributor decision.",
        "chapter_titles": [
            "Consumer or Distributor?",
            "Choosing a Sponsor",
            "Compensation Reality Check",
            "Questions Before You Join",
        ],
        "hook": "A consequential choice creates tension before the registration form appears.",
        "body": ["A useful section with enough detail for the metadata summary."],
        "cta": "Ask for a guided walkthrough if you want help checking the official information.",
        "full_text": "A complete narration.",
        "word_count": 100,
        "estimated_minutes": 1,
        "provider": "test",
    }
    values.update(overrides)
    return ScriptDocument(**values)


def test_metadata_preserves_packaging_variants(settings) -> None:
    script = _script()
    storyboard = Storyboard(title="test", total_duration_seconds=0, scenes=[], provider="test")

    metadata = build_metadata(script, storyboard, settings)

    assert metadata.title == script.title
    assert metadata.title_variants == [script.title, *script.title_variants]
    assert metadata.thumbnail_text == "BEFORE YOU JOIN"
    assert metadata.thumbnail_variants == [
        "BEFORE YOU JOIN",
        "KNOW THIS FIRST",
        "TWO DIFFERENT PATHS",
    ]
    assert metadata.packaging_hypothesis == script.packaging_hypothesis
    assert metadata.description.startswith(script.description_summary)
    assert metadata.hashtags == ["#Atomy", "#AtomyUSA", "#NetworkMarketing"]


def test_thumbnail_copy_has_topic_sensitive_fallback() -> None:
    primary, variants = _thumbnail_copy(
        _script(thumbnail_text_options=[]),
        "How to Join Atomy USA",
    )

    assert primary == "BEFORE YOU JOIN"
    assert variants == ["BEFORE YOU JOIN"]


def test_metadata_uses_all_supplied_semantic_chapters(settings) -> None:
    script = _script(
        chapter_titles=["Picture", "PV", "Smaller Leg", "Pools", "Reality Check"]
    )
    scenes = [
        Scene(
            index=index,
            duration_seconds=12,
            narration=f"Scene {index}",
            video_prompt=f"Scene {index}",
            visual_search_query=f"scene {index}",
        )
        for index in range(1, 11)
    ]
    storyboard = Storyboard(
        title="test",
        total_duration_seconds=120,
        scenes=scenes,
        provider="test",
    )

    metadata = build_metadata(script, storyboard, settings)

    assert len(metadata.chapters) == 5
    assert [chapter.split(" ", 1)[1] for chapter in metadata.chapters] == script.chapter_titles


def test_compensation_profile_uses_specific_hashtags(settings) -> None:
    settings.research.seed_topics = ["atomy compensation plan 2026"]
    metadata = build_metadata(
        _script(),
        Storyboard(title="test", total_duration_seconds=0, scenes=[], provider="test"),
        settings,
    )

    assert metadata.hashtags == ["#Atomy", "#AtomyBusiness", "#CompensationPlan"]
