"""Independently check difficult vocal windows with a larger local ASR model."""

import json
import subprocess
import time
from pathlib import Path

from faster_whisper import WhisperModel

P = Path(__file__).resolve().parent
E = P / "timing-evidence"
folder = next(Path("models/whisper/models--Systran--faster-whisper-medium/snapshots").iterdir())
deadline = time.monotonic() + 300
while not (folder / "model.bin").exists():
    if time.monotonic() > deadline:
        raise TimeoutError("Medium model download did not complete in the validation wait window")
    time.sleep(2)
model = WhisperModel(str(folder), device="cpu", compute_type="int8")
t = time.perf_counter()
data = []
for a, b in [(0, 40), (155, 178)]:
    audio = E / f"medium-{a:03d}-{b:03d}.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(a),
            "-i",
            "C:/Users/Aman/Downloads/Boston Pragon 好运来 (1).wav",
            "-t",
            str(b - a),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio),
        ],
        check=True,
    )
    segments, info = model.transcribe(
        str(audio),
        language="zh",
        beam_size=5,
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    for s in segments:
        item = {
            "start": s.start + a,
            "end": s.end + a,
            "text": s.text,
            "no_speech_prob": s.no_speech_prob,
            "avg_logprob": s.avg_logprob,
            "words": [
                {
                    "text": w.word,
                    "start": w.start + a,
                    "end": w.end + a,
                    "probability": w.probability,
                }
                for w in s.words or []
            ],
        }
        print(json.dumps(item, ensure_ascii=False), flush=True)
        data.append(item)
(E / "asr-medium-validation.json").write_text(
    json.dumps(
        {
            "model": "Systran/faster-whisper-medium",
            "model_revision": folder.name,
            "prompt": None,
            "source": "original song master, mono16k chunks",
            "elapsed_seconds": time.perf_counter() - t,
            "segments": data,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
