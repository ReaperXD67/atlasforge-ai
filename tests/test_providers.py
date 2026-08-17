from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from daily_video_factory.exceptions import ProviderFailed
from daily_video_factory.media.ai_quality import AIClipQualityReport
from daily_video_factory.models import Scene
from daily_video_factory.providers.base import Provider, ProviderChain
from daily_video_factory.providers.text import extract_json
from daily_video_factory.providers.video import (
    ComfyUISDXLReferenceProvider,
    ComfyUIWan22Provider,
    GeminiOmniVideoProvider,
    LocalSceneScheduler,
    PexelsReferenceImageProvider,
    PexelsStockVideoProvider,
    _comfy_model_choices,
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


def test_comfy_model_choices_supports_dynamic_combo_schema() -> None:
    node = {
        "input": {"required": {"model_name": ["COMBO", {"options": ["rife_v4.26.safetensors"]}]}}
    }

    assert _comfy_model_choices(node, "model_name") == ["rife_v4.26.safetensors"]


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


def test_reference_director_falls_back_to_top_local_rank_without_openrouter(
    settings, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = PexelsReferenceImageProvider(settings)
    image = Image.new("RGB", (64, 96), "gray")

    selected = provider._vision_pick(
        "unbranded silver race car",
        [({"id": 1}, 0.8, image), ({"id": 2}, 0.7, image)],
    )

    assert selected == 0


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
    assert workflow["59"]["inputs"]["model_name"] == "rife_v4.26.safetensors"
    assert workflow["60"]["inputs"]["images"] == ["8", 0]
    assert workflow["57"]["inputs"]["images"] == ["60", 0]
    assert workflow["57"]["inputs"]["fps"] == 48


def test_sdxl_reference_workflow_uses_full_resolution_plate(settings) -> None:
    provider = ComfyUISDXLReferenceProvider(settings)

    workflow = provider._workflow("A photoreal cat in a professional pit garage", seed=42)

    assert workflow["1"]["inputs"]["ckpt_name"] == "sd_xl_base_1.0.safetensors"
    assert workflow["4"]["inputs"] == {"width": 768, "height": 1344, "batch_size": 1}
    assert workflow["5"]["inputs"]["sampler_name"] == "dpmpp_2m"
    assert workflow["5"]["inputs"]["steps"] == 28
    assert workflow["5"]["inputs"]["seed"] == 42


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


def test_local_scheduler_requires_explicit_necessity(settings, tmp_path: Path) -> None:
    scheduler = LocalSceneScheduler(settings)
    scene = Scene(
        index=1,
        duration_seconds=5,
        narration="",
        video_prompt="A cinematic hook",
        visual_search_query="person at desk",
        visual_mode="local_ai_candidate",
        premium_score=1,
    )

    generated, costs = scheduler.generate([scene], tmp_path)

    assert generated == {}
    assert costs == []


def test_local_scheduler_selects_only_a_passing_best_of_candidate(
    settings, monkeypatch, tmp_path: Path
) -> None:
    class FakeLocalProvider:
        name = "fake_local"

        def available(self) -> bool:
            return True

        def generate(self, scene: Scene, output: Path) -> Path:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(str(scene.generation_seed), encoding="utf-8")
            return output

    class FakeInspector:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def inspect(self, clip: Path, **_kwargs) -> AIClipQualityReport:
            accepted = "candidate_02" in clip.name
            return AIClipQualityReport(
                clip=clip,
                passed=accepted,
                score=0.9 if accepted else 0.2,
                checks={"semantic_realism": accepted},
                metrics={},
                reasons=[] if accepted else ["continuity failure"],
                sampled_frames=9,
            )

    monkeypatch.setattr("daily_video_factory.providers.video.SyntheticClipInspector", FakeInspector)
    settings.video.local_generation_enabled = True
    settings.video.local_generation_quality_gate = True
    settings.video.local_generation_candidates = 2
    scheduler = LocalSceneScheduler(settings)
    scheduler.providers = [FakeLocalProvider()]  # type: ignore[list-item]
    scene = Scene(
        index=1,
        duration_seconds=5,
        narration="",
        video_prompt="A rigid product moves once",
        visual_search_query="product",
        visual_mode="local_ai_candidate",
        premium_score=1,
        generation_seed=10,
        ai_generation_required=True,
        ai_generation_reason="No licensed clip can show this fictional product action.",
    )

    generated, costs = scheduler.generate([scene], tmp_path)

    selected = generated[1]
    report = json.loads(selected.with_suffix(".quality.json").read_text(encoding="utf-8"))
    assert selected.read_text(encoding="utf-8") == str(1_000_013)
    assert report["decision"] == "accepted"
    assert report["selected_seed"] == 1_000_013
    assert len(report["candidates"]) == 2
    assert costs[0].note.startswith("Best-of-2 admitted")
