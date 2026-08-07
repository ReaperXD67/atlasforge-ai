from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .artifacts import RunPaths
from .config import Settings
from .logging import configure_logging, get_logger
from .media.audio import generate_original_music, generate_sfx_track, mix_audio
from .media.ffmpeg import FFmpeg
from .media.render import VideoRenderer
from .media.subtitles import write_subtitles
from .metadata import build_metadata, build_thumbnail
from .models import (
    CostEntry,
    ResearchReport,
    RunManifest,
    RunStatus,
    ScriptDocument,
    StageStatus,
    Storyboard,
    VideoMetadata,
)
from .providers.images import SceneImageGenerator
from .providers.tts import NarrationGenerator
from .providers.video import PremiumSceneScheduler
from .publishing.youtube import YouTubePublisher
from .quality import validate_final, validate_script
from .research import TopicResearcher
from .script import ScriptGenerator
from .state import RunStore
from .storyboard import StoryboardBuilder

T = TypeVar("T")


class DailyVideoPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.output_root = settings.output_directory.resolve()
        self.store = RunStore(self.output_root)
        self.ffmpeg = FFmpeg()
        self.log = get_logger(component="pipeline")

    def _save_manifest(self, manifest: RunManifest, paths: RunPaths) -> None:
        self.store.save_manifest(manifest)
        paths.write_json("manifest.json", manifest)

    @staticmethod
    def _record_cost(manifest: RunManifest, entry: CostEntry) -> None:
        if not any(
            existing.stage == entry.stage and existing.provider == entry.provider
            for existing in manifest.costs
        ):
            manifest.costs.append(entry)

    def _execute(
        self,
        name: str,
        manifest: RunManifest,
        paths: RunPaths,
        operation: Callable[[], T],
    ) -> T:
        manifest.current_stage = name
        self.store.stage(manifest.run_id, name, StageStatus.running)
        self._save_manifest(manifest, paths)
        self.log.info("stage_started", run_id=manifest.run_id, stage=name)
        try:
            result = operation()
        except Exception as exc:
            self.store.stage(manifest.run_id, name, StageStatus.failed, str(exc))
            manifest.errors.append(f"{name}: {exc}")
            manifest.status = RunStatus.failed
            self._save_manifest(manifest, paths)
            self.log.exception("stage_failed", run_id=manifest.run_id, stage=name)
            raise
        self.store.stage(manifest.run_id, name, StageStatus.completed)
        self._save_manifest(manifest, paths)
        self.log.info("stage_completed", run_id=manifest.run_id, stage=name)
        return result

    def _load_or_execute_model(
        self,
        name: str,
        artifact: Path,
        model: type[T],
        manifest: RunManifest,
        paths: RunPaths,
        operation: Callable[[], T],
        resume: bool,
    ) -> T:
        if (
            resume
            and self.store.stage_completed(manifest.run_id, name)
            and artifact.exists()
            and isinstance(model, type)
            and issubclass(model, BaseModel)
        ):
            return model.model_validate_json(artifact.read_text(encoding="utf-8"))
        return self._execute(name, manifest, paths, operation)

    @staticmethod
    def _retime_storyboard(storyboard: Storyboard, audio_duration: float) -> Storyboard:
        if storyboard.total_duration_seconds <= 0:
            return storyboard
        factor = audio_duration / storyboard.total_duration_seconds
        for scene in storyboard.scenes:
            scene.duration_seconds = round(scene.duration_seconds * factor, 3)
        storyboard.total_duration_seconds = round(sum(s.duration_seconds for s in storyboard.scenes), 3)
        return storyboard

    def run(
        self,
        publication_date: date,
        *,
        topic_override: str | None = None,
        resume: bool = True,
        upload: bool | None = None,
    ) -> RunManifest:
        self.ffmpeg.require()
        with self.store.exclusive(timeout_seconds=2):
            self.store.assert_not_published(publication_date)
            existing = self.store.latest_resumable(publication_date) if resume else None
            if existing:
                manifest = existing
                paths = RunPaths.from_root(manifest.output_root)
            else:
                run_id = f"{publication_date.isoformat()}-{uuid.uuid4().hex[:8]}"
                paths = RunPaths.create(self.output_root, publication_date, run_id)
                configure_logging(paths.logs / "pipeline.jsonl")
                manifest = RunManifest(
                    run_id=run_id,
                    publication_date=publication_date,
                    status=RunStatus.running,
                    output_root=paths.root,
                )
                self._save_manifest(manifest, paths)
            configure_logging(paths.logs / "pipeline.jsonl")
            manifest.status = RunStatus.running
            try:
                research_file = paths.research / "research.json"

                def research_operation() -> ResearchReport:
                    report = TopicResearcher(self.settings).run(publication_date)
                    if topic_override:
                        report.selected_title = topic_override
                        report.selected_angle = (
                            f"Create an education-first, skeptical beginner guide about '{topic_override}', "
                            "using Atomy only as a neutral optional example."
                        )
                    paths.write_json("research/research.json", report)
                    return report

                research = self._load_or_execute_model(
                    "research", research_file, ResearchReport, manifest, paths, research_operation, resume
                )
                manifest.topic = research.selected_title

                script_file = paths.scripts / "script.json"

                def script_operation() -> ScriptDocument:
                    script = ScriptGenerator(self.settings).run(research)
                    paths.write_json("scripts/script.json", script)
                    paths.write_text("scripts/narration.txt", script.full_text)
                    validate_script(script, self.settings)
                    return script

                script = self._load_or_execute_model(
                    "script", script_file, ScriptDocument, manifest, paths, script_operation, resume
                )
                self._record_cost(
                    manifest,
                    CostEntry(
                        stage="script",
                        provider=script.provider,
                        estimated_usd={"gemini": 0.02, "openrouter": 0.03, "ollama": 0.0}.get(
                            script.provider, 0.0
                        ),
                        note="Planning estimate; confirm actual provider billing.",
                    ),
                )

                storyboard_file = paths.storyboards / "storyboard.json"

                def storyboard_operation() -> Storyboard:
                    board = StoryboardBuilder(self.settings).run(script)
                    paths.write_json("storyboards/storyboard.json", board)
                    return board

                storyboard = self._load_or_execute_model(
                    "storyboard", storyboard_file, Storyboard, manifest, paths, storyboard_operation, resume
                )

                narration_file = paths.audio / "narration.wav"
                narration_provider_file = paths.audio / "provider.txt"

                def narration_operation() -> Path:
                    result = NarrationGenerator(self.settings, self.ffmpeg).run(script.full_text, paths.audio)
                    narration_provider_file.write_text(result.provider, encoding="utf-8")
                    return result.value

                if resume and self.store.stage_completed(manifest.run_id, "narration") and narration_file.exists():
                    narration = narration_file
                else:
                    narration = self._execute("narration", manifest, paths, narration_operation)
                narration_provider = (
                    narration_provider_file.read_text(encoding="utf-8").strip()
                    if narration_provider_file.exists()
                    else "unknown"
                )
                self._record_cost(
                    manifest,
                    CostEntry(
                        stage="narration",
                        provider=narration_provider,
                        estimated_usd={"openai": 0.12, "gemini": 0.10}.get(
                            narration_provider, 0.0
                        ),
                        note="Seven-minute planning estimate; confirm actual provider billing.",
                    ),
                )
                audio_duration = self.ffmpeg.duration(narration)
                storyboard = self._retime_storyboard(storyboard, audio_duration)
                paths.write_json("storyboards/storyboard_timed.json", storyboard)

                image_index = paths.scenes / "images.json"

                def image_operation() -> dict[int, Path]:
                    generator = SceneImageGenerator(self.settings)
                    result: dict[int, Path] = {}
                    index_payload: list[dict[str, object]] = []
                    for scene in storyboard.scenes:
                        target = paths.scenes / f"scene_{scene.index:03d}.jpg"
                        provider, generated = generator.run(scene, target)
                        result[scene.index] = generated
                        index_payload.append({"scene": scene.index, "provider": provider, "path": str(generated)})
                    paths.write_json("scenes/images.json", index_payload)
                    return result

                if resume and self.store.stage_completed(manifest.run_id, "images") and image_index.exists():
                    payload = json.loads(image_index.read_text(encoding="utf-8"))
                    images = {int(item["scene"]): Path(item["path"]) for item in payload}
                else:
                    images = self._execute("images", manifest, paths, image_operation)

                def premium_operation() -> dict[int, Path]:
                    generated, costs = PremiumSceneScheduler(self.settings).generate(
                        storyboard.scenes, paths.videos / "premium"
                    )
                    manifest.costs.extend(costs)
                    paths.write_json(
                        "videos/premium/index.json",
                        {str(index): str(path) for index, path in generated.items()},
                    )
                    paths.write_json("storyboards/storyboard_timed.json", storyboard)
                    return generated

                premium_index = paths.videos / "premium" / "index.json"
                if resume and self.store.stage_completed(manifest.run_id, "premium_video") and premium_index.exists():
                    raw = json.loads(premium_index.read_text(encoding="utf-8"))
                    premium = {int(index): Path(path) for index, path in raw.items()}
                else:
                    premium = self._execute("premium_video", manifest, paths, premium_operation)

                renderer = VideoRenderer(self.settings, self.ffmpeg)
                silent_video = paths.videos / "assembled_silent.mp4"

                def render_operation() -> Path:
                    rendered: list[Path] = []
                    for scene in storyboard.scenes:
                        output = paths.videos / f"scene_{scene.index:03d}.mp4"
                        if scene.index in premium:
                            renderer.normalize_cloud_scene(scene, premium[scene.index], output)
                        else:
                            renderer.render_scene(scene, images[scene.index], output)
                        rendered.append(output)
                    return renderer.concatenate(rendered, silent_video)

                if not (resume and self.store.stage_completed(manifest.run_id, "render") and silent_video.exists()):
                    self._execute("render", manifest, paths, render_operation)

                srt_file = paths.subtitles / "subtitles.srt"
                ass_file = paths.subtitles / "subtitles.ass"

                def subtitle_operation() -> Path:
                    cues = write_subtitles(
                        script, audio_duration, srt_file, ass_file, self.settings
                    )
                    paths.write_json("subtitles/cues.json", [cue.model_dump() for cue in cues])
                    return ass_file

                if not (resume and self.store.stage_completed(manifest.run_id, "subtitles") and ass_file.exists()):
                    self._execute("subtitles", manifest, paths, subtitle_operation)

                music_file = paths.music / "original_ambient.wav"
                sfx_file = paths.sfx / "scene_transitions.wav"
                mixed_audio = paths.audio / "final_mix.m4a"

                def sound_operation() -> Path:
                    generate_original_music(audio_duration, music_file)
                    generate_sfx_track(storyboard, audio_duration, sfx_file)
                    return mix_audio(
                        narration, music_file, sfx_file, audio_duration, mixed_audio, self.settings, self.ffmpeg
                    )

                if not (resume and self.store.stage_completed(manifest.run_id, "sound_mix") and mixed_audio.exists()):
                    self._execute("sound_mix", manifest, paths, sound_operation)

                metadata_file = paths.metadata / "metadata.json"
                thumbnail_file = paths.thumbnails / "thumbnail.jpg"

                def metadata_operation() -> VideoMetadata:
                    metadata = build_metadata(script, storyboard, self.settings)
                    paths.write_json("metadata/metadata.json", metadata)
                    paths.write_text("metadata/title.txt", metadata.title)
                    paths.write_text("metadata/description.txt", metadata.description)
                    build_thumbnail(images[1], metadata, thumbnail_file)
                    return metadata

                metadata = self._load_or_execute_model(
                    "metadata", metadata_file, VideoMetadata, manifest, paths, metadata_operation, resume
                )

                final_video = paths.final / "video.mp4"

                def finish_operation() -> Path:
                    return renderer.finish(silent_video, mixed_audio, ass_file, final_video)

                if not (resume and self.store.stage_completed(manifest.run_id, "finalize") and final_video.exists()):
                    self._execute("finalize", manifest, paths, finish_operation)

                def quality_operation() -> list[str]:
                    warnings = validate_final(
                        final_video, thumbnail_file, storyboard, metadata, self.settings, self.ffmpeg
                    )
                    paths.write_json("metadata/quality_report.json", {"warnings": warnings, "passed": not warnings})
                    return warnings

                warnings = self._execute("quality_gate", manifest, paths, quality_operation)
                manifest.warnings.extend(warnings)
                manifest.final_video = final_video
                manifest.thumbnail = thumbnail_file
                manifest.status = RunStatus.ready

                should_upload = self.settings.publishing.enabled if upload is None else upload
                upload_receipt = paths.metadata / "youtube_video_id.txt"
                if upload_receipt.exists() and not manifest.youtube_video_id:
                    manifest.youtube_video_id = upload_receipt.read_text(encoding="utf-8").strip()
                    manifest.status = RunStatus.published
                if should_upload and not manifest.youtube_video_id:

                    def upload_operation() -> str:
                        uploaded_id = YouTubePublisher(self.settings).upload(
                            final_video, thumbnail_file, srt_file, metadata, publication_date
                        )
                        paths.write_text("metadata/youtube_video_id.txt", uploaded_id)
                        return uploaded_id

                    video_id = self._execute("publish", manifest, paths, upload_operation)
                    manifest.youtube_video_id = video_id
                    manifest.status = RunStatus.published
                manifest.finished_at = datetime.now(UTC)
                manifest.current_stage = "complete"
                self._save_manifest(manifest, paths)
                return manifest
            except Exception:
                manifest.status = RunStatus.failed
                manifest.finished_at = datetime.now(UTC)
                self._save_manifest(manifest, paths)
                raise
