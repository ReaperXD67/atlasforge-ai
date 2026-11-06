"""Export measured narration timing for the new hero without changing old pilots."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

from prepare_pilot_batch import constrain_word_anchors

from daily_video_factory.media.ffmpeg import FFmpeg
from daily_video_factory.media.subtitles import write_exact_caption_sidecars
from daily_video_factory.voice_direction import VoiceDirection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=Path("videos/biznex-second-question"))
    parser.add_argument("--direction", type=Path, default=Path("config/voice-directions/biznex-second-question.json"))
    parser.add_argument("--name", choices=["baseline", "expressive"], required=True)
    args = parser.parse_args()
    text = " ".join((args.project / "script.txt").read_text(encoding="utf-8").split())
    plan = VoiceDirection.load(args.direction)
    plan.validate_transcript(text)
    audio = args.audio_dir
    performance = json.loads((audio / "narration.performance.json").read_text(encoding="utf-8"))
    if "takes" in performance:
        performance["beats"] = [take for take in performance["takes"] if take["mode"] == "directed"]
    words = json.loads((audio / "narration.words.json").read_text(encoding="utf-8"))
    if " ".join(word["text"] for word in words) != text:
        raise ValueError("Caption transcript differs from hero script")
    words, corrected = constrain_word_anchors(words, plan, performance)
    seconds = FFmpeg().duration(audio / "narration.wav")
    if not all(0 <= word["start"] < word["end"] <= seconds for word in words):
        raise ValueError("Caption timing outside actual narration")
    if any(b["start"] < a["end"] - 0.001 for a, b in zip(words, words[1:], strict=False)):
        raise ValueError("Overlapping word timing")
    write_exact_caption_sidecars(
        text, [(word["text"], word["start"], word["end"]) for word in words], audio,
        max_words=4, minimum_seconds=0.5,
    )
    beats = []
    for index, (beat, measured) in enumerate(zip(plan.beats, performance["beats"], strict=True)):
        start = measured["start_sample"] / performance["sample_rate"]
        end = (measured["start_sample"] + measured["speech_samples"] + measured["appended_pause_samples"]) / performance["sample_rate"]
        beats.append({"index": index, "id": f"beat-{index + 1:02d}", **beat.model_dump(),
                      "start": round(start, 5), "end": round(end, 5)})
    destination = args.project / "assets/audio"
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in [
        ("narration.wav", f"narration-{args.name}.wav"),
        ("narration.exact.srt", f"narration-{args.name}.srt"),
        ("narration.direction-report.json", f"narration-{args.name}.direction-report.json"),
    ]:
        shutil.copy2(audio / source, destination / target)
    timing = {
        "schema_version": 1, "voice_variant": args.name, "fps": 30,
        "duration_seconds": math.ceil(seconds * 30) / 30,
        "narration_duration_seconds": seconds, "beats": beats, "words": words,
        "captions": json.loads((audio / "narration.captions.json").read_text(encoding="utf-8")),
        "timing_basis": "ASR word evidence bounded to measured synthesis windows; exact approved transcript",
        "anchors_constrained_to_speech_beats": corrected,
    }
    path = args.project / f"{args.name}-timing.json"
    path.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"timing": str(path.resolve()), "seconds": seconds, "words": len(words)}))


if __name__ == "__main__":
    main()
