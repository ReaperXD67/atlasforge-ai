from __future__ import annotations

import copy

import pytest

from daily_video_factory.expressive_voice import sha256_file
from daily_video_factory.voice_lab import build_summary, compile_experiment


@pytest.fixture
def plan(tmp_path):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"authorized synthetic fixture")
    return {
        "schema_version": 1, "reference_audio": str(reference),
        "reference_sha256": sha256_file(reference), "reference_provenance": "Original synthesis",
        "seed": 1986, "transcript": "I asked. Then I listened.",
        "variants": [
            {"id": "split", "label": "Separate sentences", "beats": [
                {"text": "I asked.", "preset": "soft", "pause_after_ms": 300},
                {"text": "Then I listened.", "preset": "soft"},
            ]},
            {"id": "grouped", "label": "One thought with breath", "beats": [
                {"text": "I asked. Then I listened.",
                 "synthesis_text": "I asked. [breath] Then I listened.", "preset": "soft"},
            ]},
        ],
    }


def test_grouping_and_native_cues_preserve_exact_caption_words(plan):
    request = compile_experiment(plan)
    assert len(request["beats"]) == 3
    assert request["beats"][-1]["text"] == "I asked. [breath] Then I listened."
    assert request["beats"][-1]["caption_text"] == plan["transcript"]
    assert {beat["seed"] for beat in request["beats"]} == {1986}
    assert request["beats"][0]["instruction"] == request["beats"][-1]["instruction"]


@pytest.mark.parametrize("synthesis", [
    "I asked. Then I bought it.", "I asked. [invented-emotion] Then I listened.",
    "I asked. <strong>Then I listened.",
])
def test_rejects_changed_words_unknown_or_unbalanced_cues(plan, synthesis):
    plan["variants"][1]["beats"][0]["synthesis_text"] = synthesis
    with pytest.raises(ValueError):
        compile_experiment(plan)


def test_rejects_changed_reference_and_transcript(plan):
    changed = copy.deepcopy(plan)
    changed["reference_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="reference hash"):
        compile_experiment(changed)
    plan["variants"][0]["beats"].pop()
    with pytest.raises(ValueError, match="complete comparison transcript"):
        compile_experiment(plan)


def fixture_evidence(plan, tmp_path):
    request = compile_experiment(plan)
    generated, checked = [], []
    for beat in request["beats"]:
        path = tmp_path / (beat["id"] + ".wav")
        path.write_bytes(beat["id"].encode())
        generated.append({**beat, "path": str(path), "sha256": sha256_file(path),
                          "duration_seconds": 2, "inference_seconds": 1})
        checked.append({"id": beat["id"], "expected_text": beat["caption_text"],
                        "asr_transcript": ("I bought." if beat["id"] == "split-00"
                                           else beat["caption_text"]),
                        "normalized_asr_matches": beat["id"] != "split-00",
                        "all_samples_finite": True, "clipped_sample_fraction": 0})
    report = {
        "takes": generated, "reference_sha256": plan["reference_sha256"],
        "provider": "cosyvoice3", "model_revision": "pinned", "upstream_commit": "pinned",
        "load_seconds": 30, "total_seconds": 33,
    }
    return report, {"takes": checked}


def test_records_asr_failure_and_measured_speed_without_quality_recommendation(plan, tmp_path):
    report, evidence = fixture_evidence(plan, tmp_path)
    result = build_summary(plan, report, evidence)
    assert result["variants"][0]["asr_matches"] == 1
    assert result["variants"][0]["asr_total"] == 2
    assert result["variants"][0]["duration_seconds"] == 4.3
    assert result["variants"][1]["real_time_factor_excluding_load"] == 0.5
    assert result["recommended_variant"] is None
    assert result["emotion_fidelity_verified"] is False
    assert result["speaker_similarity_verified"] is False


@pytest.mark.parametrize("fault", ["missing", "seed", "wording", "tamper", "false-match"])
def test_summary_requires_complete_unmodified_matching_evidence(plan, tmp_path, fault):
    report, evidence = fixture_evidence(plan, tmp_path)
    if fault == "missing":
        evidence["takes"].pop()
    elif fault == "seed":
        report["takes"][0]["seed"] += 1
    elif fault == "wording":
        evidence["takes"][0]["expected_text"] = "Different text"
    elif fault == "false-match":
        evidence["takes"][0]["normalized_asr_matches"] = True
    else:
        (tmp_path / "split-00.wav").write_bytes(b"altered take")
    with pytest.raises(ValueError):
        build_summary(plan, report, evidence)
