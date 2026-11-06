"""Compile or verify an opted-in cinematic project's voice-anchored timeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from daily_video_factory.edit_plan import (
    EditPlan,
    EditPlanError,
    compile_project_edit_plan,
    validate_edit_plan_bundle,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, nargs="?", help="Project-local EDIT_PLAN.json")
    parser.add_argument("--check", action="store_true", help="Verify existing payloads and fingerprints without writing")
    parser.add_argument("--schema", type=Path, help="Write the current JSON schema, then exit")
    args = parser.parse_args(argv)
    if args.schema:
        if args.plan or args.check:
            parser.error("--schema cannot be combined with plan or --check")
        args.schema.parent.mkdir(parents=True, exist_ok=True)
        args.schema.write_text(json.dumps(EditPlan.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        return 0
    if args.plan is None:
        parser.error("Provide the project's EDIT_PLAN.json")
    try:
        if args.check:
            audit = validate_edit_plan_bundle(args.plan)
        else:
            _, audit = compile_project_edit_plan(args.plan)
    except (EditPlanError, ValidationError, OSError, json.JSONDecodeError) as exc:
        print(f"Edit plan rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": audit.passed, "mode": "check" if args.check else "compile",
                      "metrics": audit.metrics, "warnings": [f.code for f in audit.findings]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
