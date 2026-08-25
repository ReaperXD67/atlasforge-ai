from __future__ import annotations

import wave
from pathlib import Path

import pytest

from daily_video_factory.media.audio import generate_original_music, generate_sfx_track, mix_audio
from daily_video_factory.media.render import VideoRenderer
from daily_video_factory.media.subtitles import _align_script_words, write_subtitles
from daily_video_factory.models import Scene, ScriptDocument, Storyboard
from daily_video_factory.providers.tts import _atempo_chain, fit_narration_duration


def _script() -> ScriptDocument:
    text = (
        "A clear plan starts with a real customer problem. Compare options before choosing Atomy."
    )
    return ScriptDocument(
        title="A clear decision framework",
        hook=text,
        body=[text],
        cta="Share your approach.",
        full_text=text,
        word_count=len(text.split()),
        estimated_minutes=0.1,
        facts_to_verify=[],
        disclosures=["AI voice", "not financial advice"],
        provider="test",
    )


def _storyboard() -> Storyboard:
    scenes = [
        Scene(
            index=index,
            duration_seconds=2,
            narration="Example narration.",
            video_prompt="cinematic example",
            visual_search_query="business planning",
        )
        for index in range(1, 4)
    ]
    return Storyboard(title="Test", total_duration_seconds=6, scenes=scenes, provider="test")


def test_procedural_audio_has_expected_duration(tmp_path: Path) -> None:
    music = generate_original_music(2, tmp_path / "music.wav")
    sfx = generate_sfx_track(_storyboard(), 6, tmp_path / "sfx.wav")
    with wave.open(str(music), "rb") as source:
        assert source.getnframes() == 2 * source.getframerate()
    with wave.open(str(sfx), "rb") as source:
        assert source.getnframes() == 6 * source.getframerate()


def test_subtitle_outputs(settings, tmp_path: Path) -> None:
    cues = write_subtitles(
        _script(), 10, tmp_path / "captions.srt", tmp_path / "captions.ass", settings
    )
    assert cues[0].start_seconds == 0
    assert abs(cues[-1].end_seconds - 10) < 0.001
    ass = (tmp_path / "captions.ass").read_text(encoding="utf-8-sig")
    assert "Dialogue:" in ass
    assert r"{\c&H0037E6FF&}Atomy{\c&H00FFFFFF&}" in ass


def test_script_locked_alignment_corrects_brand_and_discards_asr_insertions() -> None:
    canonical = ["Join", "Atomy", "USA", "after", "reviewing", "the", "official", "guide."]
    recognized = [
        ("Join", 0.0, 0.25),
        ("ADAMI", 0.25, 0.62),
        ("USA", 0.62, 0.88),
        ("however", 0.88, 1.0),
        ("after", 1.0, 1.22),
        ("reviewing", 1.22, 1.62),
        ("the", 1.62, 1.75),
        ("official", 1.75, 2.05),
        ("guide", 2.05, 2.4),
    ]

    aligned = _align_script_words(canonical, recognized)

    assert [word for word, _start, _end in aligned] == canonical
    assert "ADAMI" not in {word for word, _start, _end in aligned}
    assert "however" not in {word for word, _start, _end in aligned}
    assert all(right[1] >= left[2] for left, right in zip(aligned, aligned[1:], strict=False))


def test_audio_mix_splits_narration_before_sidechain(settings, tmp_path: Path) -> None:
    class RecordingFFmpeg:
        def __init__(self) -> None:
            self.args: list[str] = []

        def run(self, args: list[str]) -> None:
            self.args = args

    ffmpeg = RecordingFFmpeg()
    output = tmp_path / "mixed.m4a"
    mix_audio(
        tmp_path / "narration.wav",
        tmp_path / "music.wav",
        tmp_path / "sfx.wav",
        10,
        output,
        settings,
        ffmpeg,  # type: ignore[arg-type]
    )

    filter_graph = ffmpeg.args[ffmpeg.args.index("-filter_complex") + 1]
    assert "asplit=2[narr_mix][narr_sidechain]" in filter_graph
    assert "[music][narr_sidechain]sidechaincompress" in filter_graph
    assert "[narr_mix][ducked][fx]amix" in filter_graph
    assert "normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11" in filter_graph
    assert filter_graph.count("aformat=channel_layouts=stereo") == 3


def test_slow_narration_is_pitch_preserving_duration_fitted(tmp_path: Path) -> None:
    class RecordingFFmpeg:
        def __init__(self) -> None:
            self.args: list[str] = []

        def duration(self, _path: Path) -> float:
            return 180

        def run(self, args: list[str]) -> None:
            self.args = args
            Path(args[-1]).write_bytes(b"fitted")

    narration = tmp_path / "narration.wav"
    narration.write_bytes(b"original")
    ffmpeg = RecordingFFmpeg()

    result = fit_narration_duration(
        narration,
        target_minutes=2,
        max_duration_ratio=1.18,
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
    )

    assert result == narration
    assert narration.read_bytes() == b"fitted"
    assert ffmpeg.args[ffmpeg.args.index("-filter:a") + 1] == "atempo=1.271186"
    assert _atempo_chain(5) == "atempo=2.000000,atempo=2.000000,atempo=1.250000"
    with pytest.raises(ValueError, match="positive"):
        _atempo_chain(0)


def test_local_video_master_uses_sharp_scale_without_legacy_optical_flow(
    settings, tmp_path: Path
) -> None:
    class RecordingFFmpeg:
        def __init__(self) -> None:
            self.args: list[str] = []

        def can_encode(self, _encoder: str) -> bool:
            return True

        def duration(self, _path: Path) -> float:
            return 5

        def run(self, args: list[str]) -> None:
            self.args = args

    scene = Scene(
        index=1,
        duration_seconds=5,
        narration="",
        video_prompt="photoreal motion",
        visual_search_query="controlled movement",
        selected_video_provider="comfyui_wan22",
    )
    ffmpeg = RecordingFFmpeg()
    renderer = VideoRenderer(settings, ffmpeg)  # type: ignore[arg-type]

    renderer.normalize_video_scene(scene, tmp_path / "raw.mp4", tmp_path / "master.mp4")

    video_filter = ffmpeg.args[ffmpeg.args.index("-vf") + 1]
    assert "minterpolate" not in video_filter
    assert "flags=lanczos+accurate_rnd+full_chroma_int" in video_filter
    assert f"fps={settings.video.fps}" in video_filter


def test_normalize_video_scene_applies_authored_source_reframe(settings, tmp_path: Path) -> None:
    class RecordingFFmpeg:
        def __init__(self) -> None:
            self.args: list[str] = []

        def can_encode(self, _encoder: str) -> bool:
            return True

        def duration(self, _path: Path) -> float:
            return 3.5

        def run(self, args: list[str]) -> None:
            self.args = args

    scene = Scene(
        index=1,
        duration_seconds=3.5,
        narration="",
        video_prompt="adult smoker at night",
        visual_search_query="adult smoker at night",
        source_reframe_zoom=1.35,
        source_reframe_x=0.5,
        source_reframe_y=0.0,
    )
    ffmpeg = RecordingFFmpeg()
    renderer = VideoRenderer(settings, ffmpeg)  # type: ignore[arg-type]

    renderer.normalize_video_scene(scene, tmp_path / "raw.mp4", tmp_path / "master.mp4")

    video_filter = ffmpeg.args[ffmpeg.args.index("-vf") + 1]
    assert "scale=2592:1458" in video_filter
    assert "crop=1920:1080:(iw-ow)*0.5000:(ih-oh)*0.0000" in video_filter


def test_normalize_video_scene_honors_authored_source_inpoint(settings, tmp_path: Path) -> None:
    class RecordingFFmpeg:
        def __init__(self) -> None:
            self.args: list[str] = []

        def can_encode(self, _encoder: str) -> bool:
            return True

        def duration(self, _path: Path) -> float:
            return 12

        def run(self, args: list[str]) -> None:
            self.args = args

    scene = Scene(
        index=1,
        duration_seconds=3.5,
        narration="",
        video_prompt="adult smoker at night",
        visual_search_query="adult smoker at night",
        source_inpoint_seconds=0.25,
    )
    ffmpeg = RecordingFFmpeg()
    renderer = VideoRenderer(settings, ffmpeg)  # type: ignore[arg-type]

    renderer.normalize_video_scene(scene, tmp_path / "raw.mp4", tmp_path / "master.mp4")

    assert ffmpeg.args[ffmpeg.args.index("-ss") + 1] == "0.250"


def test_zero_transition_concat_trims_scene_padding_on_storyboard_clock(
    settings, tmp_path: Path
) -> None:
    class RecordingFFmpeg:
        def __init__(self) -> None:
            self.args: list[str] = []

        def can_encode(self, _encoder: str) -> bool:
            return True

        def run(self, args: list[str]) -> None:
            self.args = args

    ffmpeg = RecordingFFmpeg()
    renderer = VideoRenderer(settings, ffmpeg)  # type: ignore[arg-type]
    scenes = [tmp_path / "scene_001.mp4", tmp_path / "scene_002.mp4"]

    renderer.concatenate(
        scenes,
        tmp_path / "hard-cut.mp4",
        [2.033, 5.667],
        transition_seconds=0.0,
    )

    graph = ffmpeg.args[ffmpeg.args.index("-filter_complex") + 1]
    assert "trim=end_frame=122" in graph
    assert "trim=end_frame=340" in graph
    assert "concat=n=2:v=1:a=0[joined]" in graph
    assert "[joined]fps=60,settb=1/60,setpts=N[video]" in graph
    assert "xfade" not in graph


def test_transition_concat_is_frame_normalized_and_capped_to_storyboard_duration(
    settings, tmp_path: Path
) -> None:
    class RecordingFFmpeg:
        def __init__(self) -> None:
            self.args: list[str] = []

        def can_encode(self, _encoder: str) -> bool:
            return True

        def run(self, args: list[str]) -> None:
            self.args = args

    ffmpeg = RecordingFFmpeg()
    renderer = VideoRenderer(settings, ffmpeg)  # type: ignore[arg-type]
    scenes = [tmp_path / "scene_001.mp4", tmp_path / "scene_002.mp4"]

    renderer.concatenate(
        scenes,
        tmp_path / "smooth.mp4",
        [2.0, 3.0],
        transition_seconds=4 / 60,
    )

    graph = ffmpeg.args[ffmpeg.args.index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=0.067:offset=2.000" in graph
    assert "fps=60,settb=1/60,setpts=N[video]" in graph
    assert ffmpeg.args[ffmpeg.args.index("-frames:v") + 1] == "300"
