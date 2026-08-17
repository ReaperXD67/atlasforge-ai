from __future__ import annotations

from pathlib import Path

from daily_video_factory.exceptions import ProviderFailed
from daily_video_factory.models import Scene
from daily_video_factory.providers.base import Provider, ProviderChain
from daily_video_factory.providers.text import extract_json
from daily_video_factory.providers.video import (
    ComfyUIWan22Provider,
    GeminiOmniVideoProvider,
    PexelsStockVideoProvider,
)


class FakeProvider(Provider[str]):
    def __init__(self, name: str, available: bool, result: str | None = None) -> None:
        self.name = name
        self._available = available
        self.result = result

    def available(self) -> bool:
        return self._available


def test_extract_json_from_fence() -> None:
    assert extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_provider_chain_falls_through() -> None:
    providers = [FakeProvider("first", False), FakeProvider("second", True, "done")]
    result = ProviderChain(providers).run(
        "test", lambda provider: provider.result or (_ for _ in ()).throw(ProviderFailed("no"))
    )
    assert result.provider == "second"
    assert result.value == "done"


def test_pexels_video_prefers_1080p_over_unnecessary_4k(settings) -> None:
    provider = PexelsStockVideoProvider(settings)
    selected = provider._best_file(
        {
            "video_files": [
                {
                    "file_type": "video/mp4",
                    "width": 3840,
                    "height": 2160,
                    "fps": 30,
                    "link": "https://example.test/4k.mp4",
                },
                {
                    "file_type": "video/mp4",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "link": "https://example.test/1080.mp4",
                },
                {
                    "file_type": "video/mp4",
                    "width": 1280,
                    "height": 720,
                    "fps": 60,
                    "link": "https://example.test/720.mp4",
                },
            ]
        }
    )

    assert selected is not None
    assert selected["width"] == 1920


def test_pexels_video_semantic_score_beats_metadata_order(settings) -> None:
    provider = PexelsStockVideoProvider(settings)
    source = {"link": "https://example.test/video.mp4"}
    candidates = [
        ((0.0, 0.0, -60.0), {"id": 1}, source),
        ((0.0, 5.0, -24.0), {"id": 2}, source),
    ]

    ranked = provider._rank_candidates(candidates, {1: 0.2, 2: 0.9})

    assert ranked[0][1]["id"] == 2


def test_pexels_metadata_relevance_prefers_passport_over_generic_laptop(settings) -> None:
    provider = PexelsStockVideoProvider(settings)
    query = "hands holding passport identification beside laptop close up"
    passport = {"url": "https://pexels.test/video/hand-holding-a-passport-7010548/"}
    unrelated = {"url": "https://pexels.test/video/birth-chart-on-a-laptop-7221842/"}

    assert provider._semantic_ranker is not None
    assert provider._semantic_ranker._metadata_relevance(
        query, passport
    ) > provider._semantic_ranker._metadata_relevance(query, unrelated)


def test_pexels_metadata_relevance_understands_budget_planner_synonyms(settings) -> None:
    provider = PexelsStockVideoProvider(settings)
    query = "receipts notebook and budget planning overhead close up"
    planner = {"url": "https://pexels.test/video/woman-recording-receipts-in-a-planner/"}

    assert provider._semantic_ranker is not None
    assert provider._semantic_ranker._metadata_relevance(query, planner) >= 0.6


def test_pexels_rejects_explicitly_excluded_vehicle_class(settings) -> None:
    provider = PexelsStockVideoProvider(settings)

    assert provider._matches_exclusion(
        {"url": "https://www.pexels.com/video/exciting-night-go-kart-racing-123/"},
        ["go kart", "motorcycle"],
    )
    assert not provider._matches_exclusion(
        {"url": "https://www.pexels.com/video/sports-car-on-a-circuit-456/"},
        ["go kart", "motorcycle"],
    )


def test_wan_reference_workflow_wires_start_image(settings, monkeypatch, tmp_path: Path) -> None:
    reference = tmp_path / "cat.png"
    reference.write_bytes(b"image")
    scene = Scene(
        index=1,
        duration_seconds=5,
        narration="",
        video_prompt="A cat performs one stable dance move",
        visual_search_query="dancing cat",
        reference_image=reference,
        generation_task="image_to_video",
    )
    provider = ComfyUIWan22Provider(settings)
    monkeypatch.setattr(provider, "_upload_reference", lambda _path: "atlasforge/cat.png")

    workflow = provider._workflow(scene)

    assert workflow["56"]["class_type"] == "LoadImage"
    assert workflow["56"]["inputs"]["image"] == "atlasforge/cat.png"
    assert workflow["55"]["inputs"]["start_image"] == ["56", 0]


def test_gemini_omni_input_keeps_reference_before_prompt(tmp_path: Path) -> None:
    reference = tmp_path / "character.png"
    reference.write_bytes(b"png-data")
    scene = Scene(
        index=1,
        duration_seconds=5,
        narration="",
        video_prompt="Dance exactly on the supplied beat",
        visual_search_query="beat performance",
        reference_image=reference,
        generation_task="reference_to_video",
    )

    interaction_input = GeminiOmniVideoProvider.interaction_input(scene)

    assert [item["type"] for item in interaction_input] == ["image", "text"]
    assert interaction_input[-1]["text"] == scene.video_prompt
