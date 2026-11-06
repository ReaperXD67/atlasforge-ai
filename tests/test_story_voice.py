from __future__ import annotations

import json
import shutil

import numpy as np
import pytest
import soundfile as sf

from daily_video_factory.expressive_voice import sha256_file
from daily_video_factory.story_voice import (
    export_story_voice,
    load_performance_plan,
    validate_new_project,
    verify_story_voice,
)
from daily_video_factory.voice_lab import compile_performance


@pytest.fixture
def story(tmp_path):
    project, run = tmp_path / "film", tmp_path / "run"
    project.mkdir()
    run.mkdir()
    (project / "script.txt").write_text("I asked. I listened.", encoding="utf-8")
    reference = tmp_path / "reference.wav"
    sf.write(reference, np.sin(np.arange(72000) * 0.03) * 0.08, 24000)
    plan = {
        "schema_version": 1, "reference_audio": str(reference),
        "reference_sha256": sha256_file(reference), "reference_provenance": "Original fixture",
        "seed": 1986, "transcript": "I asked. I listened.",
        "beats": [{"text": "I asked.", "preset": "soft", "pause_after_ms": 300},
                  {"text": "I listened.", "preset": "neutral"}],
    }
    takes, proofs = [], []
    for index, beat in enumerate(compile_performance(plan)["beats"]):
        path = run / (beat["id"] + ".wav")
        sf.write(path, np.sin(np.arange(24000) * (0.04 + index * .01)) * 0.08, 24000)
        takes.append({**beat, "mode": "directed", "path": str(path), "sha256": sha256_file(path),
                      "duration_seconds": 1, "speech_samples": 24000, "inference_seconds": 2})
        proofs.append({"id": beat["id"], "mode": "directed", "expected_text": beat["caption_text"],
                       "asr_transcript": beat["caption_text"], "normalized_asr_matches": True,
                       "all_samples_finite": True, "clipped_sample_fraction": 0,
                       "asr_words": [{"text": "I", "start": .1, "end": .3},
                                     {"text": beat["caption_text"].split()[1],
                                      "start": .4, "end": .8}]})
    report = {
        "schema_version": 1, "takes": takes, "provider": "cosyvoice3", "upstream_commit": "pin",
        "model_id": "model", "model_revision": "revision", "code_license": "Apache-2.0",
        "model_license": "Apache-2.0", "reference_sha256": plan["reference_sha256"],
        "reference_provenance": plan["reference_provenance"], "sample_rate": 24000,
        "direction_mode": "reference_conditioned_semantic_instructions",
        "semantic_emotion_supported": True, "emotion_fidelity_verified": False,
        "speaker_similarity_verified": False, "load_seconds": 30, "total_seconds": 34,
    }
    evidence = {
        "schema_version": 1, "takes": proofs, "asr_model": "mock ASR, not real speech",
        "comparison_normalization": "Case/punctuation", "emotion_fidelity_verified": False,
        "speaker_similarity_verified": False, "limitations": ["Synthetic test fixture"],
    }
    (run / "audition-report.json").write_text(json.dumps(report))
    (run / "audition-independent-evidence.json").write_text(json.dumps(evidence))
    return project, run, plan


@pytest.mark.parametrize("marker", [
    "CINEMATIC_RUN.json", "renders/final.mp4", "assets/audio/narration.wav", "timing.json",
])
def test_never_overwrites_existing_project(story, marker):
    project, _, plan = story
    path = project / marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"unchanged")
    with pytest.raises(ValueError, match="new project"):
        validate_new_project(project, plan)
    assert path.read_bytes() == b"unchanged"


def test_requires_exact_approved_script(story):
    project, _, plan = story
    plan["transcript"] = "I asked. I agreed."
    with pytest.raises(ValueError, match="approved script"):
        validate_new_project(project, plan)


def test_portable_plan_resolves_reference_beside_plan(story):
    project, _, plan = story
    source = project.parent / "reference.wav"
    plan["reference_audio"] = "../reference.wav"
    path = project / "VOICE_PLAN.json"
    path.write_text(json.dumps(plan))
    assert load_performance_plan(path)["reference_audio"] == str(source.resolve())


def test_asr_failure_leaves_canonical_project_untouched(story):
    project, run, plan = story
    path = run / "audition-independent-evidence.json"
    data = json.loads(path.read_text())
    data["takes"][0].update(asr_transcript="I agreed.", normalized_asr_matches=False)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="ASR mismatch"):
        export_story_voice(project, plan, run)
    assert not (project / "assets").exists()
    assert not (project / "timing.json").exists()


@pytest.mark.integration
def test_exports_portable_measured_audio_captions_and_hashes(story):
    project, run, plan = story
    receipt = export_story_voice(project, plan, run)
    audio = project / "assets/audio"
    values, rate = sf.read(audio / "narration.wav")
    assert rate == 48000
    assert len(values) / rate == pytest.approx(2.3, abs=.002)
    assert receipt["words"] == 4
    assert receipt["canonical_narration_sha256"] == sha256_file(audio / "narration.wav")
    timing = json.loads((project / "timing.json").read_text())
    assert timing["words"][2]["start"] == pytest.approx(1.4)
    assert " ".join(word["text"] for word in timing["words"]) == plan["transcript"]
    assert receipt["emotion_fidelity_verified"] is False
    assert verify_story_voice(project, plan)["status"] == "verified_reuse"
    for path in [project / "timing.json", *audio.glob("*.json")]:
        assert str(project.parent) not in path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="new project"):
        export_story_voice(project, plan, run)


@pytest.mark.integration
@pytest.mark.parametrize("changed", ["script", "plan", "timing", "narration"])
def test_reuse_fails_closed_on_changed_source_or_media(story, changed):
    project, run, plan = story
    export_story_voice(project, plan, run)
    if changed == "script":
        (project / "script.txt").write_text("I agreed. I listened.")
    elif changed == "plan":
        plan["beats"][0]["preset"] = "happy"
    else:
        path = project / ("timing.json" if changed == "timing" else "assets/audio/narration.wav")
        path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError):
        verify_story_voice(project, plan)


@pytest.mark.integration
def test_new_project_can_use_its_own_authorized_reference(story):
    project, run, plan = story
    reference = project / "assets/audio/voice-reference.wav"
    reference.parent.mkdir(parents=True)
    shutil.copy2(plan["reference_audio"], reference)
    plan["reference_audio"] = str(reference)
    receipt = export_story_voice(project, plan, run)
    assert sha256_file(reference) == receipt["reference_sha256"]
    assert verify_story_voice(project, plan)["status"] == "verified_reuse"
