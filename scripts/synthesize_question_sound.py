"""Original sample-free ribbon rustles and warm tonal score, measured-voice anchored."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import wave
from pathlib import Path

import numpy as np

RATE = 48000


def anchor(words: list[dict], phrase: str) -> float:
    def clean(text):
        return re.sub(r"[^a-z0-9']", "", text.lower().replace("’", "'"))

    tokens = [clean(w["text"]) for w in words]
    wanted = [clean(w) for w in phrase.split()]
    matches = [
        i for i in range(len(tokens) - len(wanted) + 1) if tokens[i : i + len(wanted)] == wanted
    ]
    if len(matches) != 1:
        raise ValueError("Ribbon sound anchor must occur once: " + phrase)
    return round(words[matches[0]]["start"] * 30) / 30


def synthesize(project: Path) -> dict:
    source = project / "timing.json"
    timing = json.loads(source.read_text(encoding="utf-8-sig"))
    duration = float(timing["duration_seconds"])
    if not math.isfinite(duration) or not 20 <= duration <= 40:
        raise ValueError("Ribbon sound requires measured 20–40 second narration")
    cues = {
        key: anchor(timing["words"], phrase)
        for key, phrase in {
            "compliment": "First",
            "apology": "Then",
            "send": "pressed send",
            "reset": "So I tried",
            "fewer": "Fewer words",
            "plain": "No performance",
            "question": "what am I agreeing to",
            "clarity": "The question didn't",
            "answer": "It became possible",
        }.items()
    }
    if sorted(cues.values()) != list(cues.values()):
        raise ValueError("Ribbon sound cues must preserve narrative order")
    t = np.arange(round(duration * RATE)) / RATE
    score = np.zeros((len(t), 2))
    foley = np.zeros_like(score)
    rng = np.random.default_rng(20261111)
    release = np.clip((t - cues["reset"]) / 1.2, 0, 1)
    for index, (before, after) in enumerate(
        [(164.8138, 174.6141), (220, 220), (246.9417, 261.6256), (329.6276, 349.2282)]
    ):
        for channel, detune in enumerate([0.9997, 1.0003]):
            a = np.sin(2 * np.pi * before * detune * t + index * 0.3)
            b = np.sin(2 * np.pi * after * detune * t + index * 0.3)
            score[:, channel] += 0.033 / (1 + index * 0.3) * (a * (1 - release) + b * release)
    envelope = 0.68 * np.minimum(np.clip(t / 0.3, 0, 1), np.clip((duration - t) / 0.65, 0, 1))
    envelope[t >= cues["answer"]] *= 0.6
    hush_start, hush_end = cues["reset"] - 0.12, cues["reset"] + 0.4
    hush = np.minimum(
        np.clip((hush_start - t) / 0.12, 0, 1) + np.clip((t - hush_end) / 0.35, 0, 1), 1
    )
    score *= (envelope * hush)[:, None]
    events = []
    for key in ["opening", "compliment", "apology", "send", "fewer", "plain", "question", "answer"]:
        at = 0.12 if key == "opening" else cues[key]
        length = 0.65 if key in ("compliment", "apology", "fewer", "plain") else 0.32
        x = np.arange(round(length * RATE)) / RATE
        noise = rng.normal(0, 1, len(x))
        smooth = np.convolve(noise, np.ones(11) / 11, mode="same")
        shape = np.sin(np.pi * x / length) ** 2
        if key in ("question", "answer"):
            sound = (
                0.08 * np.sin(2 * np.pi * 880 * x) + 0.03 * np.sin(2 * np.pi * 1320 * x)
            ) * np.exp(-x * 10)
        else:
            sound = (
                0.24 * smooth * shape + 0.025 * np.sin(2 * np.pi * (190 * x + 85 * x * x)) * shape
            )
        start = round(at * RATE)
        available = min(len(sound), len(t) - start)
        pan = -0.35 if key in ("compliment", "fewer") else 0.35
        foley[start : start + available] += sound[:available, None] * [
            math.sqrt((1 - pan) / 2),
            math.sqrt((1 + pan) / 2),
        ]
        events.append({"anchor": key, "time_seconds": at, "duration_seconds": length})
    foley *= hush[:, None]
    files = []
    for name, samples in [("score", score), ("machine", foley)]:
        if not np.isfinite(samples).all() or np.max(np.abs(samples)) >= 1:
            raise ValueError("Invalid/clipping original sound")
        target = project / "assets" / "audio" / (name + ".wav")
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(RATE)
            stream.writeframes(np.round(samples * 32767).astype("<i2").tobytes())
        files.append(
            {
                "asset": target.relative_to(project).as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "peak": float(np.max(np.abs(samples))),
            }
        )
    receipt = {
        "schema_version": 1,
        "author": "BizNex original deterministic synthesis",
        "license": "MIT",
        "uses_external_recording": False,
        "timing_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "duration_seconds": duration,
        "cues": cues,
        "events": events,
        "hush_seconds": [hush_start, hush_end],
        "files": files,
        "listening_reviewed": False,
    }
    (project / "SOUND_PROVENANCE.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    print(json.dumps(synthesize(parser.parse_args().project.resolve())["files"], indent=2))
