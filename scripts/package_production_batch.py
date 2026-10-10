"""Validate and bundle mixed-format videos, thumbnails and upload copy."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from daily_video_factory.production_audio_quality import check_production_audio
from daily_video_factory.production_batch import (
    load_production_batch_manifest,
    run_production_batch,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = load_production_batch_manifest(args.manifest)
    # Resume rechecks media/source hashes and can rerender stale/missing episodes;
    # this packaging workflow is not a verify-only alternative to the runner.
    report = run_production_batch(args.manifest, resume=True)
    if report["status"] != "verified":
        raise ValueError("All deliveries must pass before packaging")
    verified = {item["id"]: item["report"] for item in report["episodes"]}
    audio_quality = check_production_audio(args.manifest)
    if audio_quality["status"] != "verified":
        raise ValueError("Final audio quality must pass before packaging")
    audio_readings = {item["id"]: item for item in audio_quality["episodes"]}
    root = Path(__file__).resolve().parents[1]
    out = root / "output" / manifest.batch_id
    out.mkdir(parents=True, exist_ok=True)
    upload_text = ["# BizNex Repair Lab — three Shorts and two videos\n",
                   "Approved female narration: Kokoro af_heart. Final H.264/AAC MP4s, 30 fps. No automatic YouTube upload.\n"]
    files, summary = [], []
    for ep in manifest.episodes:
        duration = verified[ep.id]["duration_seconds"]
        upload_text.append(f"\n---\n\n# {ep.id} ({ep.format}, {duration:.1f}s)\n\n")
        upload_text.append(ep.upload_package.read_text(encoding="utf-8"))
        files.extend([(ep.output, f"{ep.id}/final.mp4"),
                      (ep.thumbnail, f"{ep.id}/thumbnail.png"),
                      (ep.upload_package, f"{ep.id}/UPLOAD_PACKAGE.md")])
        summary.append({"id": ep.id, "format": ep.format, "duration_seconds": duration,
                        "voice": "af_heart", "delivery_passed": True,
                        "video": f"{ep.id}/final.mp4", "thumbnail": f"{ep.id}/thumbnail.png",
                        "audio_quality": {"integrated_lufs": audio_readings[ep.id]["integrated_lufs"],
                                          "true_peak_dbtp": audio_readings[ep.id]["true_peak_dbtp"]}})
    metadata = out / "UPLOAD_ALL.md"
    metadata.write_text("\n".join(upload_text), encoding="utf-8")
    validation = out / "DELIVERY_SUMMARY.json"
    validation.write_text(json.dumps({"batch_id": manifest.batch_id, "episodes": summary,
                          "guaranteed_views": False, "uploaded_to_youtube": False}, indent=2) + "\n", encoding="utf-8")
    archive = out / "biznex-three-shorts-two-videos.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as delivery:
        for source, name in files:
            delivery.write(source, name)
        delivery.write(metadata, metadata.name)
        delivery.write(validation, validation.name)
    print(f"Package: {archive}\nMetadata: {metadata}\nVerification: {validation}")


if __name__ == "__main__":
    main()
