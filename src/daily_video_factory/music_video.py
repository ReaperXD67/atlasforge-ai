from __future__ import annotations

import json
import math
import shutil
import textwrap
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, Field

from .artifacts import RunPaths
from .config import Settings
from .media.ffmpeg import FFmpeg
from .media.render import VideoRenderer
from .models import RunManifest, RunStatus, Scene, StageStatus, Storyboard
from .providers.images import SceneImageGenerator
from .providers.video import LocalSceneScheduler, PremiumSceneScheduler, StockVideoScheduler
from .state import RunStore


class EnergyPoint(BaseModel):
    time_seconds: float
    energy: float = Field(ge=0, le=1)


class MusicSection(BaseModel):
    start_seconds: float
    end_seconds: float
    label: Literal["intro", "build", "drive", "peak", "outro"]
    energy: float = Field(ge=0, le=1)


class BeatMap(BaseModel):
    duration_seconds: float
    bpm: float
    beats_seconds: list[float]
    downbeats_seconds: list[float]
    energy_curve: list[EnergyPoint]
    sections: list[MusicSection]


def _normalized(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if not values.size:
        return values
    low, high = np.percentile(values, [5, 95])
    if high <= low:
        return np.zeros_like(values)
    return np.clip((values - low) / (high - low), 0, 1)


def analyze_music(track: Path, ffmpeg: FFmpeg) -> BeatMap:
    """Create a deterministic edit map from the uploaded master track."""
    import librosa
    from scipy.signal import find_peaks

    duration = ffmpeg.duration(track)
    waveform, sample_rate = librosa.load(track, sr=22050, mono=True, duration=duration)
    if waveform.size == 0:
        raise ValueError("The uploaded track contains no decodable audio")
    hop = 512
    onset = librosa.onset.onset_strength(y=waveform, sr=sample_rate, hop_length=hop)
    centered = onset - float(np.mean(onset))
    correlation = np.correlate(centered, centered, mode="full")[len(centered) - 1 :]
    min_lag = max(1, round(60 * sample_rate / (220 * hop)))
    max_lag = min(len(correlation) - 1, round(60 * sample_rate / (45 * hop)))
    if max_lag > min_lag:
        lag = int(np.argmax(correlation[min_lag : max_lag + 1])) + min_lag
        bpm = 60 * sample_rate / (hop * lag)
    else:
        bpm = 120.0
    if not math.isfinite(bpm) or bpm < 45 or bpm > 220:
        bpm = 120.0
    # Normalize common half/double-tempo ambiguity to a practical edit grid.
    while bpm < 75:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    beat_seconds = 60 / bpm
    minimum_peak_distance = max(1, round(beat_seconds * sample_rate / hop * 0.55))
    prominence = max(0.01, float(np.std(onset)) * 0.35)
    peak_frames, _ = find_peaks(
        onset,
        distance=minimum_peak_distance,
        prominence=prominence,
    )
    peak_times = librosa.frames_to_time(peak_frames, sr=sample_rate, hop_length=hop)
    start_candidates = peak_frames[peak_times < min(duration, 8)]
    start_frame = int(start_candidates[0]) if start_candidates.size else 0
    start_time = float(librosa.frames_to_time(start_frame, sr=sample_rate, hop_length=hop))
    expected_grid = np.arange(start_time, duration, beat_seconds)
    beats: list[float] = []
    for expected in expected_grid:
        nearby = np.where(np.abs(peak_times - expected) <= beat_seconds * 0.22)[0]
        if nearby.size:
            chosen = nearby[np.argmax(onset[peak_frames[nearby]])]
            value = float(peak_times[chosen])
        else:
            value = float(expected)
        if not beats or value - beats[-1] > beat_seconds * 0.45:
            beats.append(value)
    if len(beats) < 4:
        beats = np.arange(0, duration, beat_seconds).tolist()

    rms = librosa.feature.rms(y=waveform, frame_length=2048, hop_length=hop)[0]
    rms = _normalized(rms)
    rms_times = librosa.frames_to_time(np.arange(rms.size), sr=sample_rate, hop_length=hop)
    stride = max(1, round(0.5 * sample_rate / hop))
    energy_curve = [
        EnergyPoint(
            time_seconds=round(float(rms_times[index]), 3), energy=round(float(rms[index]), 4)
        )
        for index in range(0, rms.size, stride)
    ]

    downbeats = [round(float(value), 3) for value in beats[::4]]
    section_count = max(3, min(8, round(duration / 20)))
    edges = np.linspace(0, duration, section_count + 1)
    means: list[float] = []
    for start, end in zip(edges[:-1], edges[1:], strict=True):
        mask = (rms_times >= start) & (rms_times < end)
        means.append(float(np.mean(rms[mask])) if np.any(mask) else 0.0)
    peak = max(means) if means else 1.0
    sections: list[MusicSection] = []
    for index, (start, end, energy) in enumerate(zip(edges[:-1], edges[1:], means, strict=True)):
        relative = energy / peak if peak else 0
        label: Literal["intro", "build", "drive", "peak", "outro"]
        if index == 0:
            label = "intro"
        elif index == section_count - 1:
            label = "outro"
        elif relative >= 0.86:
            label = "peak"
        elif relative >= 0.62:
            label = "drive"
        else:
            label = "build"
        sections.append(
            MusicSection(
                start_seconds=round(float(start), 3),
                end_seconds=round(float(end), 3),
                label=label,
                energy=round(float(relative), 4),
            )
        )
    return BeatMap(
        duration_seconds=round(duration, 3),
        bpm=round(bpm, 2),
        beats_seconds=[round(float(value), 3) for value in beats],
        downbeats_seconds=downbeats,
        energy_curve=energy_curve,
        sections=sections,
    )


RACING_QUERIES = {
    "intro": [
        "race track aerial sunrise cinematic",
        "sports car garage silhouette close up",
        "race car steering wheel cockpit detail",
        "racing helmet gloves pit garage cinematic",
    ],
    "build": [
        "sports car wheel brake caliper close up",
        "driver hands racing steering wheel close up",
        "pit crew preparing sports car cinematic",
        "sports car rolling through pit lane",
    ],
    "drive": [
        "sports car racing on circuit tracking shot",
        "race car cornering on asphalt track",
        "sports car acceleration race track cinematic",
        "racing car onboard cockpit speed",
    ],
    "peak": [
        "sports cars racing side by side circuit",
        "race car fast corner tire smoke cinematic",
        "sports car night race track lights",
        "motorsport crowd finish line celebration",
    ],
    "outro": [
        "sports car cool down lap sunset",
        "race track finish line night cinematic",
        "sports car parked pit lane dramatic lights",
    ],
}


def _section_for_time(beat_map: BeatMap, time_seconds: float) -> MusicSection:
    return next(
        (
            section
            for section in beat_map.sections
            if section.start_seconds <= time_seconds < section.end_seconds
        ),
        beat_map.sections[-1],
    )


def build_racing_storyboard(
    beat_map: BeatMap,
    *,
    title: str,
    max_duration_seconds: float | None = None,
) -> Storyboard:
    duration = min(beat_map.duration_seconds, max_duration_seconds or beat_map.duration_seconds)
    beats = [beat for beat in beat_map.beats_seconds if 0 < beat < duration]
    beats_per_cut = 8 if beat_map.bpm >= 145 else 4
    while beats_per_cut * 60 / beat_map.bpm < 2:
        beats_per_cut += 2
    cut_points = [0.0, *beats[beats_per_cut - 1 :: beats_per_cut], duration]
    cut_points = sorted(set(round(value, 3) for value in cut_points))
    while len(cut_points) > 66:
        cut_points = [*cut_points[::2], duration]
        cut_points = sorted(set(cut_points))
    if len(cut_points) > 2 and cut_points[-1] - cut_points[-2] < 2:
        cut_points.pop(-2)

    scenes: list[Scene] = []
    for index, (start, end) in enumerate(zip(cut_points[:-1], cut_points[1:], strict=True)):
        section = _section_for_time(beat_map, (start + end) / 2)
        queries = RACING_QUERIES[section.label]
        query = queries[index % len(queries)]
        is_opener = index == 0
        scenes.append(
            Scene(
                index=index + 1,
                duration_seconds=round(max(2.0, end - start), 3),
                narration="" if not is_opener else "A music-led motorsport event teaser.",
                camera_angle="dynamic tracking shot"
                if section.energy > 0.6
                else "locked detail shot",
                environment="professional race circuit and pit lane",
                character_description="helmeted adult racing driver or pit crew; no visible brands",
                emotion="controlled anticipation"
                if section.label in {"intro", "build"}
                else "adrenaline",
                lighting="high-contrast race-event lighting",
                sound_effects=[],
                transition="beat_cut",
                video_prompt=(
                    f"High-end motorsport commercial, {query}, realistic vehicle physics, "
                    "controlled camera, crisp bodywork, no logos, no readable text, 16:9"
                ),
                visual_search_query=query,
                visual_exclusion_terms=[
                    "go kart",
                    "motorcycle",
                    "motorbike",
                    "bicycle",
                    "public road traffic",
                ],
                onscreen_title=title if is_opener else "",
                visual_mode="information_card" if is_opener else "documentary_broll",
                premium_score=0.92 if section.label == "peak" else 0.55,
            )
        )
    total = round(sum(scene.duration_seconds for scene in scenes), 3)
    return Storyboard(
        title=title, total_duration_seconds=total, scenes=scenes, provider="beat-grid"
    )


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def render_racing_title(title: str, bpm: float, output: Path, width: int, height: int) -> Path:
    image = Image.new("RGB", (width, height), (6, 7, 8))
    draw = ImageDraw.Draw(image, "RGBA")
    for offset in range(-height, width, 150):
        draw.polygon(
            [
                (offset, 0),
                (offset + 55, 0),
                (offset - height + 55, height),
                (offset - height, height),
            ],
            fill=(255, 83, 29, 16),
        )
    image = image.filter(ImageFilter.GaussianBlur(0.6))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, width, 18), fill=(255, 80, 24, 255))
    draw.text((105, 94), "BOSSTON  ×  PRAGON", font=_font(31, True), fill=(255, 121, 53, 255))
    wrapped = "\n".join(textwrap.wrap(title.upper(), width=23))
    draw.multiline_text(
        (105, 260), wrapped, font=_font(96, True), fill=(246, 243, 236, 255), spacing=8
    )
    draw.line((108, height - 210, width - 108, height - 210), fill=(255, 93, 30, 180), width=3)
    draw.text(
        (108, height - 165),
        f"SEPANG TRACK EXPERIENCE  /  MUSIC MASTER {bpm:.0f} BPM",
        font=_font(26, True),
        fill=(190, 190, 184, 255),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=96)
    output.with_suffix(".license.json").write_text(
        json.dumps({"provider": "locally_generated", "license": "project-owned"}, indent=2),
        encoding="utf-8",
    )
    return output


class MusicVideoPipeline:
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

    def run(
        self,
        track: Path,
        *,
        title: str = "Sepang Track Experience",
        max_duration_seconds: float | None = 60,
    ) -> RunManifest:
        self.ffmpeg.require()
        track = track.resolve()
        if not track.is_file():
            raise FileNotFoundError(track)
        publication_date = date.today()
        run_id = f"music-{publication_date.isoformat()}-{uuid.uuid4().hex[:8]}"
        paths = RunPaths.create(self.settings.output_directory.resolve(), publication_date, run_id)
        manifest = RunManifest(
            run_id=run_id,
            publication_date=publication_date,
            status=RunStatus.running,
            pipeline_kind="music_film",
            topic=title,
            output_root=paths.root,
        )
        self.store.save_manifest(manifest)

        beat_map = self._stage(manifest, "beat_analysis", lambda: analyze_music(track, self.ffmpeg))
        paths.write_json("music/audiomap.json", beat_map)
        storyboard = self._stage(
            manifest,
            "storyboard",
            lambda: build_racing_storyboard(
                beat_map, title=title, max_duration_seconds=max_duration_seconds
            ),
        )
        paths.write_json("storyboards/storyboard_timed.json", storyboard)

        images: dict[int, Path] = {}

        def make_images() -> dict[int, Path]:
            generator = SceneImageGenerator(self.settings)
            for scene in storyboard.scenes:
                target = paths.scenes / f"scene_{scene.index:03d}.jpg"
                if scene.index == 1:
                    images[scene.index] = render_racing_title(
                        title,
                        beat_map.bpm,
                        target,
                        self.settings.video.width,
                        self.settings.video.height,
                    )
                else:
                    _provider, images[scene.index] = generator.run(scene, target)
            paths.write_json(
                "scenes/images.json",
                [{"scene": index, "path": str(path)} for index, path in images.items()],
            )
            return images

        self._stage(manifest, "images", make_images)

        stock = self._stage(
            manifest,
            "stock_video",
            lambda: StockVideoScheduler(self.settings).generate(
                storyboard.scenes,
                paths.videos / "stock",
            ),
        )
        premium, premium_costs = self._stage(
            manifest,
            "premium_video",
            lambda: PremiumSceneScheduler(self.settings).generate(
                [scene for scene in storyboard.scenes if scene.index not in stock],
                paths.videos / "premium",
            ),
        )
        manifest.costs.extend(premium_costs)

        remaining = [
            scene
            for scene in storyboard.scenes
            if scene.index not in stock and scene.index not in premium
        ]
        for scene in remaining:
            if scene.ai_generation_required:
                scene.reference_image = images[scene.index]
                scene.generation_task = "image_to_video"
        local, local_costs = self._stage(
            manifest,
            "local_video",
            lambda: LocalSceneScheduler(self.settings).generate(
                remaining,
                paths.videos / "local_ai",
            ),
        )
        manifest.costs.extend(local_costs)
        paths.write_json(
            "videos/selection.json",
            {
                "premium": {str(key): str(value) for key, value in premium.items()},
                "local": {str(key): str(value) for key, value in local.items()},
                "stock": {str(key): str(value) for key, value in stock.items()},
            },
        )

        renderer = VideoRenderer(self.settings, self.ffmpeg)
        silent = paths.videos / "assembled_silent.mp4"

        def render() -> Path:
            rendered: list[Path] = []
            count = len(storyboard.scenes)
            for position, scene in enumerate(storyboard.scenes):
                output = paths.videos / f"scene_{scene.index:03d}.mp4"
                visual_duration = scene.duration_seconds
                if position < count - 1:
                    visual_duration += self.settings.video.transition_seconds
                clip = stock.get(scene.index) or premium.get(scene.index) or local.get(scene.index)
                if clip:
                    renderer.normalize_video_scene(
                        scene, clip, output, duration_seconds=visual_duration
                    )
                else:
                    renderer.render_scene(
                        scene, images[scene.index], output, duration_seconds=visual_duration
                    )
                rendered.append(output)
            return renderer.concatenate(
                rendered,
                silent,
                [scene.duration_seconds for scene in storyboard.scenes],
            )

        self._stage(manifest, "render", render)
        master = paths.music / f"master{track.suffix.lower()}"
        shutil.copy2(track, master)
        final = paths.final / "video.mp4"

        def mux() -> Path:
            duration = storyboard.total_duration_seconds
            self.ffmpeg.run(
                [
                    "-i",
                    str(silent),
                    "-i",
                    str(master),
                    "-t",
                    f"{duration:.3f}",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
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

        self._stage(manifest, "audio_master", mux)
        manifest.final_video = final
        manifest.thumbnail = images[1]
        manifest.status = RunStatus.ready
        manifest.current_stage = "complete"
        manifest.finished_at = datetime.now(UTC)
        self.store.save_manifest(manifest)
        paths.write_json("manifest.json", manifest)
        return manifest
