"""Acoustic cross-attention alignment of confirmed lyrics, not ASR recovery."""

import json
import subprocess
import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import pad_or_trim
from faster_whisper.tokenizer import Tokenizer

from daily_video_factory.lyrics import parse_lyrics

P = Path(__file__).resolve().parent
E = P / "timing-evidence"
folder = next(Path("models/whisper/models--Systran--faster-whisper-medium/snapshots").iterdir())
model = WhisperModel(str(folder), device="cpu", compute_type="int8")
tokenizer = Tokenizer(
    model.hf_tokenizer, model.model.is_multilingual, task="transcribe", language="zh"
)
specs = parse_lyrics((P / "lyrics.txt").read_text(encoding="utf-8"))
t = time.perf_counter()
results = []
for a, b, indices in [(0, 14, range(0, 5)), (21, 31, range(5, 9)), (155, 178, range(61, 71))]:
    audio = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(a),
            "-i",
            str(P / "assets/bgm.wav"),
            "-t",
            str(b - a),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    samples = np.frombuffer(audio, dtype=np.float32)
    features = model.feature_extractor(samples)
    frames = features.shape[-1]
    encoder = model.encode(pad_or_trim(features))
    text = "。".join(specs[i].text for i in indices)
    tokens = tokenizer.encode(text)
    alignment = model.find_alignment(tokenizer, [tokens], encoder, frames)[0]
    item = {
        "source_start": a,
        "source_end": b,
        "line_indices": list(indices),
        "supplied_text": text,
        "words": [],
    }
    for w in alignment:
        item["words"].append(
            {
                "text": w["word"],
                "start": round(float(w["start"]) + a, 3),
                "end": round(float(w["end"]) + a, 3),
                "probability": float(w["probability"]),
            }
        )
    print(json.dumps(item, ensure_ascii=False), flush=True)
    results.append(item)
(E / "forced-alignment-medium.json").write_text(
    json.dumps(
        {
            "method": "CTranslate2 Whisper cross-attention DTW against exact user-confirmed text",
            "model_revision": folder.name,
            "elapsed_seconds": time.perf_counter() - t,
            "windows": results,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
