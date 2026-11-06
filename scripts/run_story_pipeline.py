"""Run a reviewed local story recipe; no account access, uploads or publishing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from daily_video_factory.story_pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--execute", action="store_true", help="Execute the declared local stages")
    parser.add_argument("--resume", action="store_true", help="Reuse only exact matching input/code/output hashes")
    args = parser.parse_args()
    try:
        result = run_pipeline(args.project, execute=args.execute, resume=args.resume)
    except (Exception, KeyboardInterrupt):
        print("Story pipeline failed. Check the recipe, local dependencies and stage report; no success is claimed.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
