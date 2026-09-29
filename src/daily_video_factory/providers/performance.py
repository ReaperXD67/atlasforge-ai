from __future__ import annotations

import base64
import json
import math
import mimetypes
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image, ImageFilter, ImageOps
from pydantic import BaseModel, Field

from ..config import Settings
from ..exceptions import ProviderFailed
from ..media.ai_quality import SyntheticClipInspector
from ..media.ffmpeg import FFmpeg
from ..models import CostEntry, Scene


class LipSyncQualityReport(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=1)
    mouth_motion: float = Field(ge=0)
    audio_motion_correlation: float = Field(ge=-1, le=1)
    estimated_offset_seconds: float
    sampled_frames: int
    reasons: list[str]


class LipSyncInspector:
    """A no-credit preflight that compares mouth-region motion with the supplied vocal audio."""

    sample_fps = 12

    def __init__(self, ffmpeg: FFmpeg) -> None:
        self.ffmpeg = ffmpeg

    @staticmethod
    def _standardized(values: np.ndarray) -> np.ndarray:
        deviation = float(np.std(values))
        if deviation < 1e-7:
            return np.zeros_like(values)
        return (values - float(np.mean(values))) / deviation

    def inspect(self, clip: Path, audio: Path) -> LipSyncQualityReport:
        import librosa

        with tempfile.TemporaryDirectory(prefix="atlasforge-lipsync-") as temporary:
            pattern = Path(temporary) / "frame_%04d.jpg"
            self.ffmpeg.run(
                [
                    "-i",
                    str(clip),
                    "-vf",
                    f"fps={self.sample_fps},scale=256:144:flags=lanczos",
                    "-q:v",
                    "3",
                    str(pattern),
                ]
            )
            frames: list[np.ndarray] = []
            for path in sorted(Path(temporary).glob("frame_*.jpg")):
                with Image.open(path) as image:
                    frames.append(np.asarray(image.convert("L"), dtype=np.float32) / 255.0)
        if len(frames) < 12:
            return LipSyncQualityReport(
                passed=False,
                score=0,
                mouth_motion=0,
                audio_motion_correlation=0,
                estimated_offset_seconds=0,
                sampled_frames=len(frames),
                reasons=["Too few frames for a lip-sync timing proof."],
            )

        mouth_motion: list[float] = []
        upper_motion: list[float] = []
        for previous, current in zip(frames, frames[1:], strict=False):
            delta = np.abs(current - previous)
            mouth_motion.append(float(np.mean(delta[70:118, 76:180])))
            upper_motion.append(float(np.mean(delta[20:68, 64:192])))
        isolated = np.clip(
            np.asarray(mouth_motion) - np.asarray(upper_motion) * 0.55,
            0,
            None,
        )

        waveform, sample_rate = librosa.load(audio, sr=16_000, mono=True)
        hop = max(1, round(sample_rate / self.sample_fps))
        rms = librosa.feature.rms(y=waveform, frame_length=hop * 2, hop_length=hop)[0]
        if rms.size < 3:
            rms = np.zeros(len(isolated), dtype=np.float32)
        audio_curve = np.interp(
            np.linspace(0, max(0, rms.size - 1), len(isolated)),
            np.arange(rms.size),
            rms,
        ).astype(np.float32)
        mouth_curve = self._standardized(isolated)
        audio_curve = self._standardized(audio_curve)
        correlations: list[tuple[int, float]] = []
        for lag in range(-2, 3):
            if lag < 0:
                left, right = mouth_curve[-lag:], audio_curve[:lag]
            elif lag > 0:
                left, right = mouth_curve[:-lag], audio_curve[lag:]
            else:
                left, right = mouth_curve, audio_curve
            correlation = float(np.mean(left * right)) if left.size >= 6 else -1.0
            correlations.append((lag, correlation))
        best_lag, correlation = max(correlations, key=lambda item: item[1])
        motion = float(np.percentile(isolated, 75))
        offset = best_lag / self.sample_fps
        checks = {
            "visible_articulation": motion >= 0.006,
            "audio_reactive_mouth": correlation >= 0.08,
            "timing_close": abs(offset) <= 0.17,
        }
        reasons = {
            "visible_articulation": "The mouth region is too static to read as singing.",
            "audio_reactive_mouth": "Mouth motion does not follow the supplied vocal envelope.",
            "timing_close": "Estimated mouth timing is more than 170 ms from the audio.",
        }
        score = float(
            np.clip(
                0.45 * min(1.0, motion / 0.018)
                + 0.45 * np.clip((correlation + 0.05) / 0.45, 0, 1)
                + 0.10 * (1 - min(1.0, abs(offset) / 0.25)),
                0,
                1,
            )
        )
        return LipSyncQualityReport(
            passed=all(checks.values()),
            score=round(score, 4),
            mouth_motion=round(motion, 5),
            audio_motion_correlation=round(correlation, 4),
            estimated_offset_seconds=round(offset, 4),
            sampled_frames=len(frames),
            reasons=[reason for name, reason in reasons.items() if not checks[name]],
        )


class FalWanS2VProvider:
    """Audio-driven recurring-performer shots using the official Wan2.2-S2V model on fal."""

    name = "fal_wan_s2v"
    endpoint = "https://queue.fal.run/fal-ai/wan/v2.2-14b/speech-to-video"

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.video

    def available(self) -> bool:
        return bool(os.getenv("FAL_KEY"))

    @staticmethod
    def _data_uri(path: Path) -> str:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    @staticmethod
    def _full_body_plate(image: Image.Image, size: tuple[int, int]) -> Image.Image:
        background = ImageOps.fit(
            image.convert("RGB"), size, method=Image.Resampling.LANCZOS
        ).filter(ImageFilter.GaussianBlur(34))
        background = Image.blend(background, Image.new("RGB", size, "#07090c"), 0.72)
        subject = ImageOps.contain(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
        x = (size[0] - subject.width) // 2
        y = size[1] - subject.height
        background.paste(subject, (x, y))
        return background

    @staticmethod
    def _closeup_plate(image: Image.Image, size: tuple[int, int]) -> Image.Image:
        width, height = image.size
        upper = image.crop((0, 0, width, max(1, round(height * 0.62))))
        return ImageOps.fit(upper.convert("RGB"), size, method=Image.Resampling.LANCZOS)

    def _prepare_reference(self, scene: Scene, output: Path) -> Path:
        primary_path = scene.performer_reference
        if primary_path is None or not primary_path.is_file():
            raise ProviderFailed(f"Scene {scene.index} has no performer identity reference")
        size = (1280, 720)
        with Image.open(primary_path) as source:
            primary = source.convert("RGB")
            if scene.performance_action == "friend_gathering":
                plate = ImageOps.fit(primary, size, method=Image.Resampling.LANCZOS)
            elif scene.performance_action in {"lip_sync", "smoking_closeup"}:
                plate = self._closeup_plate(primary, size)
            else:
                plate = self._full_body_plate(primary, size)

        if scene.performer_role == "duet":
            secondary_path = scene.performer_reference_secondary
            if secondary_path is None or not secondary_path.is_file():
                raise ProviderFailed(f"Scene {scene.index} has no second duet identity reference")
            with Image.open(secondary_path) as source:
                secondary = self._full_body_plate(source.convert("RGB"), (640, 720))
            primary_half = ImageOps.fit(
                plate, (640, 720), method=Image.Resampling.LANCZOS
            )
            duet = Image.new("RGB", size, "#07090c")
            duet.paste(primary_half, (0, 0))
            duet.paste(secondary, (640, 0))
            plate = duet

        output.parent.mkdir(parents=True, exist_ok=True)
        plate.save(output, format="JPEG", quality=96, subsampling=0)
        return output

    def _frame_count(self, duration_seconds: float) -> int:
        fps = self.cfg.performance_frames_per_second
        requested = math.ceil(duration_seconds * fps / 4) * 4
        return max(40, min(120, requested))

    def estimated_cost(self, scene: Scene) -> float:
        frames = self._frame_count(scene.duration_seconds)
        seconds = frames / self.cfg.performance_frames_per_second
        return round(seconds * self.cfg.performance_estimated_usd_per_second, 4)

    def generate(self, scene: Scene, output: Path) -> Path:
        if not self.available():
            raise ProviderFailed("FAL_KEY is required for Wan2.2-S2V performer generation")
        if scene.performance_audio is None or not scene.performance_audio.is_file():
            raise ProviderFailed(f"Scene {scene.index} has no performance audio slice")

        reference = self._prepare_reference(
            scene, output.with_name(f"{output.stem}_reference.jpg")
        )
        request_body = {
            "prompt": scene.video_prompt,
            "negative_prompt": (
                "non-Malaysian casting, different identity, identity drift, face morphing, child, "
                "teenager, extra person, duplicate body, malformed hands, extra fingers, broken "
                "guitar, floating cigarette, warped car, text, subtitles, logo, watermark"
            ),
            "num_frames": self._frame_count(scene.duration_seconds),
            "frames_per_second": self.cfg.performance_frames_per_second,
            "resolution": self.cfg.performance_resolution,
            "num_inference_steps": self.cfg.performance_inference_steps,
            "enable_safety_checker": True,
            "enable_output_safety_checker": True,
            "guidance_scale": 3.5,
            "shift": 5,
            "video_quality": "maximum",
            "video_write_mode": "balanced",
            "image_url": self._data_uri(reference),
            "audio_url": self._data_uri(scene.performance_audio),
        }
        headers = {
            "Authorization": f"Key {os.environ['FAL_KEY']}",
            "Content-Type": "application/json",
        }
        timeout = self.cfg.performance_timeout_minutes * 60
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.post(self.endpoint, headers=headers, json=request_body)
            if response.status_code >= 400:
                raise ProviderFailed(f"Wan S2V submission failed: {response.text[:600]}")
            queued: dict[str, Any] = response.json()
            status_url = str(queued.get("status_url", ""))
            result_url = str(queued.get("response_url", ""))
            if not status_url or not result_url:
                raise ProviderFailed("Wan S2V queue returned no status/result URL")

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                status_response = client.get(status_url, headers=headers)
                status_response.raise_for_status()
                status_payload = status_response.json()
                status = str(status_payload.get("status", "")).upper()
                if status == "COMPLETED":
                    break
                if status in {"FAILED", "CANCELLED"}:
                    raise ProviderFailed(
                        f"Wan S2V generation {status.casefold()}: {status_payload}"
                    )
                time.sleep(5)
            else:
                raise ProviderFailed(
                    f"Wan S2V generation timed out after {self.cfg.performance_timeout_minutes}m"
                )

            result_response = client.get(result_url, headers=headers)
            result_response.raise_for_status()
            result = result_response.json()
            video_url = str(result.get("video", {}).get("url", ""))
            if not video_url:
                raise ProviderFailed("Wan S2V completed without a video URL")
            video_response = client.get(video_url)
            video_response.raise_for_status()

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(video_response.content)
        output.with_suffix(".license.json").write_text(
            json.dumps(
                {
                    "provider": "fal.ai",
                    "model": "fal-ai/wan/v2.2-14b/speech-to-video",
                    "synthetic_media": True,
                    "commercial_use": True,
                    "performer_role": scene.performer_role,
                    "performance_action": scene.performance_action,
                    "reference_image": str(scene.performer_reference),
                    "secondary_reference_image": str(scene.performer_reference_secondary)
                    if scene.performer_reference_secondary
                    else None,
                    "audio_slice": str(scene.performance_audio),
                    "prompt": scene.video_prompt,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return output


class PerformanceSceneScheduler:
    """Generate every directed performer scene or fail; never replace a lead with stock people."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cfg = settings.video
        self.provider = FalWanS2VProvider(settings)

    def generate(
        self, scenes: list[Scene], output_dir: Path
    ) -> tuple[dict[int, Path], list[CostEntry]]:
        required = [scene for scene in scenes if scene.performer_generation_required]
        if not required:
            return {}, []
        if not self.cfg.performance_generation_enabled:
            raise ProviderFailed(
                "The storyboard requires recurring performers but performer generation is disabled"
            )
        if self.cfg.performance_provider != self.provider.name or not self.provider.available():
            raise ProviderFailed(
                "Malaysian Duet requires FAL_KEY for the configured Wan2.2-S2V performer lane"
            )
        if len(required) > self.cfg.performance_max_scenes_per_video:
            raise ProviderFailed(
                f"Performer plan requested {len(required)} scenes; configured maximum is "
                f"{self.cfg.performance_max_scenes_per_video}"
            )

        projected = sum(self.provider.estimated_cost(scene) for scene in required)
        if projected > self.cfg.performance_daily_budget_usd + 1e-9:
            raise ProviderFailed(
                f"Performer plan estimates ${projected:.2f}, over the "
                f"${self.cfg.performance_daily_budget_usd:.2f} run budget"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = FFmpeg()
        inspector = SyntheticClipInspector(self.settings, ffmpeg)
        lip_sync_inspector = LipSyncInspector(ffmpeg)
        results: dict[int, Path] = {}
        costs: list[CostEntry] = []
        failures: list[str] = []
        identity_proofs: list[Scene] = []
        if self.cfg.performance_preflight_enabled:
            for role in ("male_lead", "female_lead"):
                match = next(
                    (
                        scene
                        for scene in required
                        if scene.performer_role == role and scene.performance_action == "lip_sync"
                    ),
                    None,
                )
                if match is None:
                    match = next(
                        (scene for scene in required if scene.performer_role == role),
                        None,
                    )
                if match is not None:
                    identity_proofs.append(match)
        proof_ids = {scene.index for scene in identity_proofs}
        ordered = [
            *identity_proofs,
            *sorted(
                (scene for scene in required if scene.index not in proof_ids),
                key=lambda scene: scene.start_seconds,
            ),
        ]
        for scene in ordered:
            output = output_dir / f"scene_{scene.index:03d}_{self.provider.name}.mp4"
            try:
                generated = self.provider.generate(scene, output)
                if self.cfg.performance_quality_gate:
                    prepared_reference = output.with_name(f"{output.stem}_reference.jpg")
                    report = inspector.inspect(
                        generated,
                        reference=(
                            prepared_reference
                            if prepared_reference.is_file()
                            else scene.performer_reference
                        ),
                        prompt=scene.video_prompt,
                    )
                    output.with_suffix(".quality.json").write_text(
                        report.model_dump_json(indent=2), encoding="utf-8"
                    )
                    if not report.passed:
                        failures.append(
                            f"scene {scene.index} failed performer QC: {', '.join(report.reasons)}"
                        )
                        if scene.index in proof_ids:
                            raise ProviderFailed(
                                "Identity proof failed before full generation: "
                                + ", ".join(report.reasons)
                            )
                        continue
                if scene.performance_action == "lip_sync" and scene.performance_audio:
                    lip_sync_report = lip_sync_inspector.inspect(
                        generated,
                        scene.performance_audio,
                    )
                    output.with_suffix(".lipsync.json").write_text(
                        lip_sync_report.model_dump_json(indent=2), encoding="utf-8"
                    )
                    if not lip_sync_report.passed:
                        failures.append(
                            f"scene {scene.index} failed lip-sync QC: "
                            f"{', '.join(lip_sync_report.reasons)}"
                        )
                        if scene.index in proof_ids:
                            raise ProviderFailed(
                                "Lip-sync proof failed before full generation: "
                                + ", ".join(lip_sync_report.reasons)
                            )
                        continue
                scene.selected_video_provider = self.provider.name
                results[scene.index] = generated
                costs.append(
                    CostEntry(
                        stage="performer_video",
                        provider=self.provider.name,
                        estimated_usd=self.provider.estimated_cost(scene),
                        note=(
                            f"{scene.performer_role}/{scene.performance_action} scene {scene.index}"
                        ),
                    )
                )
            except Exception as exc:
                failures.append(f"scene {scene.index}: {type(exc).__name__}: {exc}")
                if scene.index in proof_ids:
                    raise ProviderFailed(
                        "Performer preflight stopped the job before remaining paid shots. "
                        f"Scene {scene.index}: {exc}"
                    ) from exc

        missing = [scene.index for scene in required if scene.index not in results]
        if missing and self.cfg.performance_require_all_scenes:
            raise ProviderFailed(
                "Recurring-performer generation failed closed; no stock-person fallback. "
                + " | ".join(failures[:6])
            )
        return results, costs
