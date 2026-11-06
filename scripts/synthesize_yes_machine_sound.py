"""Create original, deterministic sound stems from measured words; no voice changes."""
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


def anchor(words: list[dict], phrase: str, *, end: bool = False) -> float:
    def token(value: str) -> str:
        return re.sub(r"[^a-z0-9']", "", value.lower().replace("’", "'"))
    wanted = [token(part) for part in phrase.split()]
    actual = [token(word["text"]) for word in words]
    matches = [i for i in range(len(actual) - len(wanted) + 1) if actual[i:i + len(wanted)] == wanted]
    if len(matches) != 1:
        raise ValueError(f"Sound anchor must occur once: {phrase}")
    return float(words[matches[0] + (len(wanted) - 1 if end else 0)]["end" if end else "start"])


def write_wav(path: Path, samples: np.ndarray) -> str:
    if not np.isfinite(samples).all() or np.max(np.abs(samples)) >= 1:
        raise ValueError("Sound synthesis produced invalid/clipped samples")
    pcm = np.rint(samples * 32767).astype("<i2")
    with wave.open(str(path), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(RATE)
        target.writeframes(pcm.tobytes())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthesize(project: Path) -> dict:
    timing_path = project / "timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8-sig"))
    duration = float(timing["duration_seconds"])
    if not math.isfinite(duration) or not 8 <= duration <= 60:
        raise ValueError("Expected a measured 8–60 second film")
    words = timing["words"]
    points = {name: anchor(words, phrase) for name, phrase in {
        "yes": "Saying yes", "chain": "One little yes", "money": "Then the money",
        "time": "The time", "unused": "The stuff", "brake": "So I tried",
        "pause": "I paused", "cost": "What does it cost", "use": "Will I use it",
        "life": "Does it fit my life", "release": "Turns out",
    }.items()}
    pause_end = anchor(words, "I paused", end=True)
    count = round(duration * RATE)
    t = np.arange(count, dtype=np.float64) / RATE
    rng = np.random.default_rng(1986)
    score = np.zeros((count, 2), dtype=np.float64)
    # Quiet low-register Cmaj9 voicing. Its envelope changes with the narration,
    # never from an independent beat grid or arbitrary copyrighted recording.
    for i, frequency in enumerate((130.8128, 164.8138, 195.9977, 246.9417, 293.6648)):
        amplitude = .026 / (1 + i * .25)
        for channel, detune in enumerate((.9993, 1.0007)):
            phase = 2 * np.pi * frequency * detune * t + i * .41
            score[:, channel] += amplitude * (np.sin(phase) + .16 * np.sin(phase * 2))
    ramp = np.clip((t - points["chain"]) / max(.1, points["brake"] - points["chain"]), 0, 1)
    envelope = .48 + .42 * ramp
    envelope[t >= points["cost"]] = .58
    envelope[t >= points["release"]] *= 10 ** (-6 / 20)
    envelope *= np.minimum(np.clip(t / .35, 0, 1), np.clip((duration - t) / .65, 0, 1))
    hush_start = max(0, points["pause"] - .1)
    hush_end = min(points["cost"] - .05, pause_end + .5)
    hush = np.ones(count)
    hush[(t >= hush_start) & (t <= hush_end)] = 0
    ramp_out = (t >= hush_start - .1) & (t < hush_start)
    hush[ramp_out] = (hush_start - t[ramp_out]) / .1
    ramp_in = (t > hush_end) & (t < hush_end + .25)
    hush[ramp_in] = (t[ramp_in] - hush_end) / .25
    score *= (envelope * hush)[:, None]
    machine = np.zeros_like(score)
    events: list[dict] = []

    def hit(at: float, kind: str, level: float, pan: float = 0) -> None:
        length = .34 if kind == "coin" else .22
        x = np.arange(round(length * RATE)) / RATE
        noise = rng.normal(0, 1, len(x))
        if kind == "coin":
            signal = sum(np.sin(2 * np.pi * f * x) * np.exp(-x * d) * a
                         for f, d, a in [(1280, 20, .5), (2510, 31, .3), (3930, 44, .18)])
        elif kind == "tick":
            signal = .5 * np.sin(2 * np.pi * 1700 * x) * np.exp(-x * 160) + .14 * noise * np.exp(-x * 250)
        elif kind == "thud":
            signal = .65 * np.sin(2 * np.pi * (125 * x - 110 * x * x)) * np.exp(-x * 32) + .09 * noise * np.exp(-x * 60)
        else:
            signal = .48 * np.sin(2 * np.pi * 430 * x) * np.exp(-x * 65) + .12 * noise * np.exp(-x * 100)
        signal *= np.minimum(1, x / .0015) * level
        start = max(0, round(at * RATE))
        available = min(len(signal), count - start)
        if available <= 0:
            return
        gains = (math.sqrt((1 - pan) / 2), math.sqrt((1 + pan) / 2))
        machine[start:start + available] += signal[:available, None] * gains
        events.append({"time_seconds": at, "kind": kind, "level": level, "pan": pan})

    hit(points["yes"], "switch", .75, -.25)
    for i in range(13):
        hit(points["chain"] + i * min(.11, (points["money"] - points["chain"]) / 14), "domino", .45, -.5 + i / 12)
    for i in range(9):
        hit(points["money"] + i * .075, "coin", .38, -.35 + i * .06)
    for at in np.arange(points["time"], points["unused"], .16):
        hit(float(at), "tick", .36, .3)
    for i in range(4):
        hit(points["unused"] + i * .24, "thud", .6, .45)
    hit(points["brake"], "switch", .55)
    for name, pan in (("cost", -.4), ("use", 0), ("life", .4)):
        hit(points[name] + .08, "switch", .32, pan)
    machine *= hush[:, None]
    machine *= np.clip((duration - t) / .3, 0, 1)[:, None]
    output = project / "assets/audio"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, samples in (("score.wav", score), ("machine.wav", machine)):
        digest = write_wav(output / name, samples)
        rows.append({"asset": f"assets/audio/{name}", "sha256": digest, "peak": float(np.max(np.abs(samples)))})
    report = {"schema_version": 1, "origin": "Original deterministic mathematical synthesis; no sampled recording or generative model",
              "sample_rate": RATE, "channels": 2, "samples": count, "duration_seconds": count / RATE,
              "timing_sha256": hashlib.sha256(timing_path.read_bytes()).hexdigest(), "seed": 1986,
              "hush_seconds": [hush_start, hush_end], "final_score_reduction_db": 6,
              "anchors": points, "events": events, "files": rows,
              "license": "MIT (AtlasForge-authored procedural recipe and its generated stems)",
              "listening_verified": False}
    (project / "SOUND_PROVENANCE.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    result = synthesize(args.project.resolve())
    print(json.dumps({"duration_seconds": result["duration_seconds"], "files": result["files"]}, indent=2))
