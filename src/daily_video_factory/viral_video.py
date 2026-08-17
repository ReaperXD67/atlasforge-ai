from __future__ import annotations

import shutil
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .artifacts import RunPaths
from .config import Settings
from .exceptions import ConfigurationError
from .media.ai_quality import AIClipQualityReport, SyntheticClipInspector
from .media.ffmpeg import FFmpeg
from .media.render import VideoRenderer
from .models import CostEntry, RunManifest, RunStatus, Scene, StageStatus, Storyboard
from .music_video import analyze_music
from .providers.text import OpenRouterTextProvider
from .providers.video import (
    ComfyUISDXLReferenceProvider,
    ComfyUIWan22Provider,
    GeminiOmniVideoProvider,
    PexelsReferenceImageProvider,
    PremiumVideoProvider,
    VeoVideoProvider,
)
from .state import RunStore

ViralRecipe = Literal["cinematic_insert", "beat_creature", "talking_duo", "physics_spectacle"]
ViralProvider = Literal["local_wan", "gemini_omni", "veo"]


class ViralPromptDirection(BaseModel):
    reference_query: str = Field(min_length=3, max_length=100)
    motion_direction: str = Field(min_length=12, max_length=500)
    camera_direction: str = Field(min_length=8, max_length=240)
    realism_risks: list[str] = Field(min_length=2, max_length=6)


def fallback_prompt_direction(recipe: ViralRecipe, concept: str) -> ViralPromptDirection:
    if recipe == "physics_spectacle":
        return ViralPromptDirection(
            reference_query="generic brutalist concrete parking structure wide exterior",
            motion_direction=(
                "Begin completely still, introduce one localized brittle fracture, then let rigid "
                "slabs fall under gravity with one primary impact and settling dust."
            ),
            camera_direction="Locked wide tripod frame at human eye level with no artificial shake.",
            realism_risks=["rubbery concrete", "miniature scale", "uniform dust cloud"],
        )
    if recipe == "beat_creature":
        subject = " ".join(concept.split()[:10])
        return ViralPromptDirection(
            reference_query=f"{subject} full body real photograph"[:100].rstrip(),
            motion_direction=(
                "Use two simple grounded dance poses with visible weight transfer and preserve the "
                "head, eyes, paws, fur pattern, and floor contact throughout."
            ),
            camera_direction="Low locked medium-wide camera; no orbit, whip pan, or zoom.",
            realism_risks=["sliding feet", "changing fur pattern", "extra limbs"],
        )
    if recipe == "talking_duo":
        return ViralPromptDirection(
            reference_query="two expressive fictional characters natural portrait",
            motion_direction=(
                "Keep gestures small, preserve eye lines, and move only the active speaker."
            ),
            camera_direction="Locked conversational two-shot with natural portrait lens perspective.",
            realism_risks=["face drift", "simultaneous lip movement", "waxy skin"],
        )
    subject = " ".join(concept.split()[:12])
    return ViralPromptDirection(
        reference_query=f"{subject} real cinematic photograph"[:100].rstrip(),
        motion_direction=(
            "Use one slow physically plausible subject or environmental action, preserve every "
            "material and reflection, and finish in a stable hero composition. A rigid subject "
            "may remain completely stationary while rain, steam, fabric, or practical light moves."
        ),
        camera_direction="Locked tripod or one subtle straight dolly move; no orbit or shake.",
        realism_risks=["morphing geometry", "changing reflections", "floating contact points"],
    )


def compile_viral_prompt(
    recipe: ViralRecipe,
    concept: str,
    *,
    seconds: float,
    bpm: float | None = None,
    dialogue_a: str = "",
    dialogue_b: str = "",
) -> str:
    """Compile a one-shot prompt that prioritizes temporal consistency over spectacle count."""
    concept = " ".join(concept.split()).strip()
    if not concept:
        raise ConfigurationError("Describe the action and visual world for this viral short")
    shared = (
        f"Create one continuous {seconds:g}-second photoreal cinematic shot in vertical 9:16. "
        "Keep the same subjects, wardrobe, anatomy, scale, lighting direction, and environment "
        "from first frame to last. Use physically plausible motion, natural motion blur, coherent "
        "reflections, stable facial features, and a deliberately controlled camera. No cuts, no "
        "morphing, no duplicated limbs, no text, no subtitles, no logos, no watermark. "
    )
    if recipe == "beat_creature":
        rhythm = (
            f"Choreograph major poses exactly on a {bpm:.1f} BPM pulse, with a clear accent every "
            "four beats. "
            if bpm
            else "Choreograph the performance with clear, evenly spaced musical accents. "
        )
        return (
            shared
            + rhythm
            + "The animal or character performs intentional dance movement while its paws, feet, "
            "fur, eyes, and contact with the ground remain anatomically stable. Preserve the exact "
            "identity from the reference image. End on a clean loopable hero pose. Concept: "
            + concept
        )
    if recipe == "talking_duo":
        if not dialogue_a.strip() or not dialogue_b.strip():
            raise ConfigurationError("Talking Duo needs one short line for each speaker")
        return (
            shared
            + "Two clearly distinct fictional characters have a natural conversation. Only the "
            "active speaker moves their lips; preserve eye lines, micro-expressions, breath, room "
            "tone, voice identity, and exact phoneme-level lip synchronization. Use warm, natural, "
            'age-appropriate voices and never imitate a real person. Speaker A says exactly: "'
            + dialogue_a.strip()
            + '". Speaker B replies exactly: "'
            + dialogue_b.strip()
            + '". Concept: '
            + concept
        )
    if recipe == "physics_spectacle":
        return (
            shared
            + "Show a completely fictional, unoccupied structure undergoing a physically credible "
            "cinematic structural failure. The large reinforced-concrete slabs stay rigid until brittle "
            "fracture; they crack, shear, and fall under gravity and never bend, stretch, melt, or behave "
            "like rubber or a miniature. Establish cause and effect, believable mass, inertia, dust, "
            "debris scale, air displacement, and environmental response. No people, animals, injuries, "
            "real landmarks, emergency branding, news graphics, or implication of a real disaster. "
            "Include synchronized structural creaks, impact transients, debris detail, and low-frequency "
            "rumble when native audio is available. Concept: " + concept
        )
    return (
        shared
        + "Create a restrained reference-led cinematic insert with one subject and one simple "
        "subject or environmental action. The primary rigid subject may remain stationary while "
        "rain, steam, fabric, or practical light moves. "
        "Preserve exact bodywork, product geometry, materials, labels, reflections, wheel or ground "
        "contact, and background layout. Prefer a locked camera or a subtle straight dolly. Avoid "
        "spectacle, rapid acceleration, crowds, complex interactions, or transformations. Concept: "
        + concept
    )


def compile_reference_prompt(recipe: ViralRecipe, concept: str) -> str:
    """Describe a clean pre-action plate that gives Wan stable geometry and identity."""
    concept = " ".join(concept.split()).strip()
    shared = (
        "A genuinely photoreal editorial photograph captured on a full-frame cinema camera, "
        "vertical 9:16 composition, natural material micro-texture, realistic skin or surface "
        "detail, physically correct reflections, plausible scale, straight geometry, sharp "
        "primary subject, subtle depth of field, motivated practical lighting, restrained color "
        "science, no motion blur. This is the clean first frame immediately before the action. "
    )
    if recipe == "beat_creature":
        direction = (
            "Show one complete animal or fictional character in a balanced pre-dance hero pose, "
            "both feet or paws visibly grounded, anatomically correct limbs, symmetrical eyes, "
            "detailed fur or skin, enough negative space for movement. "
        )
    elif recipe == "physics_spectacle":
        direction = (
            "Show the intact unoccupied fictional structure before any failure, in a wide view "
            "with unambiguous foundations, rigid concrete and steel, straight load-bearing members, "
            "realistic surrounding scale cues, and no people, damage, dust, smoke, or debris yet. "
        )
    elif recipe == "talking_duo":
        direction = (
            "Show two distinct fictional characters in a calm conversational two-shot with clean "
            "facial anatomy, consistent eye lines, and natural expressions before either speaks. "
        )
    else:
        direction = (
            "Show one clearly framed real-world subject before it moves, with exact rigid geometry, "
            "physically correct contact and reflections, and generous negative space for one subtle "
            "action. Avoid people unless they are essential to the stated concept. "
        )
    return shared + direction + "Visual concept: " + concept


class ViralShortPipeline:
    """Render one coherent AI-native shot, then master it for social delivery."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ffmpeg = FFmpeg()
        self.store = RunStore(settings.output_directory.resolve())

    def _stage(self, manifest: RunManifest, name: str, operation):
        manifest.current_stage = name
        self.store.stage(manifest.run_id, name, StageStatus.running)
        self.store.save_manifest(manifest)
        try:
            result = operation()
        except Exception as exc:
            self.store.stage(manifest.run_id, name, StageStatus.failed, str(exc))
            manifest.status = RunStatus.failed
            manifest.errors.append(f"{name}: {exc}")
            self.store.save_manifest(manifest)
            raise
        self.store.stage(manifest.run_id, name, StageStatus.completed)
        self.store.save_manifest(manifest)
        return result

    def _provider(self, name: ViralProvider) -> ComfyUIWan22Provider | PremiumVideoProvider:
        if name == "local_wan":
            return ComfyUIWan22Provider(self.settings)
        if name == "gemini_omni":
            return GeminiOmniVideoProvider(self.settings)
        return VeoVideoProvider(self.settings)

    def _prompt_direction(
        self, recipe: ViralRecipe, concept: str, seconds: float
    ) -> tuple[ViralPromptDirection, str]:
        fallback = fallback_prompt_direction(recipe, concept)
        provider = OpenRouterTextProvider(self.settings.script.openrouter_model, timeout_seconds=90)
        if not provider.available():
            return fallback, "deterministic"
        try:
            payload = provider.generate_json(
                system=(
                    "You are a conservative cinematographer directing an image-to-video model. "
                    "Reduce the action to one physically plausible beat. Do not add objects, cuts, "
                    "camera tricks, text, brands, celebrities, or unsafe real-event framing. The "
                    "reference query must describe a static real photograph before the action and "
                    "contain only concrete searchable nouns/adjectives."
                ),
                prompt=(
                    f"Recipe: {recipe}\nDuration: {seconds:g} seconds\nConcept: {concept}\n\n"
                    "Return the most conservative direction that can look like camera footage on "
                    "a small local model. Prefer one subject, one action, one camera move."
                ),
                schema=ViralPromptDirection.model_json_schema(),
                temperature=0.25,
            )
            directed = ViralPromptDirection.model_validate(payload)
            # The language model may be useful at simplifying the motion, but free-form camera
            # ideas and negative lists often make a small video model solve more variables. Keep
            # those deterministic, and keep the physics reference search generic/non-landmark.
            directed.camera_direction = fallback.camera_direction
            directed.realism_risks = fallback.realism_risks
            if recipe == "physics_spectacle":
                directed.reference_query = fallback.reference_query
            return directed, "openrouter"
        except Exception:
            return fallback, "deterministic_fallback"

    def _procedural_impact(self, duration: float, output: Path) -> Path:
        """Create a timed, publish-loud local impact when a physics clip has no source audio."""
        impact_at = max(0.4, duration * 0.36)
        rumble_fade = max(0.1, duration - 0.8)
        delay_ms = round(impact_at * 1000)
        self.ffmpeg.run(
            [
                "-f",
                "lavfi",
                "-i",
                f"anoisesrc=color=brown:amplitude=0.16:sample_rate=48000:duration={duration:.3f}",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=58:sample_rate=48000:duration=0.9",
                "-f",
                "lavfi",
                "-i",
                "anoisesrc=color=white:amplitude=0.12:sample_rate=48000:duration=0.45",
                "-filter_complex",
                (
                    f"[0:a]lowpass=f=240,highpass=f=28,volume=0.7,"
                    f"afade=t=in:st={max(0, impact_at - 0.35):.3f}:d=0.35,"
                    f"afade=t=out:st={rumble_fade:.3f}:d=0.8[debris];"
                    f"[1:a]volume=0.9,afade=t=out:st=0.06:d=0.84,"
                    f"adelay={delay_ms}:all=1[impact];"
                    f"[2:a]highpass=f=900,lowpass=f=6500,volume=0.32,"
                    "afade=t=out:st=0.04:d=0.41,haas=side_gain=0.7,"
                    f"adelay={max(0, delay_ms - 25)}:all=1[crack];"
                    "[debris][impact][crack]amix=inputs=3:normalize=0,alimiter=limit=0.92,"
                    # Short-form physics beds contain intentional pre-impact silence, so the
                    # event itself is mastered hotter to land near -16 LUFS over the whole clip.
                    "loudnorm=I=-13:TP=-1.0:LRA=7,volume=2dB,alimiter=limit=0.84,"
                    "aformat=sample_fmts=fltp:channel_layouts=stereo[a]"
                ),
                "-map",
                "[a]",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-ac",
                "2",
                str(output),
            ]
        )
        return output

    def run(
        self,
        *,
        recipe: ViralRecipe,
        concept: str,
        provider_name: ViralProvider = "local_wan",
        seconds: float = 5,
        reference_image: Path | None = None,
        master_music: Path | None = None,
        dialogue_a: str = "",
        dialogue_b: str = "",
        candidate_count: int | None = None,
    ) -> RunManifest:
        self.ffmpeg.require()
        if not 3 <= seconds <= 10:
            raise ConfigurationError("Viral shorts must be between 3 and 10 seconds")
        if recipe == "talking_duo" and provider_name == "local_wan":
            raise ConfigurationError(
                "Talking Duo needs Gemini Omni or Veo native audio; Wan 5B cannot provide honest lip sync"
            )
        if recipe == "talking_duo" and (not dialogue_a.strip() or not dialogue_b.strip()):
            raise ConfigurationError("Talking Duo needs one short line for each speaker")
        if recipe == "beat_creature" and master_music is None:
            raise ConfigurationError(
                "Beat Creature needs a master music track for real beat timing"
            )
        if not concept.strip():
            raise ConfigurationError("Describe the action and visual world for this viral short")
        reference = reference_image.resolve() if reference_image else None
        reference_origin = "uploaded" if reference is not None else None
        music = master_music.resolve() if master_music else None
        if reference is not None and not reference.is_file():
            raise FileNotFoundError(reference)
        if music is not None and not music.is_file():
            raise FileNotFoundError(music)
        # Keep the CLI and Studio on the same vertical quality contract. A direct
        # `viral-film` invocation must never fall back to the landscape daily-video defaults.
        self.settings.video.width = 1080
        self.settings.video.height = 1920
        self.settings.video.fps = 60
        if provider_name == "local_wan":
            if self.settings.video.comfyui_height <= self.settings.video.comfyui_width:
                self.settings.video.comfyui_width = 576
                self.settings.video.comfyui_height = 1024
            else:
                self.settings.video.comfyui_width = min(
                    640, max(576, self.settings.video.comfyui_width)
                )
                self.settings.video.comfyui_height = min(
                    1136, max(1024, self.settings.video.comfyui_height)
                )
            self.settings.video.comfyui_frames = min(
                241, max(17, 4 * round(seconds * self.settings.video.comfyui_fps / 4) + 1)
            )
            self.settings.video.comfyui_steps = max(28, self.settings.video.comfyui_steps)
            self.settings.video.comfyui_rife_enabled = True
            self.settings.video.interpolate_low_fps_clips = False
        provider = self._provider(provider_name)
        if not provider.available():
            requirement = (
                "a running ComfyUI Wan 2.2 service"
                if provider_name == "local_wan"
                else "GOOGLE_API_KEY and the google optional dependency"
            )
            raise ConfigurationError(f"{provider_name} is not ready; it needs {requirement}")
        reference_provider = None
        real_reference_provider = None
        if provider_name == "local_wan" and reference is None:
            reference_provider = ComfyUISDXLReferenceProvider(self.settings)
            real_reference_provider = PexelsReferenceImageProvider(self.settings)
            if not reference_provider.available() and not real_reference_provider.available():
                raise ConfigurationError(
                    "No automatic reference source is ready. Add PEXELS_API_KEY or run "
                    ".\\scripts\\install_comfyui_wan22.ps1 once, then restart Studio."
                )
        renderer = VideoRenderer(self.settings, self.ffmpeg)

        publication_date = date.today()
        run_id = f"viral-{publication_date.isoformat()}-{uuid.uuid4().hex[:8]}"
        paths = RunPaths.create(self.settings.output_directory.resolve(), publication_date, run_id)
        manifest = RunManifest(
            run_id=run_id,
            publication_date=publication_date,
            status=RunStatus.running,
            pipeline_kind="viral_short",
            topic=concept,
            output_root=paths.root,
        )
        self.store.save_manifest(manifest)
        generation_seed = int(run_id.rsplit("-", 1)[1], 16)

        direction, direction_provider = self._stage(
            manifest,
            "prompt_direction",
            lambda: self._prompt_direction(recipe, concept, seconds),
        )
        paths.write_json("metadata/prompt_direction.json", direction)
        if direction_provider == "openrouter":
            manifest.costs.append(
                CostEntry(
                    stage="prompt_direction",
                    provider="openrouter",
                    estimated_usd=0.002,
                    note="Conservative image-to-video prompt extension estimate",
                )
            )

        beat_map = None
        if music is not None:
            beat_map = self._stage(
                manifest, "beat_analysis", lambda: analyze_music(music, self.ffmpeg)
            )
            paths.write_json("music/audiomap.json", beat_map)
            shutil.copy2(music, paths.music / f"master{music.suffix.lower()}")

        if reference is not None:
            source_reference = reference
            staged_reference = paths.scenes / f"reference{reference.suffix.lower()}"
            shutil.copy2(reference, staged_reference)
            source_license = source_reference.with_suffix(".license.json")
            if source_license.is_file():
                shutil.copy2(source_license, staged_reference.with_suffix(".license.json"))
            reference = staged_reference
        elif provider_name == "local_wan":
            assert reference_provider is not None and real_reference_provider is not None

            def choose_reference() -> tuple[Path, str]:
                if (
                    self.settings.video.local_generation_reference_policy == "real_first"
                    and real_reference_provider.available()
                ):
                    try:
                        return (
                            real_reference_provider.generate(
                                direction.reference_query,
                                paths.scenes / "real_reference.jpg",
                            ),
                            real_reference_provider.name,
                        )
                    except Exception as exc:
                        manifest.warnings.append(f"Real reference search fell back to SDXL: {exc}")
                if not reference_provider.available():
                    raise ConfigurationError(
                        "Pexels could not supply a suitable real reference and SDXL is unavailable."
                    )
                return (
                    reference_provider.generate(
                        compile_reference_prompt(recipe, concept),
                        paths.scenes / "synthetic_reference.png",
                        seed=generation_seed,
                    ),
                    reference_provider.name,
                )

            reference, reference_origin = self._stage(
                manifest,
                "reference_generation",
                choose_reference,
            )
            manifest.costs.append(
                CostEntry(
                    stage="reference_image",
                    provider=reference_origin,
                    estimated_usd=0,
                    note=(
                        "Licensed real photographic plate"
                        if reference_origin == real_reference_provider.name
                        else "Local SDXL fallback identity/geometry plate; electricity only"
                    ),
                )
            )

        prompt = compile_viral_prompt(
            recipe,
            concept,
            seconds=seconds,
            bpm=beat_map.bpm if beat_map else None,
            dialogue_a=dialogue_a,
            dialogue_b=dialogue_b,
        )
        prompt += (
            f" Shot direction: {direction.motion_direction} Camera: "
            f"{direction.camera_direction} Explicitly avoid: "
            + ", ".join(direction.realism_risks)
            + "."
        )
        task: Literal["text_to_video", "image_to_video", "reference_to_video"] = (
            "reference_to_video"
            if provider_name == "gemini_omni" and reference is not None
            else "image_to_video"
            if reference is not None
            else "text_to_video"
        )
        scene = Scene(
            index=1,
            duration_seconds=seconds,
            narration="",
            camera_angle="controlled cinematic vertical camera",
            environment="photoreal social-video set",
            character_description="consistent fictional subject",
            emotion="authentic and spontaneous",
            lighting="motivated cinematic practical lighting",
            sound_effects=["native synchronized audio"],
            transition="none",
            video_prompt=prompt,
            visual_search_query=concept,
            visual_exclusion_terms=["morphing", "jitter", "watermark", "real disaster"],
            visual_mode="local_ai_candidate" if provider_name == "local_wan" else "premium_ai",
            premium_score=1,
            selected_video_provider=(
                "comfyui_wan22" if provider_name == "local_wan" else provider_name
            ),
            aspect_ratio="9:16",
            reference_image=reference,
            generation_seed=generation_seed,
            generation_task=task,
            ai_generation_required=True,
            ai_generation_reason="Explicit isolated AI Lab request for an impossible or synthetic shot.",
        )
        storyboard = Storyboard(
            title=concept[:100],
            total_duration_seconds=seconds,
            scenes=[scene],
            provider="viral-prompt-contract-v1",
        )
        paths.write_json("storyboards/storyboard_timed.json", storyboard)
        paths.write_json(
            "metadata/provenance.json",
            {
                "contains_synthetic_media": True,
                "recipe": recipe,
                "provider": provider_name,
                "reference_image": str(reference) if reference else None,
                "reference_origin": reference_origin,
                "reference_policy": self.settings.video.local_generation_reference_policy,
                "master_music": str(music) if music else None,
                "auto_insert_into_editorial": False,
                "quality_report": "quality/ai_clip_report.json"
                if provider_name == "local_wan"
                else None,
                "publishing_enabled": False,
                "safety": "fictional content; do not present as news or documentary evidence",
            },
        )

        raw = paths.videos / f"raw_{provider.name}.mp4"
        admission: dict[str, object] | None = None
        if provider_name == "local_wan":
            requested_candidates = max(
                1,
                min(
                    3,
                    candidate_count
                    if candidate_count is not None
                    else self.settings.video.local_generation_candidates,
                ),
            )
            inspector = SyntheticClipInspector(self.settings, self.ffmpeg)

            def generate_candidates() -> tuple[Path, dict[str, object], int]:
                reports: list[AIClipQualityReport] = []
                candidate_paths: list[Path] = []
                candidate_seeds: list[int] = []
                candidate_dir = paths.videos / "candidates"
                candidate_dir.mkdir(parents=True, exist_ok=True)
                for candidate_index in range(requested_candidates):
                    seed = (generation_seed + candidate_index * 1_000_003) % (2**63 - 1)
                    candidate_scene = scene.model_copy(deep=True, update={"generation_seed": seed})
                    candidate_path = (
                        candidate_dir / f"candidate_{candidate_index + 1:02d}_{seed}.mp4"
                    )
                    provider.generate(candidate_scene, candidate_path)
                    if self.settings.video.local_generation_quality_gate:
                        report = inspector.inspect(
                            candidate_path,
                            reference=reference,
                            prompt=candidate_scene.video_prompt,
                        )
                    else:
                        report = AIClipQualityReport(
                            clip=candidate_path,
                            passed=True,
                            score=1,
                            checks={"quality_gate_disabled": True},
                            metrics={},
                            reasons=[],
                            sampled_frames=0,
                        )
                    reports.append(report)
                    candidate_paths.append(candidate_path)
                    candidate_seeds.append(seed)
                selected_index = max(
                    range(len(reports)),
                    key=lambda index: (reports[index].passed, reports[index].score),
                )
                selected_report = reports[selected_index]
                selected_path = candidate_paths[selected_index]
                shutil.copy2(selected_path, raw)
                selected_license = selected_path.with_suffix(".license.json")
                if selected_license.exists():
                    shutil.copy2(selected_license, raw.with_suffix(".license.json"))
                decision = "accepted" if selected_report.passed else "quarantined"
                aggregate: dict[str, object] = {
                    "decision": decision,
                    "auto_insert_into_editorial": False,
                    "selected_candidate": selected_index + 1,
                    "selected_seed": candidate_seeds[selected_index],
                    "selected_score": selected_report.score,
                    "policy": (
                        "AI Lab candidates are isolated. Editorial insertion requires this gate "
                        "to pass and a real-footage search to fail first."
                    ),
                    "candidates": [report.model_dump(mode="json") for report in reports],
                }
                return raw, aggregate, candidate_seeds[selected_index]

            raw, admission, selected_seed = self._stage(
                manifest, "ai_generation", generate_candidates
            )
            scene.generation_seed = selected_seed
            paths.write_json("quality/ai_clip_report.json", admission)
            paths.write_json("storyboards/storyboard_timed.json", storyboard)
            if admission["decision"] == "quarantined":
                manifest.warnings.append(
                    "The best local candidate did not pass the realism gate and remains quarantined."
                )
        else:
            self._stage(manifest, "ai_generation", lambda: provider.generate(scene, raw))
        if isinstance(provider, PremiumVideoProvider):
            manifest.costs.append(
                CostEntry(
                    stage="video",
                    provider=provider.name,
                    estimated_usd=provider.estimated_cost_usd,
                    note=f"{seconds:g}s native video estimate",
                )
            )
        else:
            manifest.costs.append(
                CostEntry(
                    stage="video",
                    provider=provider.name,
                    estimated_usd=0,
                    note=(f"Best-of-{requested_candidates} local GPU candidates; electricity only"),
                )
            )

        silent = paths.videos / "vertical_60fps_silent.mp4"
        self._stage(
            manifest,
            "vertical_master",
            lambda: renderer.normalize_video_scene(scene, raw, silent, duration_seconds=seconds),
        )

        final = paths.final / "video.mp4"

        def mux_audio() -> Path:
            if music is not None:
                audio_input = music
            elif provider_name != "local_wan":
                audio_input = raw
            elif recipe == "physics_spectacle":
                audio_input = self._procedural_impact(seconds, paths.audio / "impact.m4a")
            else:
                shutil.copy2(silent, final)
                return final
            self.ffmpeg.run(
                [
                    "-i",
                    str(silent),
                    "-i",
                    str(audio_input),
                    "-t",
                    f"{seconds:.3f}",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0?",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "320k",
                    "-af",
                    "aresample=48000,alimiter=limit=0.98",
                    "-movflags",
                    "+faststart",
                    str(final),
                ]
            )
            return final

        self._stage(manifest, "audio_master", mux_audio)
        thumbnail = paths.thumbnails / "viral-poster.jpg"

        def make_thumbnail() -> Path:
            self.ffmpeg.run(
                [
                    "-ss",
                    f"{min(0.4, seconds / 4):.3f}",
                    "-i",
                    str(final),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(thumbnail),
                ]
            )
            return thumbnail

        self._stage(manifest, "thumbnail", make_thumbnail)
        scene_images = [{"scene": 1, "role": "poster", "path": str(thumbnail)}]
        if reference is not None:
            scene_images.insert(
                0,
                {
                    "scene": 1,
                    "role": "generation_reference",
                    "origin": reference_origin,
                    "path": str(reference),
                },
            )
        paths.write_json("scenes/images.json", scene_images)
        manifest.final_video = final
        manifest.thumbnail = thumbnail
        manifest.status = RunStatus.ready
        manifest.current_stage = "complete"
        manifest.finished_at = datetime.now(UTC)
        self.store.save_manifest(manifest)
        paths.write_json("manifest.json", manifest)
        return manifest
