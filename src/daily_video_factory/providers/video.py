from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import uuid
from abc import abstractmethod
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from ..config import Settings
from ..exceptions import ProviderFailed
from ..models import CostEntry, Scene
from .base import Provider

StockCandidate = tuple[tuple[float, float, float], dict[str, Any], dict[str, Any]]


class LocalClipRanker:
    """Rerank stock thumbnails locally with CLIP; fail closed to metadata ranking."""

    def __init__(self, model_name: str, max_candidates: int) -> None:
        self.model_name = model_name
        self.max_candidates = max_candidates
        self._model: Any | None = None
        self._processor: Any | None = None
        self._disabled = False

    @staticmethod
    def _thumbnail_url(video: dict[str, Any]) -> str | None:
        pictures = video.get("video_pictures") or []
        usable = [
            picture
            for picture in pictures
            if isinstance(picture, dict) and (picture.get("picture") or picture.get("image"))
        ]
        if not usable:
            return None
        middle = usable[len(usable) // 2]
        return str(middle.get("picture") or middle.get("image"))

    def _load(self) -> tuple[Any, Any] | None:
        if self._disabled:
            return None
        if self._model is not None and self._processor is not None:
            return self._model, self._processor
        try:
            from transformers import CLIPModel, CLIPProcessor

            self._processor = CLIPProcessor.from_pretrained(self.model_name)
            self._model = CLIPModel.from_pretrained(self.model_name)
            self._model.eval()
            return self._model, self._processor
        except Exception:
            self._disabled = True
            return None

    @staticmethod
    def _metadata_relevance(query: str, video: dict[str, Any]) -> float:
        generic = {
            "a",
            "adult",
            "and",
            "at",
            "beside",
            "broll",
            "cinematic",
            "close",
            "documentary",
            "frame",
            "hand",
            "hands",
            "home",
            "of",
            "on",
            "person",
            "professional",
            "the",
            "up",
            "video",
            "with",
        }
        synonyms = {
            "budget": {"expense", "expenses", "planner", "receipts"},
            "completing": {"typing", "application", "registration"},
            "identification": {"passport", "identity", "id"},
            "mentor": {"mentoring", "coach", "coaching", "tutor", "tutoring"},
            "passport": {"identification", "identity", "id"},
            "mobile": {"phone", "smartphone"},
            "notebook": {"notes", "planner", "writing"},
            "phone": {"mobile", "smartphone"},
            "planning": {"planner", "recording", "notes"},
            "product": {"products", "cosmetic", "cosmetics", "beauty", "serum"},
            "products": {"product", "cosmetic", "cosmetics", "beauty", "serum"},
            "registration": {"register", "signup", "application"},
            "receipts": {"receipt", "budget", "expense", "expenses"},
            "register": {"registration", "signup", "application"},
            "shelf": {"shelves", "display"},
            "skincare": {"skin", "cosmetic", "cosmetics", "beauty", "serum"},
            "taking": {"writing", "notes", "recording"},
        }

        def tokens(value: str) -> set[str]:
            return set(re.findall(r"[a-z0-9]+", value.casefold()))

        query_tokens = tokens(query) - generic
        source_tokens = tokens(str(video.get("url") or "")) - generic
        if not query_tokens or not source_tokens:
            return 0.0
        matched = 0
        for token in query_tokens:
            related = {token, *synonyms.get(token, set())}
            if related & source_tokens:
                matched += 1
        return matched / len(query_tokens)

    def rank(
        self,
        query: str,
        videos: list[dict[str, Any]],
        exclusions: list[str] | None = None,
    ) -> dict[int, float]:
        loaded = self._load()
        if loaded is None:
            return {}
        model, processor = loaded
        ids: list[int] = []
        images: list[Image.Image] = []
        for video in videos[: self.max_candidates]:
            thumbnail_url = self._thumbnail_url(video)
            if not thumbnail_url:
                continue
            try:
                response = httpx.get(thumbnail_url, timeout=15, follow_redirects=True)
                response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as image:
                    images.append(image.convert("RGB"))
                ids.append(int(video["id"]))
            except Exception:
                continue
        if not images:
            return {}
        positive = f"A relevant documentary b-roll frame showing {query}."
        negative = "An unrelated generic stock image about a different activity and subject."
        text_prompts = [positive, negative]
        if exclusions:
            text_prompts.append(
                "An off-brief stock frame dominated by " + ", ".join(exclusions) + "."
            )
        try:
            import torch

            inputs = processor(
                text=text_prompts, images=images, return_tensors="pt", padding=True
            )
            with torch.inference_mode():
                probabilities = model(**inputs).logits_per_image.softmax(dim=1)[:, 0].tolist()
            semantic_scores = {
                asset_id: float(score)
                for asset_id, score in zip(ids, probabilities, strict=True)
            }
            by_id = {int(video["id"]): video for video in videos}
            return {
                asset_id: 0.6 * self._metadata_relevance(query, by_id[asset_id])
                + 0.4 * semantic_score
                for asset_id, semantic_score in semantic_scores.items()
            }
        except Exception:
            return {}


class StockVideoProvider(Provider[Path]):
    @abstractmethod
    def generate(
        self,
        scene: Scene,
        output: Path,
        *,
        used_asset_ids: set[int],
        used_creators: set[str],
        target_duration: float,
    ) -> Path:
        pass


class PexelsStockVideoProvider(StockVideoProvider):
    """Download a unique, landscape stock clip and persist its attribution record."""

    name = "pexels_video"

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video
        self._semantic_ranker = (
            LocalClipRanker(
                self.cfg.stock_video_semantic_model,
                self.cfg.stock_video_semantic_candidates,
            )
            if self.cfg.stock_video_semantic_ranking
            else None
        )

    def available(self) -> bool:
        return bool(os.getenv("PEXELS_API_KEY"))

    def _best_file(self, video: dict[str, Any]) -> dict[str, Any] | None:
        candidates = [
            item
            for item in video.get("video_files", [])
            if item.get("file_type") == "video/mp4"
            and int(item.get("width") or 0) >= self.cfg.stock_video_min_width
            and int(item.get("height") or 0) > 0
            and item.get("link")
        ]
        if not candidates:
            return None

        target_ratio = self.cfg.width / self.cfg.height

        def score(item: dict[str, Any]) -> tuple[float, float, float]:
            width = int(item.get("width") or 0)
            height = int(item.get("height") or 1)
            ratio_error = abs(width / height - target_ratio)
            # Prefer 1080p without downloading a 4K source that FFmpeg will immediately shrink.
            width_error = abs(width - self.cfg.width)
            fps = float(item.get("fps") or 0)
            return (ratio_error, width_error, -fps)

        return min(candidates, key=score)

    @staticmethod
    def _matches_exclusion(video: dict[str, Any], exclusions: list[str]) -> bool:
        """Reject an explicitly off-brief subject when Pexels exposes it in metadata."""
        metadata = " ".join(
            str(value or "")
            for value in (
                video.get("url"),
                video.get("title"),
                video.get("description"),
            )
        ).casefold()
        metadata_tokens = set(re.findall(r"[a-z0-9]+", metadata))
        for exclusion in exclusions:
            exclusion_tokens = set(re.findall(r"[a-z0-9]+", exclusion.casefold()))
            if exclusion_tokens and exclusion_tokens <= metadata_tokens:
                return True
        return False

    @staticmethod
    def _rank_candidates(
        candidates: list[StockCandidate], semantic_scores: dict[int, float]
    ) -> list[StockCandidate]:
        return sorted(
            candidates,
            key=lambda item: (
                -semantic_scores.get(int(item[1].get("id") or 0), -1.0),
                *item[0],
            ),
        )

    def generate(
        self,
        scene: Scene,
        output: Path,
        *,
        used_asset_ids: set[int],
        used_creators: set[str],
        target_duration: float,
    ) -> Path:
        headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
        response = httpx.get(
            "https://api.pexels.com/v1/videos/search",
            headers=headers,
            params={
                "query": scene.visual_search_query,
                "orientation": "landscape",
                "size": "medium",
                "per_page": self.cfg.stock_video_candidates_per_scene,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise ProviderFailed(f"Pexels video search returned HTTP {response.status_code}")
        fresh_creator_candidates: list[StockCandidate] = []
        reuse_creator_candidates: list[StockCandidate] = []
        for video in response.json().get("videos", []):
            asset_id = int(video.get("id") or 0)
            if not asset_id or asset_id in used_asset_ids:
                continue
            if self._matches_exclusion(video, scene.visual_exclusion_terms):
                continue
            source = self._best_file(video)
            if source is None:
                continue
            duration = float(video.get("duration") or 0)
            if duration < self.cfg.stock_video_min_duration_seconds:
                continue
            covers_scene = 0.0 if duration >= target_duration else target_duration - duration
            excess = abs(duration - target_duration)
            fps = float(source.get("fps") or 0)
            candidate = ((covers_scene, excess, -fps), video, source)
            creator = str((video.get("user") or {}).get("name") or "").casefold().strip()
            if creator and creator in used_creators:
                reuse_creator_candidates.append(candidate)
            else:
                fresh_creator_candidates.append(candidate)
        candidates = fresh_creator_candidates or reuse_creator_candidates
        if not candidates:
            raise ProviderFailed(
                f"Pexels returned no usable video for '{scene.visual_search_query}'"
            )

        semantic_scores = (
            self._semantic_ranker.rank(
                scene.visual_search_query,
                [candidate[1] for candidate in candidates],
                scene.visual_exclusion_terms,
            )
            if self._semantic_ranker is not None
            else {}
        )
        if semantic_scores:
            candidates = [
                candidate
                for candidate in candidates
                if semantic_scores.get(int(candidate[1].get("id") or 0), -1)
                >= self.cfg.stock_video_min_visual_relevance
            ]
            if not candidates:
                raise ProviderFailed(
                    f"No Pexels clip passed local visual relevance for "
                    f"'{scene.visual_search_query}'"
                )
        errors: list[str] = []
        for _score, video, source in self._rank_candidates(candidates, semantic_scores):
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                with httpx.stream(
                    "GET",
                    str(source["link"]),
                    timeout=self.cfg.stock_video_download_timeout_seconds,
                    follow_redirects=True,
                ) as download:
                    download.raise_for_status()
                    with output.open("wb") as destination:
                        for chunk in download.iter_bytes(1024 * 1024):
                            destination.write(chunk)
                if output.stat().st_size < 100_000:
                    raise ProviderFailed("downloaded clip is implausibly small")
                asset_id = int(video["id"])
                used_asset_ids.add(asset_id)
                creator_name = str((video.get("user") or {}).get("name") or "").strip()
                if creator_name:
                    used_creators.add(creator_name.casefold())
                attribution = {
                    "provider": "Pexels",
                    "media_type": "video",
                    "video_id": asset_id,
                    "creator": creator_name,
                    "creator_url": (video.get("user") or {}).get("url"),
                    "video_url": video.get("url"),
                    "search_query": scene.visual_search_query,
                    "visual_relevance_score": semantic_scores.get(asset_id),
                    "visual_ranking_model": (
                        self.cfg.stock_video_semantic_model if semantic_scores else None
                    ),
                    "source_width": source.get("width"),
                    "source_height": source.get("height"),
                    "source_fps": source.get("fps"),
                    "source_duration_seconds": video.get("duration"),
                }
                output.with_suffix(".license.json").write_text(
                    json.dumps(attribution, indent=2), encoding="utf-8"
                )
                return output
            except Exception as exc:
                output.unlink(missing_ok=True)
                errors.append(f"{video.get('id')}: {exc}")
        raise ProviderFailed("Pexels video downloads failed: " + " | ".join(errors[:3]))


class StockVideoScheduler:
    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video
        mapping: dict[str, StockVideoProvider] = {
            "pexels_video": PexelsStockVideoProvider(settings),
        }
        self.providers = [
            mapping[name] for name in self.cfg.stock_video_providers if name in mapping
        ]

    def generate(
        self,
        scenes: list[Scene],
        output_dir: Path,
        *,
        excluded_scene_ids: set[int] | None = None,
    ) -> dict[int, Path]:
        if not self.cfg.stock_video_enabled or self.cfg.stock_video_max_scenes_per_video <= 0:
            return {}
        output_dir.mkdir(parents=True, exist_ok=True)
        results: dict[int, Path] = {}
        used_asset_ids: set[int] = set()
        used_creators: set[str] = set()
        excluded = excluded_scene_ids or set()
        eligible = [
            scene
            for scene in scenes
            if scene.index not in excluded and scene.visual_mode != "information_card"
        ]
        for scene in eligible[: self.cfg.stock_video_max_scenes_per_video]:
            for provider in self.providers:
                if not provider.available():
                    continue
                try:
                    output = output_dir / f"scene_{scene.index:03d}_{provider.name}.mp4"
                    results[scene.index] = provider.generate(
                        scene,
                        output,
                        used_asset_ids=used_asset_ids,
                        used_creators=used_creators,
                        target_duration=scene.duration_seconds,
                    )
                    scene.selected_video_provider = provider.name
                    break
                except Exception:
                    continue
        return results


class LocalVideoProvider(Provider[Path]):
    @abstractmethod
    def generate(self, scene: Scene, output: Path) -> Path:
        pass


class ComfyUIWan22Provider(LocalVideoProvider):
    """Call a stock ComfyUI Wan 2.2 TI2V 5B graph with no custom nodes."""

    name = "comfyui_wan22"
    negative_prompt = (
        "text, subtitles, logo, watermark, static frame, flicker, jitter, camera shake, "
        "deformed hands, distorted face, low quality, oversaturated, duplicate people"
    )

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video
        self.base_url = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")

    def available(self) -> bool:
        try:
            return httpx.get(f"{self.base_url}/system_stats", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False

    def _workflow(self, scene: Scene) -> dict[str, dict[str, Any]]:
        seed = int(hashlib.sha256(scene.video_prompt.encode("utf-8")).hexdigest()[:14], 16)
        prompt = (
            f"{scene.video_prompt}. The subject action is {scene.visual_search_query}. "
            "Stable tripod or smooth dolly movement, coherent motion, documentary realism, "
            "cinematic color, physically plausible details."
        )
        return {
            "37": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "wan2.2_ti2v_5B_fp16.safetensors",
                    "weight_dtype": "default",
                },
            },
            "38": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "type": "wan",
                    "device": "default",
                },
            },
            "39": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "wan2.2_vae.safetensors"},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["38", 0]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": self.negative_prompt, "clip": ["38", 0]},
            },
            "48": {
                "class_type": "ModelSamplingSD3",
                "inputs": {"model": ["37", 0], "shift": 8},
            },
            "55": {
                "class_type": "Wan22ImageToVideoLatent",
                "inputs": {
                    "width": self.cfg.comfyui_width,
                    "height": self.cfg.comfyui_height,
                    "length": self.cfg.comfyui_frames,
                    "batch_size": 1,
                    "vae": ["39", 0],
                },
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": self.cfg.comfyui_steps,
                    "cfg": self.cfg.comfyui_cfg,
                    "sampler_name": "uni_pc",
                    "scheduler": "simple",
                    "denoise": 1,
                    "model": ["48", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["55", 0],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["39", 0]},
            },
            "57": {
                "class_type": "CreateVideo",
                "inputs": {"images": ["8", 0], "fps": self.cfg.comfyui_fps},
            },
            "58": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["57", 0],
                    "filename_prefix": f"atlasforge/scene_{scene.index:03d}",
                    "format": "auto",
                    "codec": "auto",
                },
            },
        }

    @staticmethod
    def _output_file(history: dict[str, Any]) -> dict[str, Any] | None:
        for node in history.get("outputs", {}).values():
            for key in ("videos", "gifs", "images"):
                for item in node.get(key, []) if isinstance(node, dict) else []:
                    filename = str(item.get("filename", ""))
                    if filename.lower().endswith((".mp4", ".webm", ".mov", ".mkv")):
                        return item
        return None

    def generate(self, scene: Scene, output: Path) -> Path:
        prompt_response = httpx.post(
            f"{self.base_url}/prompt",
            json={"prompt": self._workflow(scene), "client_id": str(uuid.uuid4())},
            timeout=30,
        )
        if prompt_response.status_code >= 400:
            raise ProviderFailed(f"ComfyUI rejected workflow: {prompt_response.text[:1000]}")
        prompt_id = prompt_response.json().get("prompt_id")
        if not prompt_id:
            raise ProviderFailed("ComfyUI returned no prompt_id")
        deadline = time.monotonic() + self.cfg.comfyui_timeout_minutes * 60
        while time.monotonic() < deadline:
            history_response = httpx.get(f"{self.base_url}/history/{prompt_id}", timeout=15)
            history_response.raise_for_status()
            history = history_response.json().get(prompt_id)
            if history:
                item = self._output_file(history)
                if item is None:
                    status = history.get("status", {})
                    if status.get("status_str") == "error":
                        raise ProviderFailed(f"ComfyUI generation failed: {status}")
                    raise ProviderFailed("ComfyUI finished but returned no video file")
                video_response = httpx.get(
                    f"{self.base_url}/view",
                    params={
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    },
                    timeout=180,
                    follow_redirects=True,
                )
                video_response.raise_for_status()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(video_response.content)
                output.with_suffix(".license.json").write_text(
                    json.dumps(
                        {
                            "provider": "ComfyUI",
                            "model": "Wan2.2 TI2V 5B",
                            "license": "Apache-2.0",
                            "prompt_id": prompt_id,
                            "prompt": scene.video_prompt,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                return output
            time.sleep(5)
        raise ProviderFailed(
            f"ComfyUI generation timed out after {self.cfg.comfyui_timeout_minutes} minutes"
        )


class LocalSceneScheduler:
    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video
        mapping: dict[str, LocalVideoProvider] = {
            "comfyui_wan22": ComfyUIWan22Provider(settings),
        }
        self.providers = [
            mapping[name] for name in self.cfg.local_generation_providers if name in mapping
        ]

    def generate(
        self, scenes: list[Scene], output_dir: Path
    ) -> tuple[dict[int, Path], list[CostEntry]]:
        if (
            not self.cfg.local_generation_enabled
            or self.cfg.local_generation_max_scenes_per_video <= 0
        ):
            return {}, []
        candidates = [
            scene
            for scene in scenes
            if scene.visual_mode == "local_ai_candidate"
            or scene.premium_score >= self.cfg.local_generation_min_score
        ]
        selected = sorted(candidates, key=lambda scene: scene.premium_score, reverse=True)[
            : self.cfg.local_generation_max_scenes_per_video
        ]
        results: dict[int, Path] = {}
        costs: list[CostEntry] = []
        for scene in selected:
            for provider in self.providers:
                if not provider.available():
                    continue
                try:
                    path = output_dir / f"scene_{scene.index:03d}_{provider.name}.mp4"
                    results[scene.index] = provider.generate(scene, path)
                    scene.selected_video_provider = provider.name
                    costs.append(
                        CostEntry(
                            stage="video",
                            provider=provider.name,
                            estimated_usd=0,
                            note=f"Local GPU scene {scene.index}; electricity only",
                        )
                    )
                    break
                except Exception:
                    continue
        return results, costs


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
