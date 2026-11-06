"""Export independently verified thought-group narration into a new film project."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

from daily_video_factory.expressive_voice import sha256_file
from daily_video_factory.media.ffmpeg import FFmpeg
from daily_video_factory.media.subtitles import _align_script_words, write_exact_caption_sidecars
from daily_video_factory.voice_lab import build_summary, performance_as_experiment


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_performance_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    reference = Path(plan.get("reference_audio", ""))
    if not reference.is_absolute() and not reference.is_file():
        # Portable project VOICE_PLAN.json resolves beside the plan. Repository
        # configs retain their existing root-relative path when it is available.
        reference = path.parent / reference
    plan["reference_audio"] = str(reference.resolve())
    return plan


def performance_plan_hash(plan: dict[str, Any]) -> str:
    portable = {key: value for key, value in plan.items() if key != "reference_audio"}
    payload = json.dumps(portable, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _voice_files(plan: dict[str, Any]) -> list[str]:
    names = ["narration.wav", "narration.srt", "narration.words.json", "narration.captions.json",
             "narration.caption-verification.json", "narration.performance.json",
             "narration.asr-evidence.json", "narration.direction-report.json",
             "voice-reference.wav", "voice-reference.provenance.json"]
    return ["timing.json", *["assets/audio/" + name for name in names],
            *[f"assets/audio/voice-takes/beat-{index:02}.wav"
              for index in range(len(plan["beats"]))]]


def bind_voice_receipt(project: Path, plan: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Bind a newly exported delivery; callers must have validated source takes."""
    return {**receipt, "performance_plan_sha256": performance_plan_hash(plan),
            "script_sha256": sha256_file(project / "script.txt"),
            "voice_files": {name: sha256_file(project / name) for name in _voice_files(plan)}}


def verify_story_voice(project: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Verify exact existing voice inputs for a resumable pipeline, without writing."""
    receipt = json.loads((project / "VOICE_DELIVERY.json").read_text(encoding="utf-8"))
    if receipt.get("performance_plan_sha256") != performance_plan_hash(plan):
        raise ValueError("Existing voice uses a different/unbound performance plan; use a fresh project")
    if receipt.get("script_sha256") != sha256_file(project / "script.txt"):
        raise ValueError("Approved script changed after voice export; use a fresh project")
    if set(receipt.get("voice_files", {})) != set(_voice_files(plan)):
        raise ValueError("Incomplete canonical voice receipt")
    for name, expected in receipt["voice_files"].items():
        if sha256_file(project / name) != expected:
            raise ValueError(f"Canonical voice input changed: {name}")
    audio = project / "assets/audio"
    report = json.loads((audio / "narration.performance.json").read_text(encoding="utf-8"))
    evidence = json.loads((audio / "narration.asr-evidence.json").read_text(encoding="utf-8"))
    for take in report["takes"]:
        path = (audio / take["path"]).resolve()
        if not path.is_relative_to(audio.resolve()):
            raise ValueError("Take path escapes portable audio directory")
        take["path"] = str(path)
    # Validation does not require a private source checkout or copied absolute path.
    local_plan = {**plan, "reference_audio": str(audio / "voice-reference.wav")}
    report.setdefault("load_seconds", 0)
    report.setdefault("total_seconds", 0)
    checked = build_summary(performance_as_experiment(local_plan), report, evidence,
                            single_performance=True)["variants"][0]
    if checked["asr_matches"] != checked["asr_total"] or not checked["all_finite"]:
        raise ValueError("Existing voice no longer passes independent evidence checks")
    if sha256_file(audio / "narration.wav") != receipt["canonical_narration_sha256"]:
        raise ValueError("Canonical voice hash disagrees with receipt")
    return {**receipt, "status": "verified_reuse", "generation_repeated": False}


def validate_new_project(project: Path, plan: dict[str, Any]) -> str:
    """Never replace a delivered film or existing canonical narration."""
    frozen = ("CINEMATIC_RUN.json", "renders/final.mp4", "renders/final.report.json",
              "VOICE_DELIVERY.json", "assets/audio/narration.wav", "timing.json")
    if any((project / item).exists() for item in frozen):
        raise ValueError("Voice export requires a new project without canonical/delivered media")
    script = " ".join((project / "script.txt").read_text(encoding="utf-8").split())
    if script != " ".join(plan["transcript"].split()):
        raise ValueError("Performance plan must match the complete approved script exactly")
    return script


def export_story_voice(project: Path, plan: dict[str, Any], run: Path) -> dict[str, Any]:
    """Fail before copying project inputs if any word, sample or receipt is suspect."""
    import numpy as np
    import soundfile as sf

    from daily_video_factory.providers.tts import concatenate_and_normalize

    script = validate_new_project(project, plan)
    report_path = run / "audition-report.json"
    evidence_path = run / "audition-independent-evidence.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    summary = build_summary(performance_as_experiment(plan), report, evidence,
                            single_performance=True)
    result = summary["variants"][0]
    if result["asr_matches"] != result["asr_total"]:
        raise ValueError("Independent ASR mismatch: repair the take before voice export")
    if not result["all_finite"] or result["clipped_sample_fraction_max"]:
        raise ValueError("Invalid or clipped source audio")
    rate = report["sample_rate"]
    generated = {item["id"]: item for item in report["takes"]}
    checked = {item["id"]: item for item in evidence["takes"]}
    chunks, words, beats, takes = [], [], [], []
    cursor = 0
    staging = run / "prepared"
    staging.mkdir(exist_ok=True)
    for index, item in enumerate(plan["beats"]):
        identifier = f"beat-{index:02}"
        take, proof = generated[identifier], checked[identifier]
        values, actual_rate = sf.read(take["path"], dtype="float32")
        if actual_rate != rate or values.ndim != 1 or len(values) != take["speech_samples"]:
            raise ValueError("Actual take samples differ from performance receipt")
        if not np.isfinite(values).all() or not np.any(values):
            raise ValueError("Invalid source take")
        aligned = _align_script_words(item["text"].split(), [
            (word["text"], word["start"], word["end"]) for word in proof["asr_words"]
        ])
        for text, start, end in aligned:
            start, end = max(0, start), min(len(values) / rate, end)
            if start >= end:
                raise ValueError("ASR word lies outside its measured speech window")
            words.append((text, cursor / rate + start, cursor / rate + end))
        pause = (round(rate * item.get("pause_after_ms", 0) / 1000)
                 if index + 1 < len(plan["beats"]) else 0)
        selected = {**take, "start_sample": cursor, "appended_pause_samples": pause,
                    "path": f"voice-takes/{identifier}.wav"}
        selected.pop("source_take", None)
        takes.append(selected)
        beats.append({"index": index, "id": f"beat-{index + 1:02d}", "text": item["text"],
                      "start": round(cursor / rate, 5),
                      "end": round((cursor + len(values) + pause) / rate, 5),
                      "delivery": item.get("delivery", item.get("preset", "neutral")),
                      "pause_after_ms": item.get("pause_after_ms", 0)})
        chunks.extend([values, np.zeros(pause, dtype=np.float32)])
        cursor += len(values) + pause
    if any(right[1] < left[2] for left, right in zip(words, words[1:], strict=False)):
        raise ValueError("Overlapping independent word timing")
    raw = staging / "narration-raw.wav"
    sf.write(raw, np.concatenate(chunks), rate, subtype="PCM_16")
    ffmpeg = FFmpeg()
    narration = concatenate_and_normalize([raw], staging / "narration.wav", -16, ffmpeg)
    seconds = ffmpeg.duration(narration)
    if abs(seconds - cursor / rate) > 0.002:
        raise ValueError("Normalization changed narration duration")
    write_exact_caption_sidecars(script, words, staging, max_words=4, minimum_seconds=0.5)
    captions = json.loads((staging / "narration.captions.json").read_text(encoding="utf-8"))
    word_data = json.loads((staging / "narration.words.json").read_text(encoding="utf-8"))
    if any(cue["end"] > seconds + 0.001 for cue in captions):
        raise ValueError("Caption extends past narration")
    performance = {
        key: copy.deepcopy(report[key]) for key in (
            "schema_version", "provider", "upstream_commit", "model_id", "model_revision",
            "code_license", "model_license", "reference_sha256", "reference_provenance",
            "sample_rate", "direction_mode", "semantic_emotion_supported",
            "emotion_fidelity_verified", "speaker_similarity_verified",
        )
    }
    performance.update({"reference_audio": "voice-reference.wav", "takes": takes,
                        "source_report_sha256": sha256_file(report_path),
                        "source_asr_sha256": sha256_file(evidence_path)})
    portable_evidence = {key: copy.deepcopy(evidence[key]) for key in (
        "schema_version", "asr_model", "comparison_normalization", "takes",
        "emotion_fidelity_verified", "speaker_similarity_verified", "limitations",
    )}
    portable_evidence["source_report_sha256"] = sha256_file(report_path)
    portable_evidence["all_selected_takes_normalized_asr_match"] = True
    timing = {
        "schema_version": 1, "voice_variant": "expressive", "fps": 30,
        "duration_seconds": math.ceil(seconds * 30) / 30,
        "narration_duration_seconds": seconds, "beats": beats,
        "words": word_data, "captions": captions,
        "timing_basis": "Independent per-thought ASR bounded to measured speech samples",
        "anchors_constrained_to_speech_beats": 0,
    }
    direction = {
        "schema_version": 1, "selected_provider": "cosyvoice3", "fallback_used": False,
        "direction_requested": True, "direction_applied": True,
        "direction_mode": report["direction_mode"], "semantic_emotion_supported": True,
        "emotion_fidelity_verified": False, "duration_seconds": seconds,
        "ignored_numeric_controls": [], "generation_method": "Verified authored thought groups",
    }
    # All validation precedes this new-project copy. Existing canonical files are
    # checked again after slow normalization, so a concurrent delivery is preserved.
    validate_new_project(project, plan)
    destination = project / "assets/audio"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "voice-takes").mkdir(exist_ok=True)
    for source, target in (
        ("narration.wav", "narration.wav"), ("narration.exact.srt", "narration.srt"),
        ("narration.words.json", "narration.words.json"),
        ("narration.captions.json", "narration.captions.json"),
        ("narration.caption-verification.json", "narration.caption-verification.json"),
    ):
        shutil.copy2(staging / source, destination / target)
    if Path(plan["reference_audio"]).resolve() != (destination / "voice-reference.wav").resolve():
        shutil.copy2(plan["reference_audio"], destination / "voice-reference.wav")
    for take in takes:
        shutil.copy2(generated[take["id"]]["path"], destination / take["path"])
    write_json(destination / "narration.performance.json", performance)
    write_json(destination / "narration.asr-evidence.json", portable_evidence)
    write_json(destination / "narration.direction-report.json", direction)
    write_json(destination / "voice-reference.provenance.json", {
        "schema_version": 1, "sha256": plan["reference_sha256"],
        "provenance": plan["reference_provenance"], "source": "Authorized synthetic reference",
    })
    write_json(project / "timing.json", timing)
    receipt = {
        "schema_version": 1, "duration_seconds": timing["duration_seconds"],
        "narration_seconds": seconds, "words": len(words), "beats": len(beats),
        "all_selected_takes_asr_match": True,
        "canonical_narration_sha256": sha256_file(destination / "narration.wav"),
        "reference_sha256": plan["reference_sha256"],
        "timing_sha256": sha256_file(project / "timing.json"),
        "srt_sha256": sha256_file(destination / "narration.srt"),
        "emotion_fidelity_verified": False, "speaker_similarity_verified": False,
    }
    receipt = bind_voice_receipt(project, plan, receipt)
    write_json(project / "VOICE_DELIVERY.json", receipt)
    return receipt
