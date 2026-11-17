import json
from pathlib import Path

import pytest

from daily_video_factory import lyric_cues
from daily_video_factory.lyrics import LyricLineCue, LyricTimingReport


def test_load_cues_preserves_text_and_accepts_an_editor_envelope(tmp_path: Path) -> None:
    path = tmp_path / "cues.json"
    path.write_text(
        json.dumps(
            {"cues": [{"text": "  你好！ ", "start": 0, "end": 2, "section": "开场"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert lyric_cues.load_cues(path, 2) == [
        lyric_cues.Cue(text="  你好！ ", start=0, end=2, section="开场")
    ]


@pytest.mark.parametrize(
    ("times", "message"),
    [
        ([(0, 1), (0.9, 1.5)], "before cue 1 ends"),
        ([(1, 2), (0, 1)], "before cue 1 ends"),
        ([(0, float("nan"))], "finite"),
        ([(-0.5, 1)], "0 <= start < end"),
        ([(0.5, 0.5)], "0 <= start < end"),
        ([(0, 2.001)], "0 <= start < end"),
    ],
)
def test_load_cues_rejects_unusable_times(
    tmp_path: Path, times: list[tuple[float, float]], message: str
) -> None:
    path = tmp_path / "cues.json"
    path.write_text(
        json.dumps([{"text": "lyric", "start": start, "end": end} for start, end in times]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        lyric_cues.load_cues(path, 2.0)


@pytest.mark.parametrize(
    ("backend", "coverage", "expected_code"),
    [("faster_whisper_dtw", 0.62, 0), ("faster_whisper_dtw", 0.61, 1), ("estimated", 0, 1)],
)
def test_command_exports_only_verified_cues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    backend: str,
    coverage: float,
    expected_code: int,
) -> None:
    lyric_text = tmp_path / "lyrics.txt"
    lyric_text.write_text("新年快乐！", encoding="utf-8")
    output = tmp_path / "cues.json"
    review_output = tmp_path / "review.json"
    report = LyricTimingReport.model_validate(
        {
            "analysis_backend": backend,
            "anchor_coverage": coverage,
            "lines": [
                LyricLineCue(
                    index=0,
                    section="副歌",
                    singer="ensemble",
                    text="新年快乐！",
                    start_seconds=0.3,
                    end_seconds=2.001,
                    confidence=coverage,
                )
            ],
        }
    )
    monkeypatch.setattr(lyric_cues, "_audio_duration", lambda _: 2.0007)
    monkeypatch.setattr(lyric_cues, "load_settings", lambda _: None)
    monkeypatch.setattr(lyric_cues, "align_supplied_lyrics", lambda *_, **_kwargs: report)

    code = lyric_cues.main(
        [
            "--audio",
            str(tmp_path / "song.wav"),
            "--lyrics",
            str(lyric_text),
            "--language",
            "zh",
            "--output",
            str(output),
            "--review-output",
            str(review_output),
        ]
    )

    assert code == expected_code
    result = json.loads(output.with_suffix(".alignment.json").read_text(encoding="utf-8"))
    assert result["alignment"]["anchor_coverage"] == coverage
    if expected_code == 0:
        assert result["status"] == "ready"
        assert not review_output.exists()
        assert lyric_cues.load_cues(output, 2.0007)[0].end == 2.0007
    else:
        assert result["status"] == "needs_review"
        assert not output.exists()
        pending = json.loads(review_output.read_text(encoding="utf-8"))
        assert pending["draft_cues"][0]["text"] == "新年快乐！"
        with pytest.raises(ValueError, match="review the timing"):
            lyric_cues.load_cues(review_output, 2.0007)


def test_command_reports_probe_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def failed_probe(_: Path) -> float:
        raise RuntimeError("Recording could not be opened.")

    monkeypatch.setattr(lyric_cues, "_audio_duration", failed_probe)
    output = tmp_path / "cues.json"

    code = lyric_cues.main(
        ["--audio", "bad.wav", "--lyrics", "lyrics.txt", "--output", str(output)]
    )

    assert code == 1
    assert not output.exists()
    result = json.loads(output.with_suffix(".alignment.json").read_text(encoding="utf-8"))
    assert result["status"] == "error"
    assert result["message"] == "Recording could not be opened."
