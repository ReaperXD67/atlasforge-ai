"""Render a prepared new story using the existing checked, serial media wrapper."""
from __future__ import annotations

import argparse
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import portalocker

from daily_video_factory.story_delivery import load_script
from daily_video_factory.story_pipeline import ROOT, PipelineError, local, write


def render(project: Path) -> dict[str, Any]:
    project = project.resolve()
    if not project.is_relative_to(ROOT / "videos"):
        raise PipelineError("Use a story project inside videos")
    runner = load_script("run_cinematic_project.py")
    target = local(project, "renders/final.mp4", exists=False)
    target.parent.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex
    temporary = target.parent / f".story-{run_id}.mp4"
    report: dict[str, Any] = {"schema_version": 1, "run_id": run_id, "project_id": project.name,
        "status": "running", "stages": [], "rendered": False, "delivery_verified": False,
        "visual_review_verified": False, "voice_emotion_verified": False, "published": False,
        "started_at": datetime.now(UTC).isoformat(), "output": None}
    started = time.perf_counter()
    logs = ROOT / "output/story-render" / project.name / run_id
    logs.mkdir(parents=True)
    with portalocker.Lock(str(target.parent / "cinematic-run.lock"), timeout=0):
        try:
            plan, snapshot = runner.verify_project_sources(project)
            report.update(source_files=snapshot, authored_shot_count=len(plan["shots"]),
                          authored_caption_word_count=sum(len(c["words"]) for c in plan["captions"]))
            stage_started = time.perf_counter()
            print("[render] running17-sample browser check and serial export", flush=True)
            runner.run_command(runner.render_command(project, temporary), cwd=ROOT, log=logs / "render.log")
            runner.assert_sources_unchanged(project, snapshot)
            report["stages"].append({"name": "render-with-check", "status": "passed",
                                     "elapsed_seconds": round(time.perf_counter() - stage_started, 3)})
            media = runner.verify_rendered_media(temporary, plan)
            report["stages"].append({"name": "media-verification", "status": "passed"})
            runner.assert_sources_unchanged(project, snapshot)
            report["stages"].append({"name": "final-source-verification", "status": "passed"})
            os.replace(temporary, target)
            report.update(status="verified_delivery", rendered=True, delivery_verified=True,
                          output={"file": "renders/final.mp4", **media})
            write(target.with_suffix(".report.json"), report)
        except BaseException as exc:
            report.update(status="failed", error_type=type(exc).__name__, rendered=False,
                          delivery_verified=False, output=None)
            raise
        finally:
            report["finished_at"] = datetime.now(UTC).isoformat()
            report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            write(logs / "report.json", report)
            write(project / "STORY_RENDER.json", report)
            if report["delivery_verified"]:
                write(target.with_suffix(".report.json"), report)
            temporary.unlink(missing_ok=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        result = render(args.project)
    except (Exception, KeyboardInterrupt):
        print("Story render failed; no new delivery is verified. Inspect its ignored local run log.")
        return 1
    print(f"[render] verified in {result['elapsed_seconds']:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
