import json
import re
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro


MODEL = Path.home() / ".cache/hyperframes/tts/models/kokoro-v1.0.onnx"
VOICES = Path.home() / ".cache/hyperframes/tts/voices/voices-v1.0.bin"
VOICE = "af_heart"
SPEED = 1.06
LINES = [
    "Quick—one Atomy leg has 1.9 million PV. The other has 700 thousand. Which side decides your general commission score?",
    "Most people point to the bigger side. That's the trap.",
    "Atomy USA says the calculation uses your daily smaller leg. Here, that's 700 thousand PV.",
    "Personal PV may be added to that smaller leg after you first reach 10,000 personal PV.",
    "Big side gets attention. Small side does the math. Save this, then watch the full breakdown.",
]


def word_timings(text: str, duration: float, frame: int) -> list[dict[str, object]]:
    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    usable = max(0.2, duration - 0.12)
    gap = min(0.026, usable / max(1, len(tokens)) / 5) if len(tokens) > 1 else 0
    speech = usable - gap * max(0, len(tokens) - 1)
    weights = [0.55 + max(1, len(re.sub(r"[^A-Za-z0-9]", "", token))) ** 0.5 for token in tokens]
    total_weight = sum(weights)
    cursor = 0.04
    words = []
    for index, (token, weight) in enumerate(zip(tokens, weights, strict=True)):
        start = cursor
        end = start + speech * (weight / total_weight)
        cursor = end + gap
        words.append(
            {
                "id": f"caption-word-{frame}-{index}",
                "text": token,
                "start": round(start, 3),
                "end": round(end, 3),
            }
        )
    return words


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    output = project / "assets" / "voice"
    output.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(str(MODEL), str(VOICES))
    voice_records = []
    for index, text in enumerate(LINES, 1):
        samples, sample_rate = kokoro.create(
            text,
            voice=VOICE,
            speed=SPEED,
            lang="en-us",
            sentence_pause=0.18,
            clause_pause=0.08,
        )
        target = output / f"{index:02d}.wav"
        sf.write(target, samples, sample_rate)
        duration = len(samples) / sample_rate
        voice_records.append(
            {
                "frame": index,
                "path": target.relative_to(project).as_posix(),
                "duration_s": round(duration, 3),
                "words": word_timings(text, duration, index),
            }
        )
        print(f"{target.name}\t{duration:.3f}s")

    total = round(sum(record["duration_s"] for record in voice_records), 3)
    meta = {
        "voice_lock": {"provider": "kokoro", "voice": VOICE, "speed": SPEED},
        "bgm": {
            "path": "assets/bgm/track.wav",
            "volume": 0.085,
            "query": "tense editorial quiz pulse with a satisfying reveal",
            "duration_s": total,
        },
        "bgm_pending": False,
        "total_duration_s": total,
        "voices": voice_records,
    }
    (project / "audio_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
