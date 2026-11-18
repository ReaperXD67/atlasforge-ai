"""Rebuild reviewed song lyric timing from the local ASR evidence."""

import json
import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel

from daily_video_factory import lyrics
from daily_video_factory.config import load_settings

PROJECT = Path(__file__).resolve().parent
AUDIO = Path("C:/Users/Aman/Downloads/Boston Pragon 好运来 (1).wav")
EVIDENCE = PROJECT / "timing-evidence"
EVIDENCE.mkdir(exist_ok=True)
RAW = EVIDENCE / "asr-original-small.json"

if RAW.exists():
    data = json.loads(RAW.read_text(encoding="utf-8"))
else:
    started = time.perf_counter()
    device = sys.argv[1] if len(sys.argv) > 1 else "cpu"
    model = WhisperModel(
        "small", device=device, compute_type="int8", download_root="models/whisper"
    )
    segments, info = model.transcribe(
        str(AUDIO),
        language="zh",
        beam_size=5,
        vad_filter=False,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    data = {
        "model": "Systran/faster-whisper-small",
        "device": device,
        "compute_type": "int8",
        "language": info.language,
        "segments": [],
    }
    for s in segments:
        item = {
            "start": s.start,
            "end": s.end,
            "text": s.text,
            "avg_logprob": s.avg_logprob,
            "words": [
                {"text": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                for w in s.words or []
            ],
        }
        data["segments"].append(item)
        print(f"{s.start:7.2f}-{s.end:7.2f} {s.text}", flush=True)
    data["elapsed_seconds"] = time.perf_counter() - started
    RAW.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

observed = [
    (w["text"].strip(), w["start"], w["end"], w["probability"])
    for s in data["segments"]
    for w in s["words"]
]
lyrics._transcribe_words = lambda *_args: (observed, "zh")
report = lyrics.align_supplied_lyrics(
    AUDIO,
    (PROJECT / "lyrics.txt").read_text(encoding="utf-8"),
    load_settings(),
    duration_seconds=185.0,
    language="zh",
)
(EVIDENCE / "alignment-original.json").write_text(
    report.model_dump_json(indent=2), encoding="utf-8"
)
captions = [
    {
        "start": x.start_seconds,
        "end": x.end_seconds,
        "text": x.text,
        "section": x.section,
        "confidence": x.confidence,
        "words": [w.model_dump() for w in x.words],
    }
    for x in report.lines
]
(PROJECT / "captions.json").write_text(
    json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Coverage", report.anchor_coverage, "Confidence", report.mean_anchor_confidence)
for x in report.lines:
    print(
        f"{x.index:02} {x.start_seconds:7.2f}-{x.end_seconds:7.2f} ({x.confidence:.2f}) {x.section}: {x.text}"
    )
