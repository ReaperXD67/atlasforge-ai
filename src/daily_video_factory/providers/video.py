from __future__ import annotations

import os
import time
from abc import abstractmethod
from pathlib import Path

import httpx

from ..config import Settings
from ..exceptions import ProviderFailed
from ..models import CostEntry, Scene
from .base import Provider


class PremiumVideoProvider(Provider[Path]):
    estimated_cost_usd: float

    @abstractmethod
    def generate(self, scene: Scene, output: Path) -> Path:
        pass


class VeoVideoProvider(PremiumVideoProvider):
    name = "veo"

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video
        self.estimated_cost_usd = (
            self.cfg.cloud_clip_seconds * self.cfg.veo_estimated_usd_per_second
        )

    def available(self) -> bool:
        if not os.getenv("GOOGLE_API_KEY"):
            return False
        try:
            from google import genai  # noqa: F401

            return True
        except ImportError:
            return False

    def generate(self, scene: Scene, output: Path) -> Path:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProviderFailed("Install the google extra to use Veo") from exc
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        operation = client.models.generate_videos(
            model=self.cfg.veo_model,
            prompt=scene.video_prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9",
                resolution="720p",
                duration_seconds=self.cfg.cloud_clip_seconds,
                number_of_videos=1,
            ),
        )
        deadline = time.monotonic() + 30 * 60
        while not operation.done:
            if time.monotonic() > deadline:
                raise ProviderFailed("Veo generation timed out after 30 minutes")
            time.sleep(10)
            operation = client.operations.get(operation)
        if not operation.response or not operation.response.generated_videos:
            raise ProviderFailed(f"Veo generation failed: {operation.error}")
        generated = operation.response.generated_videos[0]
        if generated.video is None:
            raise ProviderFailed("Veo returned an empty video payload")
        client.files.download(file=generated.video)
        output.parent.mkdir(parents=True, exist_ok=True)
        generated.video.save(str(output))
        return output


class MiniMaxVideoProvider(PremiumVideoProvider):
    name = "minimax"

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video
        self.estimated_cost_usd = self.cfg.minimax_estimated_usd_per_clip
        self.headers = {"Authorization": f"Bearer {os.getenv('MINIMAX_API_KEY', '')}"}

    def available(self) -> bool:
        return bool(os.getenv("MINIMAX_API_KEY"))

    def generate(self, scene: Scene, output: Path) -> Path:
        response = httpx.post(
            "https://api.minimax.io/v1/video_generation",
            headers=self.headers,
            json={
                "model": self.cfg.minimax_model,
                "prompt": scene.video_prompt,
                "duration": 6 if self.cfg.cloud_clip_seconds <= 8 else 10,
                "resolution": self.cfg.minimax_resolution,
            },
            timeout=60,
        )
        if response.status_code >= 400:
            raise ProviderFailed(f"MiniMax create task failed: {response.text[:500]}")
        task_id = response.json().get("task_id")
        if not task_id:
            raise ProviderFailed("MiniMax returned no task_id")
        deadline = time.monotonic() + 30 * 60
        file_id: str | None = None
        while time.monotonic() < deadline:
            time.sleep(10)
            status_response = httpx.get(
                "https://api.minimax.io/v1/query/video_generation",
                headers=self.headers,
                params={"task_id": task_id},
                timeout=30,
            )
            status_response.raise_for_status()
            payload = status_response.json()
            status = str(payload.get("status", "")).lower()
            if status == "success":
                file_id = str(payload["file_id"])
                break
            if status == "fail":
                raise ProviderFailed(f"MiniMax generation failed: {payload.get('error_message')}")
        if not file_id:
            raise ProviderFailed("MiniMax generation timed out after 30 minutes")
        file_response = httpx.get(
            "https://api.minimax.io/v1/files/retrieve",
            headers=self.headers,
            params={"file_id": file_id},
            timeout=30,
        )
        file_response.raise_for_status()
        download_url = file_response.json()["file"]["download_url"]
        video_response = httpx.get(download_url, timeout=180, follow_redirects=True)
        video_response.raise_for_status()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(video_response.content)
        return output


class PremiumSceneScheduler:
    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video
        mapping: dict[str, PremiumVideoProvider] = {
            "veo": VeoVideoProvider(settings),
            "minimax": MiniMaxVideoProvider(settings),
        }
        self.providers = [mapping[name] for name in self.cfg.premium_providers if name in mapping]

    def generate(
        self, scenes: list[Scene], output_dir: Path
    ) -> tuple[dict[int, Path], list[CostEntry]]:
        if not self.cfg.enable_premium_scenes or self.cfg.premium_max_scenes_per_video <= 0:
            return {}, []
        selected = sorted(scenes, key=lambda scene: scene.premium_score, reverse=True)
        selected = selected[: self.cfg.premium_max_scenes_per_video]
        results: dict[int, Path] = {}
        costs: list[CostEntry] = []
        spent = 0.0
        for scene in selected:
            for provider in self.providers:
                if not provider.available():
                    continue
                projected = spent + provider.estimated_cost_usd
                if projected > self.cfg.premium_daily_budget_usd + 1e-9:
                    continue
                try:
                    path = output_dir / f"scene_{scene.index:03d}_{provider.name}.mp4"
                    provider.generate(scene, path)
                    results[scene.index] = path
                    scene.selected_video_provider = provider.name
                    spent = projected
                    costs.append(
                        CostEntry(
                            stage="video",
                            provider=provider.name,
                            estimated_usd=provider.estimated_cost_usd,
                            note=f"Premium scene {scene.index}",
                        )
                    )
                    break
                except Exception:
                    continue
        return results, costs
