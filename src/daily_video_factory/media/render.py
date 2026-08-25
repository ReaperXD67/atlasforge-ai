from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from ..artifacts import atomic_write
from ..config import Settings
from ..models import OWNED_VISUAL_MODES, Scene
from .ffmpeg import FFmpeg


def select_motion_window(
    profile: list[float],
    *,
    sample_fps: int,
    target_duration: float,
    target_energy: float,
    source_duration: float,
    scene_boundaries: list[float] | None = None,
) -> float:
    """Choose a coherent source window whose motion matches the music without crossing a cut."""
    window = max(2, round(target_duration * sample_fps))
    if len(profile) <= window:
        return 0.0
    values = np.asarray(profile, dtype=np.float32)
    low, high = np.percentile(values, [10, 92])
    normalized = (
        np.clip((values - low) / (high - low), 0, 1) if high > low else np.zeros_like(values)
    )
    desired = float(np.clip(0.16 + target_energy * 0.72, 0.16, 0.88))
    best_score = -float("inf")
    best_index = 0
    best_safe_score = -float("inf")
    best_safe_index: int | None = None
    step = max(1, sample_fps // 2)
    for index in range(0, len(normalized) - window + 1, step):
        sample = normalized[index : index + window]
        average = float(np.mean(sample))
        early = float(np.mean(sample[: max(1, sample_fps)]))
        variation = float(np.std(sample))
        abruptness = max(0.0, float(np.max(sample) - np.percentile(sample, 75)) - 0.35)
        # A high-motion cut should arrive alive; a calm phrase should stay controlled.
        arrival_bonus = early * (0.18 if target_energy >= 0.55 else 0.05)
        coherence_penalty = variation * (0.08 if target_energy >= 0.55 else 0.6)
        score = 1 - abs(average - desired) + arrival_bonus - coherence_penalty - abruptness * 0.35
        if score > best_score:
            best_score = score
            best_index = index
        start_seconds = index / sample_fps
        end_seconds = start_seconds + target_duration
        crosses_cut = any(
            start_seconds + 0.12 < boundary < end_seconds - 0.12
            for boundary in (scene_boundaries or [])
        )
        if not crosses_cut and score > best_safe_score:
            best_safe_score = score
            best_safe_index = index
    selected_index = best_safe_index if best_safe_index is not None else best_index
    return round(min(selected_index / sample_fps, max(0.0, source_duration - target_duration)), 3)


def _drawtext_font() -> str:
    candidates = [
        Path("/app/assets/fonts/BarlowCondensed-Black.ttf"),
        Path("assets/fonts/BarlowCondensed-Black.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return f"fontfile='{FFmpeg.filter_path(candidate)}'"
    return "font='Arial'"


def _safe_drawtext(value: str) -> str:
    # Storyboard creation already limits the alphabet. This second boundary keeps an imported
    # storyboard from injecting FFmpeg filter syntax through a hook phrase.
    return "".join(
        character for character in value.upper() if character.isalnum() or character in " &+.-"
    )[:88].strip()


def _fade_alpha(start: float, end: float) -> str:
    fade_in_end = min(end, start + 0.08)
    fade_out_start = max(fade_in_end, end - 0.13)
    return (
        f"if(lt(t,{fade_in_end:.3f}),(t-{start:.3f})/0.08,"
        f"if(lt(t,{fade_out_start:.3f}),1,max(0,({end:.3f}-t)/0.13)))"
    )


def music_video_filters(
    scene: Scene,
    *,
    duration: float,
    width: int,
    height: int,
    fps: int,
) -> list[str]:
    """Build deterministic, scene-local motion design for the final FFmpeg export."""
    if not scene.music_section or scene.music_edit_style == "clean":
        return []
    accents = [
        value for value in scene.beat_accents_seconds[:3] if 0 <= value < max(0, duration - 0.03)
    ]
    filters: list[str] = []
    if accents and scene.visual_mode != "information_card":
        pulse_parts = [
            (f"if(between(t,{value:.3f},{value + 0.14:.3f}),0.018*(1-(t-{value:.3f})/0.14),0)")
            for value in accents
        ]
        pulse = "+".join(pulse_parts)
        filters.extend(
            [
                (
                    f"scale=w='trunc(iw*(1+({pulse}))/2)*2':"
                    f"h='trunc(ih*(1+({pulse}))/2)*2':eval=frame"
                ),
                f"crop={width}:{height}",
                "setsar=1",
            ]
        )
    if scene.music_edit_style == "pragon_neon":
        filters.append("colorbalance=rs=-0.015:bs=0.035:rm=0.02:bm=0.025:rh=0.025:bh=0.015:pl=1")
    if scene.music_treatment == "film_texture":
        filters.append("noise=alls=5:allf=t+u")
    elif scene.music_treatment not in {"clean_hold", "ember_resolve"}:
        filters.append("noise=alls=2:allf=t+u")
    if scene.music_treatment == "shutter_trail":
        for accent_index, value in enumerate(accents[:2]):
            trail_end = min(duration, value + 0.18)
            shift = 5 if accent_index % 2 == 0 else -5
            filters.append(
                f"chromashift=cbh={-shift}:crh={shift}:edge=smear:"
                f"enable='between(t,{value:.3f},{trail_end:.3f})'"
            )
            filters.append(
                "eq=contrast=1.08:saturation=1.04:brightness=0.015:"
                f"enable='between(t,{value:.3f},{trail_end:.3f})'"
            )
    elif scene.music_treatment == "neon_flash":
        for accent_index, value in enumerate(accents[:2]):
            split_end = min(duration, value + 3 / fps)
            shift = 4 if accent_index % 2 == 0 else -4
            filters.append(
                f"chromashift=cbh={-shift}:crh={shift}:edge=smear:"
                f"enable='between(t,{value:.3f},{split_end:.3f})'"
            )
    filters.append("vignette=PI/5:eval=frame")

    font_option = _drawtext_font()
    base_size = max(54, round(min(width, height) * 0.13))
    palette = {
        "neon_strobe": ("0x38DFFF", "0xFF3159"),
        "smoke_velocity": ("0xF4EEE6", "0xD7FF45"),
        "luxury_noir": ("0xF5F1EA", "0xD1A96C"),
        "flash_editorial": ("0xFFFFFF", "0xFF4B9B"),
        "pragon_neon": ("0xF7F4ED", "0x2DE7FF"),
    }[scene.music_edit_style]
    for cue_index, cue in enumerate(scene.motion_text_cues[:6]):
        text = _safe_drawtext(cue.text)
        if not text:
            continue
        start = min(duration, cue.time_seconds)
        end = min(duration, start + cue.duration_seconds)
        if end - start < 0.08:
            continue
        alpha = _fade_alpha(start, end)
        if cue.style in {"lyric_line", "lyric_whisper"}:
            enable = f"enable='between(t,{start:.3f},{end:.3f})'"
            lyric_size = max(
                36,
                round(min(width, height) * (0.048 if len(text) > 42 else 0.060)),
            )
            lyric_y = "h*0.805"
            lyric_common = (
                f"{font_option}:text='{text}':fontsize={lyric_size}:y={lyric_y}:"
                f"alpha='{alpha}':{enable}"
            )
            filters.extend(
                [
                    "drawbox=x=iw*0.13:y=ih*0.775:w=iw*0.74:h=ih*0.115:"
                    f"color=0x030608@0.54:t=fill:{enable}",
                    "drawbox=x=iw*0.20:y=ih*0.895:w=iw*0.13:h=3:"
                    f"color=0x2DE7FF@0.86:t=fill:{enable}",
                    "drawbox=x=iw*0.67:y=ih*0.895:w=iw*0.13:h=3:"
                    f"color=0xFF315D@0.80:t=fill:{enable}",
                    (
                        f"drawtext={lyric_common}:x=(w-text_w)/2+3:fontcolor=0x2DE7FF@0.28:"
                        "borderw=1:bordercolor=0x020304@0.76"
                    ),
                    (
                        f"drawtext={lyric_common}:x=(w-text_w)/2:fontcolor=0xF8F5EE:"
                        "borderw=2:bordercolor=0x05070A@0.96:shadowx=0:shadowy=5:"
                        "shadowcolor=0x000000@0.80"
                    ),
                ]
            )
            continue
        if cue.style == "brand_neon":
            continue
        if cue.style == "brand_outro":
            display_text = " ".join(text)
            brand_size = max(92, round(min(width, height) * 0.19))
            brand_y = "h*0.30"
            enable = f"enable='between(t,{start:.3f},{end:.3f})'"
            brand_common = (
                f"{font_option}:text='{display_text}':fontsize={brand_size}:"
                f"y={brand_y}:alpha='{alpha}':{enable}"
            )
            filters.extend(
                [
                    (f"drawbox=x=0:y=ih*0.22:w=iw:h=ih*0.32:color=0x020509@0.42:t=fill:{enable}"),
                    (
                        f"drawbox=x=iw*0.18:y=ih*0.68:w=iw*0.20:h=5:"
                        f"color=0x31E7FF@0.96:t=fill:{enable}"
                    ),
                    (
                        f"drawbox=x=iw*0.62:y=ih*0.68:w=iw*0.20:h=5:"
                        f"color=0xFF315D@0.90:t=fill:{enable}"
                    ),
                    (
                        f"drawtext={brand_common}:x=(w-text_w)/2-9:fontcolor=0x31E7FF@0.64:"
                        "borderw=2:bordercolor=0x31E7FF@0.48"
                    ),
                    (
                        f"drawtext={brand_common}:x=(w-text_w)/2+9:fontcolor=0xFF315D@0.58:"
                        "borderw=2:bordercolor=0xFF315D@0.42"
                    ),
                    (
                        f"drawtext={brand_common}:x=(w-text_w)/2:fontcolor=0xF8F5EE:"
                        "borderw=3:bordercolor=0x05070A:shadowx=0:shadowy=9:"
                        "shadowcolor=0x000000@0.78"
                    ),
                ]
            )
            continue
        y = "h*0.22" if (scene.index + cue_index) % 2 else "h*0.66"
        enable = f"enable='between(t,{start:.3f},{end:.3f})'"
        common = f"{font_option}:text='{text}':fontsize={base_size}:y={y}:alpha='{alpha}':{enable}"
        cue_bar_y = "ih*0.20" if y == "h*0.22" else "ih*0.84"
        filters.append(
            f"drawbox=x=iw*0.08:y={cue_bar_y}:w=iw*0.18:h=8:color={palette[1]}@0.90:t=fill:{enable}"
        )
        if cue.style == "split":
            filters.extend(
                [
                    (
                        f"drawtext={common}:x=(w-text_w)/2-8:fontcolor={palette[0]}@0.76:"
                        "shadowx=0:shadowy=0:shadowcolor=0x000000@0.20"
                    ),
                    (
                        f"drawtext={common}:x=(w-text_w)/2+8:fontcolor={palette[1]}@0.76:"
                        "shadowx=0:shadowy=0:shadowcolor=0x000000@0.20"
                    ),
                    f"drawtext={common}:x=(w-text_w)/2:fontcolor=0xFFFFFF:borderw=2:bordercolor=0x050505",
                ]
            )
        elif cue.style == "outline":
            filters.append(
                f"drawtext={common}:x=(w-text_w)/2:fontcolor={palette[0]}:borderw=5:"
                f"bordercolor={palette[1]}:shadowx=10:shadowy=10:shadowcolor=0x000000@0.75"
            )
        elif cue.style == "stamp":
            filters.append(
                f"drawtext={common}:x=(w-text_w)/2:fontcolor={palette[0]}:borderw=2:"
                f"bordercolor={palette[1]}:box=1:boxborderw=18:boxcolor=0x050505@0.72"
            )
        else:
            filters.append(
                f"drawtext={common}:x=(w-text_w)/2:fontcolor={palette[0]}:borderw=3:"
                f"bordercolor=0x050505:shadowx=8:shadowy=8:shadowcolor={palette[1]}@0.72"
            )
    if scene.visual_mode == "information_card" and scene.music_section == "outro":
        filters.append(f"fade=t=out:st={max(0.0, duration - 1.2):.3f}:d=1.2")
    return filters


class VideoRenderer:
    def __init__(self, settings: Settings, ffmpeg: FFmpeg) -> None:
        self.settings = settings
        self.cfg = settings.video
        self.ffmpeg = ffmpeg
        self.encoder = (
            self.cfg.codec if ffmpeg.can_encode(self.cfg.codec) else self.cfg.fallback_codec
        )
        if not ffmpeg.can_encode(self.encoder):
            raise RuntimeError(
                f"Neither {self.cfg.codec} nor {self.cfg.fallback_codec} can encode a test frame"
            )

    def _video_codec_args(self) -> list[str]:
        if self.encoder.endswith("_nvenc"):
            return ["-c:v", self.encoder, "-preset", self.cfg.preset, "-cq", str(self.cfg.crf)]
        return [
            "-c:v",
            self.encoder,
            "-preset",
            self.cfg.fallback_preset,
            "-crf",
            str(self.cfg.crf),
        ]

    def render_scene(
        self,
        scene: Scene,
        image: Path,
        output: Path,
        *,
        duration_seconds: float | None = None,
    ) -> Path:
        duration = duration_seconds or scene.duration_seconds
        frames = max(2, round(duration * self.cfg.fps))
        progress = f"(0.5-0.5*cos(PI*on/{frames - 1}))"
        direction = 1 if scene.index % 2 else -1
        if scene.visual_mode in OWNED_VISUAL_MODES:
            x_expr = "(iw-iw/zoom)*0.5"
            zoom_amount = 0.012 if scene.visual_mode == "kinetic_statement" else 0.018
        else:
            x_expr = (
                f"(iw-iw/zoom)*(0.25+0.5*{progress})"
                if direction > 0
                else f"(iw-iw/zoom)*(0.75-0.5*{progress})"
            )
            zoom_amount = 0.045
        # Render the crop from a 2x supersampled canvas. zoompan rounds crop positions to
        # source pixels, so the old 1.25x canvas and vertical sine visibly stepped at 60 fps.
        # A locked optical axis plus 2x sampling makes the fallback feel like a controlled
        # dolly instead of handheld shake.
        y_expr = "(ih-ih/zoom)*0.5"
        source_width = self.cfg.width * 2
        source_height = self.cfg.height * 2
        filters = [
            f"scale={source_width}:{source_height}:force_original_aspect_ratio=increase",
            f"crop={source_width}:{source_height}",
            (
                f"zoompan=z='1+{zoom_amount}*{progress}':x='{x_expr}':y='{y_expr}':"
                f"d={frames}:s={self.cfg.width}x{self.cfg.height}:fps={self.cfg.fps}"
            ),
        ]
        filters.extend(
            music_video_filters(
                scene,
                duration=duration,
                width=self.cfg.width,
                height=self.cfg.height,
                fps=self.cfg.fps,
            )
        )
        filters.append("format=yuv420p")
        video_filter = ",".join(filters)
        output.parent.mkdir(parents=True, exist_ok=True)
        self.ffmpeg.run(
            [
                "-loop",
                "1",
                "-i",
                str(image),
                "-t",
                f"{duration:.3f}",
                "-vf",
                video_filter,
                "-an",
                *self._video_codec_args(),
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]
        )
        return output

    def normalize_video_scene(
        self,
        scene: Scene,
        source: Path,
        output: Path,
        *,
        duration_seconds: float | None = None,
    ) -> Path:
        duration = duration_seconds or scene.duration_seconds
        source_duration = self.ffmpeg.duration(source)
        local_ai = scene.selected_video_provider == "comfyui_wan22"
        speed_factor = duration / source_duration if source_duration > 0 else 1.0
        can_retime = local_ai and 1.0 < speed_factor <= 1.75
        input_args: list[str] = []
        if source_duration > duration + 0.5:
            if scene.source_inpoint_seconds is not None:
                inpoint = scene.source_inpoint_seconds
            else:
                sample_fps = 4
                profile = self.ffmpeg.video_motion_profile(source, sample_fps=sample_fps)
                if profile:
                    boundaries = self.ffmpeg.video_scene_boundaries(source)
                    inpoint = select_motion_window(
                        profile,
                        sample_fps=sample_fps,
                        target_duration=duration,
                        target_energy=scene.music_energy,
                        source_duration=source_duration,
                        scene_boundaries=boundaries,
                    )
                else:
                    available = source_duration - duration
                    seed = int(hashlib.sha256(str(scene.index).encode()).hexdigest()[:8], 16)
                    inpoint = (seed % 1000) / 1000 * available
            # Container duration can include a final partial frame. Seeking to the mathematical
            # last window may therefore leave one or two frames unavailable and create a visible
            # VFR gap at the next music cut. Keep a small decoded-frame safety margin.
            inpoint = min(
                inpoint,
                max(0.0, source_duration - duration - max(0.1, 3 / self.cfg.fps)),
            )
            scene.source_inpoint_seconds = round(inpoint, 3)
            input_args.extend(["-ss", f"{inpoint:.3f}"])
        elif source_duration + 0.2 < duration and not can_retime:
            input_args.extend(["-stream_loop", "-1"])

        filters: list[str] = []
        if can_retime:
            filters.append(f"setpts={speed_factor:.6f}*PTS")
        else:
            filters.append("setpts=PTS-STARTPTS")
        reframe_width = round(self.cfg.width * scene.source_reframe_zoom / 2) * 2
        reframe_height = round(self.cfg.height * scene.source_reframe_zoom / 2) * 2
        filters.extend(
            [
                (
                    f"scale={reframe_width}:{reframe_height}:"
                    "flags=lanczos+accurate_rnd+full_chroma_int:"
                    "force_original_aspect_ratio=increase"
                ),
                (
                    f"crop={self.cfg.width}:{self.cfg.height}:"
                    f"(iw-ow)*{scene.source_reframe_x:.4f}:"
                    f"(ih-oh)*{scene.source_reframe_y:.4f}"
                ),
                f"fps={self.cfg.fps}",
            ]
        )
        if self.cfg.clip_color_grade:
            filters.extend(
                ["eq=contrast=1.025:saturation=0.97:gamma=0.995", "unsharp=5:5:0.28:5:5:0"]
            )
        filters.extend(
            music_video_filters(
                scene,
                duration=duration,
                width=self.cfg.width,
                height=self.cfg.height,
                fps=self.cfg.fps,
            )
        )
        filters.append("format=yuv420p")
        self.ffmpeg.run(
            [
                *input_args,
                "-i",
                str(source),
                "-t",
                f"{duration:.3f}",
                "-vf",
                ",".join(filters),
                "-an",
                *self._video_codec_args(),
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]
        )
        return output

    # Backward-compatible name for external integrations created before stock/local clips.
    def normalize_cloud_scene(
        self,
        scene: Scene,
        source: Path,
        output: Path,
        *,
        duration_seconds: float | None = None,
    ) -> Path:
        return self.normalize_video_scene(scene, source, output, duration_seconds=duration_seconds)

    def concatenate(
        self,
        scene_videos: list[Path],
        output: Path,
        scene_durations: list[float] | None = None,
        *,
        transition_seconds: float | None = None,
    ) -> Path:
        if not scene_videos:
            raise ValueError("At least one scene video is required")
        transition = (
            self.cfg.transition_seconds if transition_seconds is None else transition_seconds
        )
        if scene_durations and len(scene_durations) != len(scene_videos):
            raise ValueError("scene_durations must match scene_videos")
        if scene_durations and len(scene_videos) > 1 and transition > 0:
            inputs = [value for path in scene_videos for value in ("-i", str(path))]
            filters = [
                f"[{index}:v]fps={self.cfg.fps},settb=AVTB,setpts=PTS-STARTPTS[v{index}]"
                for index in range(len(scene_videos))
            ]
            previous = "v0"
            elapsed = 0.0
            for index in range(1, len(scene_videos)):
                elapsed += scene_durations[index - 1]
                output_label = f"x{index}"
                filters.append(
                    f"[{previous}][v{index}]xfade=transition=fade:duration={transition:.3f}:"
                    f"offset={elapsed:.3f}[{output_label}]"
                )
                previous = output_label
            total_duration = sum(scene_durations)
            fade_out = max(0.0, total_duration - 0.4)
            filters.append(
                f"[{previous}]fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out:.3f}:d=0.4,"
                f"fps={self.cfg.fps},settb=1/{self.cfg.fps},setpts=N[video]"
            )
            self.ffmpeg.run(
                [
                    *inputs,
                    "-filter_complex",
                    ";".join(filters),
                    "-map",
                    "[video]",
                    *self._video_codec_args(),
                    "-pix_fmt",
                    "yuv420p",
                    "-frames:v",
                    str(max(1, round(total_duration * self.cfg.fps))),
                    str(output),
                ]
            )
            return output
        if scene_durations and len(scene_videos) > 1:
            # Normalized scene encodes can contain one or two padded tail frames. Stream-copying
            # those files makes the error accumulate over a long music edit (roughly two seconds
            # across 60 scenes). Trim on the canonical storyboard clock before the hard concat so
            # every boundary remains on its audited beat frame.
            inputs = [value for path in scene_videos for value in ("-i", str(path))]
            scene_frames = [max(1, round(duration * self.cfg.fps)) for duration in scene_durations]
            filters = [
                f"[{index}:v]trim=end_frame={frames},settb=AVTB,setpts=PTS-STARTPTS[v{index}]"
                for index, frames in enumerate(scene_frames)
            ]
            joined = "".join(f"[v{index}]" for index in range(len(scene_videos)))
            filters.append(f"{joined}concat=n={len(scene_videos)}:v=1:a=0[joined]")
            filters.append(f"[joined]fps={self.cfg.fps},settb=1/{self.cfg.fps},setpts=N[video]")
            self.ffmpeg.run(
                [
                    *inputs,
                    "-filter_complex",
                    ";".join(filters),
                    "-map",
                    "[video]",
                    *self._video_codec_args(),
                    "-pix_fmt",
                    "yuv420p",
                    str(output),
                ]
            )
            return output
        concat_file = output.with_suffix(".concat.txt")
        lines = []
        for path in scene_videos:
            safe = path.resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{safe}'")
        atomic_write(concat_file, "\n".join(lines) + "\n")
        self.ffmpeg.run(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output),
            ]
        )
        return output

    def finish(
        self,
        silent_video: Path,
        mixed_audio: Path,
        subtitles_ass: Path,
        output: Path,
    ) -> Path:
        filters = []
        if self.settings.subtitles.burn_in:
            filters = ["-vf", f"ass='{self.ffmpeg.filter_path(subtitles_ass)}'"]
        self.ffmpeg.run(
            [
                "-i",
                str(silent_video),
                "-i",
                str(mixed_audio),
                *filters,
                *self._video_codec_args(),
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-shortest",
                str(output),
            ]
        )
        return output
