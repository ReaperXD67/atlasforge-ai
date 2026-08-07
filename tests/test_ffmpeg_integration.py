from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from daily_video_factory.config import load_settings
from daily_video_factory.media.audio import generate_original_music, generate_sfx_track, mix_audio
from daily_video_factory.media.ffmpeg import FFmpeg
from daily_video_factory.media.render import VideoRenderer
from daily_video_factory.media.subtitles import write_subtitles
from daily_video_factory.models import Scene, ScriptDocument, Storyboard
from daily_video_factory.providers.images import TitleCardImageProvider


@pytest.mark.integration
def test_real_ffmpeg_render_mix_and_subtitles(tmp_path: Path, monkeypatch) -> None:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("FFmpeg is not on PATH")
    settings = load_settings(
        Path("config/default.yaml"),
        overrides={
            "video": {
                "width": 640,
                "height": 360,
                "fps": 24,
                "codec": "libx264",
                "fallback_codec": "libx264",
                "crf": 24,
            },
            "subtitles": {"font_size": 26},
        },
    )
    scenes = [
        Scene(
            index=index,
            duration_seconds=3,
            narration="Start with a real problem." if index == 1 else "Then compare Atomy with alternatives.",
            video_prompt=f"cinematic planning scene {index}",
            visual_search_query="business planning",
        )
        for index in (1, 2)
    ]
    board = Storyboard(title="Test", total_duration_seconds=6, scenes=scenes, provider="test")
    script_text = "Start with a real customer problem. Then compare Atomy with practical alternatives."
    script = ScriptDocument(
        title="A grounded comparison",
        hook=script_text,
        body=[script_text],
        cta="Share your criteria.",
        full_text=script_text,
        word_count=len(script_text.split()),
        estimated_minutes=0.1,
        facts_to_verify=[],
        disclosures=["AI voice", "not financial advice"],
        provider="test",
    )
    image_provider = TitleCardImageProvider(settings)
    renderer = VideoRenderer(settings, FFmpeg())
    rendered = []
    for scene in scenes:
        image = image_provider.generate(scene, tmp_path / f"scene_{scene.index}.jpg")
        rendered.append(renderer.render_scene(scene, image, tmp_path / f"scene_{scene.index}.mp4"))
    silent = renderer.concatenate(rendered, tmp_path / "silent.mp4")
    narration = generate_original_music(6, tmp_path / "narration.wav")
    music = generate_original_music(6, tmp_path / "music.wav")
    sfx = generate_sfx_track(board, 6, tmp_path / "sfx.wav")
    mixed = mix_audio(narration, music, sfx, 6, tmp_path / "mixed.m4a", settings, FFmpeg())
    ass = tmp_path / "captions.ass"
    write_subtitles(script, 6, tmp_path / "captions.srt", ass, settings)
    final = renderer.finish(silent, mixed, ass, tmp_path / "final.mp4")
    assert final.stat().st_size > 100_000
    assert 5.5 <= FFmpeg().duration(final) <= 6.5

