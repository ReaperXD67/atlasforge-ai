"""Controlled voice auditions without changing the production narrator.

The same words, reference and seed are required for every variant. Native cues
are synthesis-only; caption text remains explicit and cannot quietly change.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from daily_video_factory.expressive_voice import sha256_file, validate_request

PRESETS = {
    "neutral": "",
    "soft": "Please say a sentence in a very soft voice.",
    "happy": "请非常开心地说一句话。",
    "sad": "请非常伤心地说一句话。",
    "angry": "请非常生气地说一句话。",
}
# Supported by the pinned CosyVoice3 tokenizer. Existence is not proof of fidelity.
NATIVE_CUES = ("[breath]", "[quick_breath]", "[sigh]", "<strong>", "</strong>")
CARDINAL_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty",
)
ASR_NORMALIZATION = (
    "Case/punctuation, signup/sign-up/sign up spelling, and standalone unsigned "
    "integer numerals 0–20 versus their exact cardinal words only; no homophones"
)


def words(text: str) -> list[str]:
    return re.findall(r"[\w]+(?:['’][\w]+)?", text.lower().replace("’", "'"))


def asr_words(text: str) -> list[str]:
    # Normalize transcription notation, never a different value or a homophone.
    # Exclude signed numbers, decimals, percentages, ordinals and zero padding.
    text = re.sub(
        r"(?<![\w.+\-−])(?:20|1[0-9]|[0-9])(?![\w%]|\.\d)",
        lambda match: CARDINAL_WORDS[int(match[0])], text,
    )
    text = re.sub(r"\bsign(?:-| )up\b", "signup", text.lower())
    return words(text)


def clean_synthesis_text(text: str) -> str:
    for token in NATIVE_CUES:
        text = text.replace(token, "")
    if any(char in text for char in "[]<>"):
        raise ValueError("Unknown native voice control")
    return text


def compile_experiment(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile one model load with individually identified comparison takes."""
    return _compile_variants(plan, minimum_variants=2)


def performance_as_experiment(plan: dict[str, Any]) -> dict[str, Any]:
    """Use the same validation for a single production performance plan."""
    return {**plan, "variants": [{"id": "beat", "label": "Authored performance",
                                  "beats": plan["beats"]}]}


def compile_performance(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile a new film's thought groups without changing production providers."""
    return _compile_variants(performance_as_experiment(plan), minimum_variants=1,
                             allow_beat_seed=True)


def _compile_variants(
    plan: dict[str, Any], *, minimum_variants: int, allow_beat_seed: bool = False,
) -> dict[str, Any]:
    if plan.get("schema_version") != 1:
        raise ValueError("Unsupported voice experiment version")
    reference = Path(plan.get("reference_audio", ""))
    if not reference.is_file() or sha256_file(reference) != plan.get("reference_sha256"):
        raise ValueError("Authorized reference hash does not match")
    transcript = plan.get("transcript", "")
    if not isinstance(transcript, str) or not words(transcript):
        raise ValueError("A nonempty comparison transcript is required")
    seed = plan.get("seed", 1986)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("Invalid comparison seed")
    variants = plan.get("variants")
    if not isinstance(variants, list) or not minimum_variants <= len(variants) <= 6:
        raise ValueError("Expected two to six controlled variants")
    ids = set()
    beats = []
    for variant in variants:
        identifier = variant.get("id", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", identifier) or identifier in ids:
            raise ValueError("Variant IDs must be unique safe basenames")
        ids.add(identifier)
        items = variant.get("beats", [])
        if not items or words(" ".join(item["text"] for item in items)) != words(transcript):
            raise ValueError("Every variant must preserve the complete comparison transcript")
        for index, item in enumerate(items):
            beat_seed = item.get("seed", seed)
            if (isinstance(beat_seed, bool) or not isinstance(beat_seed, int)
                    or not 0 <= beat_seed < 2**32):
                raise ValueError("Invalid per-thought seed")
            if not allow_beat_seed and beat_seed != seed:
                raise ValueError("Controlled variants must use the same seed")
            text = item["text"]
            synthesis = item.get("synthesis_text", text)
            if words(clean_synthesis_text(synthesis)) != words(text):
                raise ValueError("Native cues cannot alter the spoken words")
            if synthesis.count("<strong>") != synthesis.count("</strong>"):
                raise ValueError("Unbalanced emphasis control")
            if "delivery" in item and "preset" in item:
                raise ValueError("Choose a preset or experimental delivery, not both")
            if "delivery" in item:
                delivery = item["delivery"]
                if not isinstance(delivery, str) or any(c in delivery for c in "<>[]"):
                    raise ValueError("Experimental delivery must be plain text")
            else:
                preset = item.get("preset", "neutral")
                if preset not in PRESETS:
                    raise ValueError("Unknown documented delivery preset")
                delivery = PRESETS[preset]
            instruction = "You are a helpful assistant."
            if delivery:
                instruction += " " + delivery
            beats.append({
                "id": f"{identifier}-{index:02}", "text": synthesis, "caption_text": text,
                "instruction": instruction + "<|endofprompt|>", "seed": beat_seed,
                "pause_after_ms": item.get("pause_after_ms", 0),
            })
    request = {
        "schema_version": 1, "reference_audio": str(reference.resolve()),
        "reference_provenance": plan.get("reference_provenance", ""), "beats": beats,
    }
    validate_request(request)
    return request


def build_summary(
    plan: dict[str, Any], report: dict[str, Any], evidence: dict[str, Any],
    *, single_performance: bool = False,
) -> dict[str, Any]:
    """Record actual runtime/transcript evidence without inventing a quality score."""
    request = _compile_variants(plan, minimum_variants=1 if single_performance else 2,
                                allow_beat_seed=single_performance)
    planned = {item["id"]: item for item in request["beats"]}
    generated = {item["id"]: item for item in report["takes"]}
    checked = {item["id"]: item for item in evidence["takes"]}
    if len(generated) != len(report["takes"]) or len(checked) != len(evidence["takes"]):
        raise ValueError("Duplicate take in evidence")
    if planned.keys() != generated.keys() or planned.keys() != checked.keys():
        raise ValueError("Missing or unexpected comparison evidence")
    if report["reference_sha256"] != plan["reference_sha256"]:
        raise ValueError("Evidence uses a different reference")
    for identifier, expected in planned.items():
        actual, check = generated[identifier], checked[identifier]
        if any(actual.get(key) != expected[key] for key in ("text", "caption_text", "instruction", "seed")):
            raise ValueError("Generated performance does not match the experiment")
        if words(check["expected_text"]) != words(expected["caption_text"]):
            raise ValueError("ASR evidence compares the wrong words")
        actual_match = asr_words(check["asr_transcript"]) == asr_words(expected["caption_text"])
        if check["normalized_asr_matches"] != actual_match:
            raise ValueError("ASR match flag contradicts the recognized transcript")
        if sha256_file(Path(actual["path"])) != actual["sha256"]:
            raise ValueError("Take changed after generation")
    variants = []
    for variant in plan["variants"]:
        selected = [generated[f"{variant['id']}-{i:02}"] for i in range(len(variant["beats"]))]
        checks = [checked[item["id"]] for item in selected]
        speech_seconds = sum(item["duration_seconds"] for item in selected)
        pause_seconds = sum(
            variant["beats"][i].get("pause_after_ms", 0) / 1000
            for i in range(len(selected) - 1)
        )
        inference_seconds = sum(item["inference_seconds"] for item in selected)
        variants.append({
            "id": variant["id"], "label": variant["label"], "take_count": len(selected),
            "speech_seconds": round(speech_seconds, 4),
            "authored_silence_seconds": pause_seconds,
            "duration_seconds": round(speech_seconds + pause_seconds, 4),
            "inference_seconds": round(inference_seconds, 3),
            "real_time_factor_excluding_load": round(inference_seconds / speech_seconds, 4),
            "asr_matches": sum(check["normalized_asr_matches"] for check in checks),
            "asr_total": len(checks),
            "all_finite": all(check["all_samples_finite"] for check in checks),
            "clipped_sample_fraction_max": max(check["clipped_sample_fraction"] for check in checks),
            "takes": [item["id"] for item in selected],
        })
    return {
        "schema_version": 1, "transcript": plan["transcript"], "seed": plan["seed"],
        "reference_sha256": report["reference_sha256"], "provider": report["provider"],
        "model_revision": report["model_revision"], "upstream_commit": report["upstream_commit"],
        "load_seconds": report["load_seconds"], "total_seconds": report["total_seconds"],
        "cuda_peak_allocated_bytes": report.get("cuda_peak_allocated_bytes"),
        "variants": variants, "recommended_variant": None,
        "emotion_fidelity_verified": False, "speaker_similarity_verified": False,
        "listening_review_required": True,
        "comparison_notes": [
            "Grouping, documented instructions and native cues are separately contrasted.",
            "Word matching and speed are objective checks, not emotion or preference scores.",
            "The synthetic reference limits how much human performance can be inferred.",
            "All variants use speed 1.0; no pitch shift, tempo effect or replacement model.",
        ],
    }
