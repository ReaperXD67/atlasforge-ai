"""Prepare, run or summarize an isolated next-video voice comparison."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_video_factory.voice_lab import build_summary, compile_experiment  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("prepare", "run", "summarize"), default="prepare")
    parser.add_argument("--worker-python", type=Path,
                        default=ROOT / "models/runtime/cosyvoice/Scripts/python.exe")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "output").resolve()):
        raise ValueError("Auditions must remain under ignored output/; production files are immutable")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    request = compile_experiment(plan)
    output.mkdir(parents=True, exist_ok=True)
    request_path = output / "experiment-request.json"
    if args.mode in ("prepare", "run"):
        if (output / "audition-report.json").exists():
            raise ValueError("This experiment already has takes; choose a fresh output directory")
        write_json(request_path, request)
        write_json(output / "experiment-plan.json", plan)
    if args.mode == "prepare":
        print(json.dumps({"request": str(request_path), "takes": len(request["beats"])}))
        return
    if args.mode == "run":
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA",
                   "LOCALAPPDATA", "PROGRAMDATA", "COMSPEC", "CUDA_PATH", "CUDA_VISIBLE_DEVICES"}
        environment = {k: v for k, v in os.environ.items() if k.upper() in allowed}
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
    report = json.loads((output / "audition-report.json").read_text(encoding="utf-8"))
    evidence = json.loads((output / "audition-independent-evidence.json").read_text(encoding="utf-8"))
    summary = build_summary(plan, report, evidence)
    import numpy as np
    import soundfile as sf

    takes = {item["id"]: item for item in report["takes"]}
    rate = report["sample_rate"]
    for variant, result in zip(plan["variants"], summary["variants"], strict=True):
        chunks = []
        for index, identifier in enumerate(result["takes"]):
            audio, actual_rate = sf.read(takes[identifier]["path"], dtype="float32")
            if actual_rate != rate or audio.ndim != 1:
                raise ValueError("Unexpected take format")
            chunks.append(audio)
            if index + 1 < len(result["takes"]):
                pause = variant["beats"][index].get("pause_after_ms", 0)
                chunks.append(np.zeros(round(rate * pause / 1000), dtype=np.float32))
        destination = output / (variant["id"] + ".wav")
        sf.write(destination, np.concatenate(chunks), rate, subtype="PCM_16")
        result["audio"] = destination.name
    write_json(output / "experiment-results.json", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
