"""Independent local ASR/acoustic evidence; deliberately not an emotion score."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import numpy as np
import soundfile as sf


def normalized_words(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    # Same spoken compound; retain other substitutions as visible mismatches.
    text = re.sub(r"\bsign(?:-| )up\b", "signup", text)
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.environ["HF_HUB_OFFLINE"] = "1"
    from faster_whisper import WhisperModel

    model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=4,
                         download_root="models/whisper", local_files_only=True)
    source = json.loads(args.report.read_text(encoding="utf-8"))
    evidence = {
        "schema_version": 1, "source_report": str(args.report.resolve()),
        "asr_model": "cached faster-whisper small.en, CPU int8",
        "comparison_normalization": "Case/punctuation and signup/sign-up/sign up spelling only",
        "emotion_fidelity_verified": False, "speaker_similarity_verified": False,
        "limitations": ["ASR agreement is not a subjective listening review.",
                        "Different waveforms do not establish better emotion or audience retention."],
        "takes": [],
    }
    for take in source["takes"]:
        path = Path(take["path"])
        values, rate = sf.read(path, dtype="float32", always_2d=True)
        segments, info = model.transcribe(str(path), beam_size=5, language="en",
                                          vad_filter=False, condition_on_previous_text=False,
                                          word_timestamps=True)
        segments = list(segments)
        transcript = " ".join(segment.text.strip() for segment in segments)
        item = {
            "id": take["id"], "mode": take["mode"],
            "expected_text": take.get("caption_text", take["text"]),
            "synthesis_text": take["text"],
            "asr_transcript": transcript,
            "normalized_asr_matches": normalized_words(transcript) == normalized_words(take.get("caption_text", take["text"])),
            "duration_seconds": len(values) / rate, "sample_rate": rate,
            "all_samples_finite": bool(np.isfinite(values).all()),
            "peak_abs": float(np.max(np.abs(values))),
            "rms": float(np.sqrt(np.mean(values**2))),
            "clipped_sample_fraction": float(np.mean(np.abs(values) >= 0.9999)),
            "asr_words": [{"text": word.word.strip(), "start": word.start, "end": word.end}
                          for segment in segments for word in segment.words or []],
        }
        evidence["takes"].append(item)
        print(json.dumps({"id": take["id"], "mode": take["mode"],
                          "asr": transcript, "match": item["normalized_asr_matches"]}), flush=True)
    destination = args.report.with_name("audition-independent-evidence.json")
    destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
