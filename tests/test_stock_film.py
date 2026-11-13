import shutil
import wave
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from daily_video_factory import stock_film


def two_shot_plan() -> dict:
    return {
        "title": "The Colour of You",
        "frames": 48,
        "audio_sha256": "0" * 64,
        "assets": {"colour": {"sha256": "1" * 64}},
        "shots": [
            {"asset": "colour", "start": 0, "end": 23, "title": "opening"},
            {"asset": "colour", "start": 23, "end": 48, "source_in": 1.25, "speed": 1.6},
        ],
    }


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"start": 24}, "tile the timeline at 23"),
        ({"start": 22}, "tile the timeline at 23"),
        ({"end": 47}, "timeline ends at 47"),
        ({"asset": "missing"}, "unknown asset or grade"),
        ({"grade": "missing"}, "unknown asset or grade"),
        ({"fade_in": 10, "fade_out": 15}, "fades consume the shot"),
    ],
)
def test_rejects_inconsistent_timeline(changes: dict, error: str) -> None:
    plan = two_shot_plan()
    plan["shots"][1].update(changes)

    with pytest.raises(ValidationError, match=error):
        stock_film.Film.model_validate(plan)


def test_rejects_a_different_master_before_staging(monkeypatch, tmp_path: Path) -> None:
    def unexpected_stage(*args, **kwargs):
        pytest.fail("A mismatched master must fail before fetching clips")

    monkeypatch.setattr(stock_film, "stage_assets", unexpected_stage)
    master = tmp_path / "master.wav"
    master.write_bytes(b"different source")
    film = stock_film.Film.model_validate(two_shot_plan())

    with pytest.raises(ValueError, match="does not match the timeline SHA-256"):
        stock_film.render(film, master, tmp_path / "work", tmp_path / "film.mp4", "libx264", 1)


@pytest.mark.integration
@pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe")),
    reason="FFmpeg and FFprobe are required for the offline render",
)
def test_renders_titled_and_retimed_cut_with_the_original_stereo_master(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "colour.mp4"
    master = tmp_path / "master.wav"
    output = tmp_path / "film.mp4"
    stock_film.ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "color=blue:s=320x180:d=1:r=24",
        "-f",
        "lavfi",
        "-i",
        "color=green:s=320x180:d=1:r=24",
        "-f",
        "lavfi",
        "-i",
        "color=red:s=320x180:d=1:r=24",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0",
        "-c:v",
        "libx264",
        str(source),
    )
    time = np.arange(95_040) / 48_000  # 1.98 seconds ends within the 48th picture frame.
    left = np.sin(2 * np.pi * (220 * time + 25 * time**2))
    right = np.sin(2 * np.pi * (410 * time + 45 * time**2))
    with wave.open(str(master), "wb") as wav:
        wav.setparams((2, 2, 48_000, 0, "NONE", "not compressed"))
        wav.writeframes((np.column_stack((left, right)) * 12_000).astype("<i2").tobytes())

    plan = two_shot_plan()
    plan["audio_sha256"] = stock_film.digest(master)
    plan["assets"]["colour"]["sha256"] = stock_film.digest(source)
    monkeypatch.setattr(stock_film, "stage_assets", lambda *_: {"colour": source})

    film = stock_film.Film.model_validate(plan)
    report = stock_film.render(film, master, tmp_path / "work", output, "libx264", 1)

    assert report["frames"] == 48
    assert report["duration_seconds"] == pytest.approx(2)
    assert report["full_decode"] == "passed"
    assert min(report["audio_correlation_left_right"]) > 0.99

    frames = stock_film.ffmpeg(
        "-i",
        str(output),
        "-vf",
        "select='eq(n,0)+eq(n,13)+eq(n,22)+eq(n,23)+eq(n,38)',scale=320:180",
        "-fps_mode",
        "passthrough",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "-",
    )
    opening, title, end_of_blue, start_of_green, retimed_red = np.frombuffer(
        frames, dtype=np.uint8
    ).reshape(5, 180, 320, 3)
    assert not np.any(opening[:16])  # Letterbox is encoded in the picture.
    assert np.count_nonzero(np.min(opening, axis=2) > 180) == 0
    assert np.count_nonzero(np.min(title, axis=2) > 180) > 25
    assert np.argmax(end_of_blue[60, 60]) == 2
    assert np.argmax(start_of_green[60, 60]) == 1
    assert np.argmax(retimed_red[60, 60]) == 0  # At normal speed, this would still be green.
