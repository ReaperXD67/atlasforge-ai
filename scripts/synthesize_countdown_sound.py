"""Original sample-free countdown score and mechanical Foley, anchored to narration."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import wave
from pathlib import Path

import numpy as np

RATE = 48_000


def anchor(words: list[dict], phrase: str) -> float:
    def clean(text: str) -> str:
        return re.sub(r"[^a-z0-9']", "", text.lower().replace("’", "'"))
    desired = [clean(word) for word in phrase.split()]
    tokens = [clean(word["text"]) for word in words]
    matches = [i for i in range(len(tokens) - len(desired) + 1) if tokens[i:i + len(desired)] == desired]
    if len(matches) != 1:
        raise ValueError(f"Countdown sound anchor must occur once: {phrase}")
    return round(float(words[matches[0]]["start"]) * 30) / 30


def synthesize(project: Path) -> dict:
    source = project / "timing.json"
    timing = json.loads(source.read_text(encoding="utf-8-sig"))
    duration = float(timing["duration_seconds"])
    if not math.isfinite(duration) or not 20 <= duration <= 40:
        raise ValueError("Countdown sound requires a measured 20–40 second film")
    cues = {name: anchor(timing["words"], phrase) for name, phrase in {
        "countdown": "Ten seconds", "reach": "My hand", "stop": "Then I stopped",
        "question": "Was I choosing", "reveal": "or escaping", "exit": "I let the numbers",
        "clock": "The clock", "resolve": "I still needed",
    }.items()}
    # The closing camera anticipates its spoken phrase by ten frames.
    first_tick, last_tick = cues["countdown"], cues["resolve"] - 14 / 30
    if last_tick <= first_tick:
        raise ValueError("Countdown cue order is invalid")
    count = round(duration * RATE)
    t = np.arange(count, dtype=float) / RATE
    rng = np.random.default_rng(20261109)
    score = np.zeros((count, 2))
    # An original restrained suspended chord, warming after the choice is questioned.
    change = np.clip((t - cues["question"]) / .8, 0, 1)
    for index, (tense, warm) in enumerate([(146.8324, 130.8128), (174.6141, 164.8138), (220, 195.9977), (293.6648, 261.6256)]):
        for channel, detune in enumerate([.9995, 1.0005]):
            pressure = np.sin(2 * np.pi * tense * detune * t + index * .4)
            release = np.sin(2 * np.pi * warm * detune * t + index * .4)
            score[:, channel] += .026 / (1 + index * .27) * (pressure * (1 - change) + release * change)
    envelope = .58 + .24 * np.clip((t - first_tick) / max(1, cues["stop"] - first_tick), 0, 1)
    envelope[t >= cues["question"]] = .65
    envelope[t >= cues["resolve"]] *= .5
    envelope *= np.minimum(np.clip(t / .18, 0, 1), np.clip((duration - t) / .6, 0, 1))
    hush_start, hush_end = cues["stop"] - .08, min(cues["question"] - .05, cues["stop"] + .72)
    hush = np.ones(count)
    hush[(t >= hush_start) & (t <= hush_end)] = 0
    before = (t >= hush_start - .09) & (t < hush_start)
    after = (t > hush_end) & (t < hush_end + .3)
    hush[before] = (hush_start - t[before]) / .09
    hush[after] = (t[after] - hush_end) / .3
    score *= (envelope * hush)[:, None]
    machine = np.zeros_like(score)
    events = []

    def hit(at: float, kind: str, level: float, pan: float) -> None:
        x = np.arange(round(.24 * RATE)) / RATE
        noise = rng.normal(0, 1, len(x))
        if kind == "flap":
            sound = .55 * np.sin(2 * np.pi * 310 * x) * np.exp(-x * 50) + .11 * noise * np.exp(-x * 105)
        elif kind == "token":
            sound = .48 * np.sin(2 * np.pi * 620 * x) * np.exp(-x * 26) + .22 * np.sin(2 * np.pi * 1240 * x) * np.exp(-x * 50)
        else:
            sound = .55 * np.sin(2 * np.pi * 190 * x) * np.exp(-x * 45) + .08 * noise * np.exp(-x * 80)
        sound *= level * np.minimum(1, x / .0015)
        start = max(0, round(at * RATE))
        available = min(len(x), count - start)
        if available > 0:
            machine[start:start + available] += sound[:available, None] * [math.sqrt((1 - pan) / 2), math.sqrt((1 + pan) / 2)]
            events.append({"time_seconds": at, "kind": kind, "level": level, "pan": pan})

    hit(.12, "flap", .45, -.25)
    for index in range(1, 11):
        at = first_tick + index * (last_tick - first_tick) / 10
        hit(at, "flap", .7 if at < cues["stop"] else .36, -.3 if index % 2 else .3)
    hit(cues["reach"], "token", .42, 0)
    hit(cues["stop"] - .1, "stop", .6, 0)
    hit(cues["exit"], "token", .3, .3)
    hit(cues["clock"], "token", .22, .5)
    machine *= hush[:, None]
    machine *= np.clip((duration - t) / .3, 0, 1)[:, None]
    destination = project / "assets/audio"
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    for name, samples in [("score.wav", score), ("machine.wav", machine)]:
        if not np.isfinite(samples).all() or np.max(np.abs(samples)) >= 1:
            raise ValueError("Invalid or clipped generated audio")
        path = destination / name
        with wave.open(str(path), "wb") as target:
            target.setnchannels(2)
            target.setsampwidth(2)
            target.setframerate(RATE)
            target.writeframes(np.rint(samples * 32767).astype("<i2").tobytes())
        files.append({"asset": "assets/audio/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "peak": float(np.max(np.abs(samples)))})
    receipt = {"schema_version": 1, "origin": "Original deterministic mathematical synthesis; no sampled recordings or image/video/music model",
               "license": "MIT (AtlasForge-authored recipe and generated stems)", "sample_rate": RATE, "channels": 2,
               "samples": count, "duration_seconds": count / RATE, "seed": 20261109,
               "timing_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "anchors": cues,
               "hush_seconds": [hush_start, hush_end], "tick_seconds": [first_tick, last_tick],
               "events": events, "files": files, "listening_verified": False}
    (project / "SOUND_PROVENANCE.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    print(json.dumps(synthesize(parser.parse_args().project.resolve())["files"], indent=2))
