import json
import subprocess
from pathlib import Path

from faster_whisper import WhisperModel

P = Path(__file__).resolve().parent
E = P / "timing-evidence"
model = WhisperModel("small", device="cpu", compute_type="int8", download_root="models/whisper")
out = []
for n, (a, b, prompt) in enumerate(
    [(0, 3.7, "锣鼓敲起来。"), (0, 7.7, "锣鼓敲起来，鞭炮响起来，新年的钟声已经到来。")]
):
    audio = E / f"opening-focused-{n}.wav"
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
        beam_size=7,
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt=prompt,
    )
    for s in segments:
        item = {
            "start": s.start + a,
            "end": s.end + a,
            "text": s.text,
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
        print(n, json.dumps(item, ensure_ascii=False), flush=True)
        out.append(item)
(E / "opening-first-focused.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
