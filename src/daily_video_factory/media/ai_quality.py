from __future__ import annotations

import base64
import io
import json
import math
import os
import tempfile
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from ..config import Settings
from .ffmpeg import FFmpeg


class AIClipQualityReport(BaseModel):
    """Small, reproducible admission report for a synthetic clip candidate."""

    clip: Path
    passed: bool
    score: float = Field(ge=0, le=1)
    checks: dict[str, bool]
    metrics: dict[str, float | None]
    reasons: list[str]
    sampled_frames: int
    semantic_judge: dict[str, object] | None = None
    evaluator: str = "atlasforge-lightweight-vbench-inspired-v1"


class SyntheticClipInspector:
    """Reject obvious blur, flicker, cuts, freezes, and reference drift locally.

    This intentionally stays lightweight enough for the target laptop and Docker image. It
    borrows the *dimensions* used by video-generation benchmarks, but it does not claim to run
    VBench itself. CLIP is an optional extra signal when its cached model is available.
    """

    def __init__(self, settings: Settings, ffmpeg: FFmpeg | None = None) -> None:
        self.settings = settings
        self.cfg = settings.video
        self.ffmpeg = ffmpeg or FFmpeg()

    @staticmethod
    def _rgb(image: Image.Image, size: tuple[int, int] = (320, 568)) -> np.ndarray:
        fitted = ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
        return np.asarray(fitted, dtype=np.float32) / 255.0

    @staticmethod
    def _gray(rgb: np.ndarray) -> np.ndarray:
        return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722

    @classmethod
    def _sharpness(cls, rgb: np.ndarray) -> float:
        gray = cls._gray(rgb)
        laplacian = (
            -4 * gray[1:-1, 1:-1]
            + gray[:-2, 1:-1]
            + gray[2:, 1:-1]
            + gray[1:-1, :-2]
            + gray[1:-1, 2:]
        )
        raw = float(np.var(laplacian) * 1_000_000)
        low, high = math.log1p(18), math.log1p(1800)
        return float(np.clip((math.log1p(raw) - low) / (high - low), 0, 1))

    @classmethod
    def _exposure(cls, rgb: np.ndarray) -> float:
        gray = cls._gray(rgb)
        clipped = float(np.mean((gray < 0.018) | (gray > 0.982)))
        mean = float(np.mean(gray))
        mean_penalty = min(1.0, abs(mean - 0.48) / 0.48)
        return float(np.clip(1 - clipped * 4.5 - mean_penalty * 0.18, 0, 1))

    @classmethod
    def _reference_similarity(cls, first: np.ndarray, reference: Image.Image) -> float:
        target = cls._rgb(reference, (first.shape[1], first.shape[0]))
        mae = float(np.mean(np.abs(first - target)))
        hist_score = 0.0
        for channel in range(3):
            left, _ = np.histogram(first[..., channel], bins=32, range=(0, 1), density=True)
            right, _ = np.histogram(target[..., channel], bins=32, range=(0, 1), density=True)
            left /= max(float(left.sum()), 1e-9)
            right /= max(float(right.sum()), 1e-9)
            hist_score += float(np.minimum(left, right).sum()) / 3
        return float(np.clip(0.72 * (1 - mae) + 0.28 * hist_score, 0, 1))

    def _clip_realism(self, frames: list[Image.Image]) -> float | None:
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            processor = CLIPProcessor.from_pretrained(
                self.cfg.stock_video_semantic_model, local_files_only=True
            )
            model = CLIPModel.from_pretrained(
                self.cfg.stock_video_semantic_model, local_files_only=True
            )
            model.eval()
            prompts = [
                "a natural frame captured by a real camera with coherent rigid geometry",
                "an obviously artificial AI video frame with warped melting or malformed objects",
                "a blurry broken low quality synthetic video frame",
            ]
            selected = frames[:: max(1, len(frames) // 3)][:3]
            inputs = processor(text=prompts, images=selected, return_tensors="pt", padding=True)
            with torch.inference_mode():
                probability = model(**inputs).logits_per_image.softmax(dim=1)[:, 0]
            return float(torch.median(probability).item())
        except Exception:
            return None

    @staticmethod
    def _contact_sheet(frames: list[Image.Image]) -> bytes:
        selected = frames[:9]
        thumb_width, thumb_height = 240, 426
        sheet = Image.new("RGB", (thumb_width * 3, thumb_height * 3), "black")
        for index, frame in enumerate(selected):
            thumb = ImageOps.fit(
                frame.convert("RGB"),
                (thumb_width, thumb_height),
                method=Image.Resampling.LANCZOS,
            )
            sheet.paste(thumb, ((index % 3) * thumb_width, (index // 3) * thumb_height))
        buffer = io.BytesIO()
        sheet.save(buffer, format="JPEG", quality=88, optimize=True)
        return buffer.getvalue()

    def _semantic_judge(
        self, frames: list[Image.Image], *, prompt: str
    ) -> dict[str, object] | None:
        if not self.cfg.local_generation_vlm_gate:
            return None
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return {
                "verdict": "unavailable",
                "critical_failure": True,
                "minimum_score": 0.0,
                "anomalies": ["OpenRouter semantic review is unavailable."],
            }
        encoded = base64.b64encode(self._contact_sheet(frames)).decode("ascii")
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "physical_realism",
                "anatomical_integrity",
                "temporal_consistency",
                "camera_authenticity",
                "critical_failure",
                "anomalies",
                "verdict",
            ],
            "properties": {
                "physical_realism": {"type": "number", "minimum": 0, "maximum": 1},
                "anatomical_integrity": {"type": "number", "minimum": 0, "maximum": 1},
                "temporal_consistency": {"type": "number", "minimum": 0, "maximum": 1},
                "camera_authenticity": {"type": "number", "minimum": 0, "maximum": 1},
                "critical_failure": {"type": "boolean"},
                "anomalies": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {"type": "string"},
                },
                "verdict": {"type": "string", "enum": ["pass", "reject"]},
            },
        }
        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/ReaperXD67/atlasforge-ai",
                    "X-OpenRouter-Title": "AtlasForge AI Quality Gate",
                },
                json={
                    "model": self.cfg.local_generation_vlm_model,
                    "temperature": 0,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a calibrated VFX footage supervisor. The 3x3 grid contains "
                                "nine chronological samples from one video and may be genuine camera "
                                "footage or synthetic. Do not assume either class. Normal subject or "
                                "camera displacement between tiles is motion, not inconsistency. Only "
                                "report an anomaly when its visual evidence is clear in at least two "
                                "adjacent tiles. Reject rubbery rigid objects, melting, "
                                "morphing, identity drift, duplicated or malformed anatomy, sliding "
                                "contact points, impossible mass/inertia, miniature-looking scale, "
                                "synthetic camera shake, inconsistent light/reflections, or any "
                                "sequence that would visibly read as AI-generated. Do not reward "
                                "cinematic color or sharpness when physics is wrong. Genuine coherent "
                                "camera footage should pass. A synthetic clip passes only when it could "
                                "survive normal social-media viewing as plausible camera footage."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Intended shot: {prompt or 'unspecified'}",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                                },
                            ],
                        },
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "synthetic_video_admission",
                            "strict": True,
                            "schema": schema,
                        },
                    },
                },
                timeout=90,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            scores = [
                float(result[name])
                for name in (
                    "physical_realism",
                    "anatomical_integrity",
                    "temporal_consistency",
                    "camera_authenticity",
                )
            ]
            result["minimum_score"] = min(scores)
            return result
        except Exception as exc:
            return {
                "verdict": "unavailable",
                "critical_failure": True,
                "minimum_score": 0.0,
                "anomalies": [f"Semantic review failed closed: {type(exc).__name__}"],
            }

    def inspect(
        self, clip: Path, *, reference: Path | None = None, prompt: str = ""
    ) -> AIClipQualityReport:
        duration = self.ffmpeg.duration(clip)
        sample_target = 9
        with tempfile.TemporaryDirectory(prefix="atlasforge-ai-quality-") as temporary:
            pattern = Path(temporary) / "frame_%02d.jpg"
            self.ffmpeg.run(
                [
                    "-i",
                    str(clip),
                    "-vf",
                    f"fps={sample_target / max(duration, 0.1):.8f},scale=320:-2:flags=lanczos",
                    "-frames:v",
                    str(sample_target),
                    "-q:v",
                    "2",
                    str(pattern),
                ]
            )
            frame_paths = sorted(Path(temporary).glob("frame_*.jpg"))
            pil_frames: list[Image.Image] = []
            arrays: list[np.ndarray] = []
            for path in frame_paths:
                with Image.open(path) as image:
                    loaded = image.convert("RGB")
                    pil_frames.append(loaded.copy())
                    arrays.append(self._rgb(loaded))

        if len(arrays) < 3:
            return AIClipQualityReport(
                clip=clip,
                passed=False,
                score=0,
                checks={"decodable": False},
                metrics={"duration_seconds": duration},
                reasons=["Fewer than three representative frames could be decoded."],
                sampled_frames=len(arrays),
            )

        sharpness = float(np.median([self._sharpness(frame) for frame in arrays]))
        exposure = float(np.median([self._exposure(frame) for frame in arrays]))
        grays = [self._gray(frame) for frame in arrays]
        adjacent_motion = [
            float(np.mean(np.abs(current - previous)))
            for previous, current in zip(grays, grays[1:], strict=False)
        ]
        motion = float(np.median(adjacent_motion))
        peak_motion = float(max(adjacent_motion))
        luminance_deltas = [
            abs(float(np.mean(current)) - float(np.mean(previous)))
            for previous, current in zip(grays, grays[1:], strict=False)
        ]
        # A median hides a one- or two-frame exposure flash. The 85th percentile catches brief
        # temporal defects without treating one ordinary edit-level fluctuation as the maximum.
        luminance_delta = float(np.percentile(luminance_deltas, 85))
        flicker_score = float(np.clip(1 - luminance_delta / 0.075, 0, 1))
        color_deltas = [
            float(np.linalg.norm(np.mean(current, axis=(0, 1)) - np.mean(previous, axis=(0, 1))))
            for previous, current in zip(arrays, arrays[1:], strict=False)
        ]
        color_delta = float(np.percentile(color_deltas, 85))
        color_flicker_score = float(np.clip(1 - color_delta / 0.16, 0, 1))
        if motion < 0.003:
            motion_score = motion / 0.003
        elif motion <= 0.16:
            motion_score = 1.0
        else:
            motion_score = float(np.clip(1 - (motion - 0.16) / 0.18, 0, 1))
        cut_score = float(np.clip(1 - max(0.0, peak_motion - 0.28) / 0.25, 0, 1))

        reference_similarity: float | None = None
        if reference is not None and reference.is_file():
            with Image.open(reference) as source:
                reference_similarity = self._reference_similarity(arrays[0], source)
        realism = self._clip_realism(pil_frames)
        semantic_judge = self._semantic_judge(pil_frames, prompt=prompt)

        semantic_minimum_value = (
            semantic_judge.get("minimum_score") if semantic_judge is not None else None
        )
        semantic_minimum = (
            float(semantic_minimum_value)
            if isinstance(semantic_minimum_value, int | float)
            else 0.0
        )
        components: list[tuple[float, float]] = [
            (sharpness, 0.22),
            (exposure, 0.12),
            (flicker_score, 0.18),
            (color_flicker_score, 0.12),
            (motion_score, 0.13),
            (cut_score, 0.10),
        ]
        if reference_similarity is not None:
            components.append((reference_similarity, 0.17))
        # The CLIP camera score remains diagnostic only: calibration showed that it can assign
        # low values to genuine footage. The vision supervisor carries the semantic weight.
        if semantic_judge is not None:
            components.append((semantic_minimum, 0.30))
        weight = sum(item[1] for item in components)
        score = sum(value * item_weight for value, item_weight in components) / weight

        checks = {
            "decodable": True,
            "sharp_enough": sharpness >= self.cfg.local_generation_min_sharpness,
            "exposure_safe": exposure >= 0.62,
            "no_brightness_flicker": flicker_score >= 0.62,
            "no_color_flash": color_flicker_score >= 0.58,
            "has_coherent_motion": motion_score >= 0.5,
            "no_hard_scene_cut": cut_score >= 0.65,
            "reference_preserved": (
                reference_similarity is None
                or reference_similarity >= self.cfg.local_generation_min_reference_similarity
            ),
            "semantic_realism": (
                semantic_judge is None
                or (
                    semantic_judge.get("verdict") == "pass"
                    and not bool(semantic_judge.get("critical_failure"))
                    and semantic_minimum >= self.cfg.local_generation_vlm_min_score
                )
            ),
            "overall_score": score >= self.cfg.local_generation_min_quality_score,
        }
        reasons = {
            "sharp_enough": "The representative frames are too soft for promotion.",
            "exposure_safe": "The clip contains excessive crushed or clipped luminance.",
            "no_brightness_flicker": "Brightness changes read as synthetic temporal flicker.",
            "no_color_flash": "A brief color cast or channel flash breaks temporal continuity.",
            "has_coherent_motion": "The clip is frozen or changes too abruptly between frames.",
            "no_hard_scene_cut": "A one-shot candidate contains an unexpected scene discontinuity.",
            "reference_preserved": "The generated first frame drifted too far from its real reference.",
            "semantic_realism": (
                "The contact-sheet supervisor found implausible physics, anatomy, continuity, or "
                "camera behavior."
            ),
            "overall_score": "The combined admission score is below the configured threshold.",
        }
        failed_reasons = [
            reasons[name] for name, passed in checks.items() if not passed and name in reasons
        ]
        return AIClipQualityReport(
            clip=clip,
            passed=all(checks.values()),
            score=round(float(score), 4),
            checks=checks,
            metrics={
                "duration_seconds": round(duration, 4),
                "sharpness": round(sharpness, 4),
                "exposure": round(exposure, 4),
                "flicker_score": round(flicker_score, 4),
                "color_flicker_score": round(color_flicker_score, 4),
                "color_delta": round(color_delta, 4),
                "motion_amount": round(motion, 4),
                "motion_score": round(motion_score, 4),
                "cut_score": round(cut_score, 4),
                "reference_similarity": (
                    round(reference_similarity, 4) if reference_similarity is not None else None
                ),
                "clip_camera_realism": round(realism, 4) if realism is not None else None,
            },
            reasons=failed_reasons,
            sampled_frames=len(arrays),
            semantic_judge=semantic_judge,
        )
