"""Prepare verified expressive voice for a new project; never overwrite a film."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_video_factory.story_voice import (  # noqa: E402
    export_story_voice,
    load_performance_plan,
    validate_new_project,
    verify_story_voice,
    write_json,
)
from daily_video_factory.voice_lab import compile_performance  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("prepare", "run", "export", "verify"), default="prepare")
    parser.add_argument("--worker-python", type=Path,
                        default=ROOT / "models/runtime/cosyvoice/Scripts/python.exe")
    args = parser.parse_args()
    project, output = args.project.resolve(), args.output.resolve()
    if not output.is_relative_to((ROOT / "output").resolve()):
        raise ValueError("Private voice runs must stay under output/")
    if not (project.is_relative_to((ROOT / "videos").resolve())
            or project.is_relative_to((ROOT / "output").resolve())):
        raise ValueError("New project must be under videos/ or output/")
    plan = load_performance_plan(args.plan)
    if args.mode == "verify" or (
        args.mode == "run" and (project / "VOICE_DELIVERY.json").exists()
    ):
        print(json.dumps(verify_story_voice(project, plan)))
        return
    validate_new_project(project, plan)
    request = compile_performance(plan)
    output.mkdir(parents=True, exist_ok=True)
    request_path = output / "performance-request.json"
    if args.mode in ("prepare", "run"):
        if (output / "audition-report.json").exists():
            raise ValueError("Takes already exist; use export or choose a fresh run directory")
        write_json(request_path, request)
        write_json(output / "performance-plan.json", plan)
    if args.mode == "prepare":
        print(json.dumps({"request": str(request_path), "takes": len(request["beats"])}))
        return
    if args.mode == "run":
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA",
                   "LOCALAPPDATA", "PROGRAMDATA", "COMSPEC", "CUDA_PATH", "CUDA_VISIBLE_DEVICES"}
        environment = {key: val for key, val in os.environ.items() if key.upper() in allowed}
        environment.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                            "PYTHONUTF8": "1", "TOKENIZERS_PARALLELISM": "false"})
        with (output / "worker.log").open("w", encoding="utf-8") as log:
            subprocess.run([
                str(args.worker_python.resolve()), str(ROOT / "scripts/expressive_voice_worker.py"),
                "--request", str(request_path), "--output", str(output),
            ], env=environment, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=1200)
        subprocess.run([
            sys.executable, str(ROOT / "scripts/inspect_voice_audition.py"),
            "--report", str(output / "audition-report.json"),
        ], env=environment, cwd=ROOT, check=True, timeout=1200)
    print(json.dumps(export_story_voice(project, plan, output)))


if __name__ == "__main__":
    main()
