"""Shared read-only checks for new story projects; reuse the existing media contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from daily_video_factory.story_pipeline import ROOT, PipelineError, local, read, sha


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location("story_" + Path(name).stem, ROOT / "scripts" / name)
    if spec is None or spec.loader is None:
        raise PipelineError("A required local delivery helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_current_render(project: Path, *, decode: bool = False) -> dict[str, Any]:
    project = project.resolve()
    runner = load_script("run_cinematic_project.py")
    report = read(local(project, "renders/final.report.json"))
    if (report.get("status") != "verified_delivery" or report.get("project_id") != project.name
            or report.get("delivery_verified") is not True or report.get("rendered") is not True
            or report.get("output", {}).get("file") != "renders/final.mp4"):
        raise PipelineError("A fresh verified delivery report is required")
    stages = {row.get("name") for row in report.get("stages", []) if row.get("status") == "passed"}
    if not {"render-with-check", "media-verification", "final-source-verification"}.issubset(stages):
        raise PipelineError("The render report omits required media/source checks")
    plan, snapshot = runner.verify_project_sources(project)
    if snapshot != report.get("source_files") or plan["project_id"] != project.name:
        raise PipelineError("Current sources differ from the rendered film")
    video = local(project, "renders/final.mp4")
    if sha(video) != report["output"].get("sha256"):
        raise PipelineError("Video bytes differ from their delivery report")
    if decode:
        observed = runner.verify_rendered_media(video, plan)
        if any(report["output"].get(key) != value for key, value in observed.items()):
            raise PipelineError("Actual media differs from the delivery report")
    load_script("package_cinematic_delivery.py").verify_captions(project, plan)
    return {"report": report, "plan": plan, "snapshot": snapshot, "video": video,
            "video_sha256": report["output"]["sha256"]}


def verify_story_qa(project: Path, verified: dict[str, Any]) -> dict[str, Any]:
    audio = read(local(project, "qa/audio/encoded-audio-verification.json"))
    frames = read(local(project, "qa/frames/frame-review.json"))
    digest = verified["video_sha256"]
    if (audio.get("video_sha256") != digest or audio.get("technical_passed") is not True
            or audio.get("asr_all_passed") is not True or audio.get("asr_total", 0) < 1
            or audio.get("asr_pass_count") != audio.get("asr_total")):
        raise PipelineError("Encoded voice QA is missing, stale or failed")
    if (frames.get("video_sha256") != digest or frames.get("frame_samples_verified") is not True
            or frames.get("shot_midpoints") != len(verified["plan"]["shots"])
            or frames.get("cut_boundaries") != len(verified["plan"]["transitions"])):
        raise PipelineError("Decoded frame coverage is missing, stale or incomplete")
    for name, digest in frames.get("files", {}).items():
        if sha(local(project, "qa/frames/" + name)) != digest:
            raise PipelineError("A decoded review image changed")
    return {"audio": audio, "frames": frames, "visual_review_verified": False,
            "voice_emotion_verified": False, "audience_performance_predicted": False}
