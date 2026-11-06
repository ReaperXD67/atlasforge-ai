"""Assemble independently transcribed model takes, retaining every source receipt."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from daily_video_factory.expressive_voice import instruction_for_delivery, sha256_file
from daily_video_factory.media.ffmpeg import FFmpeg
from daily_video_factory.media.subtitles import _align_script_words, write_exact_caption_sidecars
from daily_video_factory.providers.tts import concatenate_and_normalize
from daily_video_factory.voice_direction import VoiceDirection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--repair", type=Path, action="append", default=[])
    parser.add_argument("--direction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = VoiceDirection.load(args.direction)
    chosen = {}
    sources = []
    base = None
    for directory in [args.base, *args.repair]:
        report_path = directory / "audition-report.json"
        evidence_path = directory / "audition-independent-evidence.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if base is None:
            base = report
        for key in ("reference_sha256", "upstream_commit", "model_revision", "sample_rate"):
            if report[key] != base[key]:
                raise ValueError(f"Mixed voice/model inputs: {key}")
        sources.append({"report": str(report_path.resolve()), "sha256": sha256_file(report_path),
                        "asr_evidence": str(evidence_path.resolve()),
                        "asr_sha256": sha256_file(evidence_path)})
        for take in report["takes"]:
            if take["mode"] != "directed":
                continue
            proof = next(item for item in evidence["takes"]
                         if item["id"] == take["id"] and item["mode"] == take["mode"])
            chosen[take["id"]] = (take, proof)
    if len(chosen) != len(plan.beats):
        raise ValueError("Selected takes differ from direction beat count")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "directed").mkdir(exist_ok=True)
    sample_rate = base["sample_rate"]
    combined = []
    takes = []
    proofs = []
    words = []
    cursor = 0
    for index, beat in enumerate(plan.beats):
        identifier = f"beat-{index:03d}"
        take, proof = chosen[identifier]
        if take.get("caption_text", take["text"]) != beat.text or proof["expected_text"] != beat.text:
            raise ValueError(f"Spoken/canonical text drift: {identifier}")
        if take["seed"] != beat.seed or take["instruction"] != instruction_for_delivery(beat.emotion, beat.delivery):
            raise ValueError(f"Selected take direction/seed differs from plan: {identifier}")
        if not proof["normalized_asr_matches"]:
            raise ValueError(f"Independent ASR mismatch remains: {identifier}")
        source = Path(take["path"])
        if sha256_file(source) != take["sha256"]:
            raise ValueError(f"Take changed since synthesis: {identifier}")
        values, rate = sf.read(source, dtype="float32")
        if rate != sample_rate or len(values) != take["speech_samples"]:
            raise ValueError(f"Take sample metadata mismatch: {identifier}")
        target = args.output / "directed" / source.name
        shutil.copy2(source, target)
        pause = round(sample_rate * beat.pause_after_ms / 1000) if index + 1 < len(plan.beats) else 0
        selected = {**take, "path": str(target.resolve()), "source_take": str(source.resolve()),
                    "start_sample": cursor, "appended_pause_samples": pause}
        takes.append(selected)
        proofs.append(copy.deepcopy(proof))
        aligned = _align_script_words(beat.text.split(), [
            (word["text"], word["start"], word["end"]) for word in proof["asr_words"]
        ])
        for text, start, end in aligned:
            start = max(0, start)
            end = min(len(values) / rate, end)
            if start >= end:
                raise ValueError(f"Invalid independent word anchor: {identifier}/{text}")
            words.append((text, cursor / rate + start, cursor / rate + end))
        combined.extend([values, np.zeros(pause, dtype=np.float32)])
        cursor += len(values) + pause
    raw = args.output / "directed/narration.wav"
    sf.write(raw, np.concatenate(combined), sample_rate, subtype="PCM_16")
    ffmpeg = FFmpeg()
    narration = concatenate_and_normalize([raw], args.output / "narration.wav", -16, ffmpeg)
    report = {key: value for key, value in base.items()
              if key not in {"takes", "load_seconds", "total_seconds", "request_sha256"}}
    report.update({"assembly": "Selected independently ASR-verified model takes; explicit pauses",
                   "source_runs": sources, "direction_sha256": sha256_file(args.direction),
                   "takes": takes, "duration_seconds": ffmpeg.duration(narration),
                   "ignored_numeric_controls": ["energy", "pace"],
                   "requested_direction": plan.model_dump()})
    for name in ("audition-report.json", "narration.performance.json"):
        (args.output / name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "audition-independent-evidence.json").write_text(
        json.dumps({"source_runs": sources, "takes": proofs,
                    "all_selected_takes_normalized_asr_match": True,
                    "emotion_fidelity_verified": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    write_exact_caption_sidecars(plan.narration, words, args.output, max_words=4, minimum_seconds=0.5)
    direction_report = {
        "schema_version": 1, "requested_provider_order": ["cosyvoice3"],
        "selected_provider": "cosyvoice3", "fallback_used": False,
        "direction_requested": True, "direction_applied": True,
        "direction_mode": "reference_conditioned_semantic_instructions",
        "semantic_emotion_supported": True, "emotion_fidelity_verified": False,
        "duration_seconds": ffmpeg.duration(narration), "direction": plan.model_dump(),
        "generation_method": "Selected verified takes; see performance source receipts",
    }
    (args.output / "narration.direction-report.json").write_text(
        json.dumps(direction_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({"seconds": ffmpeg.duration(narration), "selected_takes": len(takes),
                      "words": len(words), "all_selected_takes_normalized_asr_match": True}))


if __name__ == "__main__":
    main()
