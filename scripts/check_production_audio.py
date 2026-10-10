"""Read-only final MP4 loudness check; emits JSON without private local paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from daily_video_factory.production_audio_quality import (
    ProductionAudioQualityError,
    check_production_audio,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = check_production_audio(args.manifest)
    except ProductionAudioQualityError as exc:
        report = {"status": "failed", "error": {"code": exc.code, "message": str(exc)}}
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
