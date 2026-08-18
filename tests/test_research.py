from __future__ import annotations

from datetime import date

from daily_video_factory.research import TopicResearcher


def _offline(researcher: TopicResearcher, monkeypatch) -> None:
    monkeypatch.setattr(researcher, "_youtube_suggestions", lambda: [])
    monkeypatch.setattr(researcher, "_google_trends", lambda: [])
    monkeypatch.setattr(researcher, "_reddit", lambda: [])


def test_editorial_rotation_is_brand_focused_and_grounded(settings, monkeypatch) -> None:
    researcher = TopicResearcher(settings)
    _offline(researcher, monkeypatch)
    report = researcher.run(date(2026, 8, 12))
    assert report.selected_title in settings.research.editorial_topics
    assert report.brand_focused is True
    assert len(report.evidence) == len(settings.research.official_sources)


def test_topic_override_is_applied_before_editorial_brief(settings, monkeypatch) -> None:
    researcher = TopicResearcher(settings)
    def unexpected_discovery() -> list:
        raise AssertionError("explicit topics must not trigger broad network discovery")

    monkeypatch.setattr(researcher, "_youtube_suggestions", unexpected_discovery)
    monkeypatch.setattr(researcher, "_google_trends", unexpected_discovery)
    monkeypatch.setattr(researcher, "_reddit", unexpected_discovery)
    report = researcher.run(date(2026, 8, 12), "How to join Atomy as a consumer")
    assert report.selected_title == "How to join Atomy as a consumer"
    assert report.brand_focused is True
    assert "registration" in report.selected_angle
    assert report.candidates[0].source == "user_topic"
