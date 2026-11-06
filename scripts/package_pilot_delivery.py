"""Export verified pilot deliveries, or extract review frames without rendering/uploading."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from daily_video_factory.production_audio_quality import measure_video_loudness, validate_loudness
from daily_video_factory.production_batch import (
    ProductionBatchManifest,
    load_production_batch_manifest,
    source_fingerprint,
    verify_production_episode,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config/batches/biznex-first-six.production.json"
BATCH_ID = "biznex-first-six"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def deliverable_hashes(episode: Any) -> dict[str, str]:
    return {key: sha256(path) for key, path in {
        "video": episode.output, "thumbnail": episode.thumbnail,
        "upload_package": episode.upload_package, "voice_manifest": episode.voice_manifest,
    }.items()}


def verify_batch(manifest: ProductionBatchManifest) -> tuple[dict, dict]:
    """Require a completed matching report and recheck it; never invoke a renderer."""
    if manifest.batch_id != BATCH_ID or len(manifest.episodes) != 6:
        raise ValueError("This helper requires the six-episode biznex-first-six manifest")
    report = json.loads(manifest.report_path.read_text(encoding="utf-8-sig"))
    if (report.get("status") != "verified" or report.get("schema_version") != 1
            or report.get("batch_id") != manifest.batch_id
            or report.get("expected_voice") != manifest.expected_voice
            or Path(report.get("manifest", "")).resolve() != manifest.path):
        raise ValueError("A completed verified report for this exact manifest is required")
    rows = report.get("episodes", [])
    expected = {episode.id for episode in manifest.episodes}
    if (len(rows) != 6 or {row.get("id") for row in rows} != expected
            or any(row.get("status") != "verified" for row in rows)):
        raise ValueError("The report must contain all six verified episodes exactly once")
    by_id = {row["id"]: row for row in rows}
    checks = {}
    for episode in manifest.episodes:
        row = by_id[episode.id]
        fingerprint, _ = source_fingerprint(episode, manifest)
        if fingerprint != row.get("source_fingerprint"):
            raise ValueError(f"{episode.id}: sources changed after delivery verification")
        if deliverable_hashes(episode) != row.get("deliverable_hashes"):
            raise ValueError(f"{episode.id}: delivery bytes changed after verification")
        checks[episode.id] = {
            "media": verify_production_episode(episode),
            "audio": validate_loudness(measure_video_loudness(episode.output)),
            "source_fingerprint": fingerprint,
        }
    return report, checks


def archive_directory(directory: Path, archive: Path) -> None:
    """Stable ordering, timestamps and attributes make unchanged exports reproducible."""
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for source in sorted(path for path in directory.rglob("*") if path.is_file()):
            info = zipfile.ZipInfo(source.relative_to(directory).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            with source.open("rb") as incoming, bundle.open(info, "w", force_zip64=True) as outgoing:
                shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)


def package_delivery(manifest_path: Path, *, root: Path = ROOT) -> dict[str, str]:
    root = root.resolve()
    manifest = load_production_batch_manifest(manifest_path, repository_root=root)
    report, checks = verify_batch(manifest)
    report_hash, manifest_hash = sha256(manifest.report_path), sha256(manifest.path)
    parent = (root / "output/deliveries").resolve()
    if not parent.is_relative_to(root / "output"):
        raise ValueError("Delivery output must remain inside the repository output directory")
    destination, archive = parent / BATCH_ID, parent / f"{BATCH_ID}.zip"
    if destination.exists() or archive.exists():
        raise ValueError("Delivery already exists; preserve or move the existing export before retrying")
    parent.mkdir(parents=True, exist_ok=True)
    exported = []
    summaries = []
    combined = ["# BizNex: six verified private-ready pilots\n",
                "No upload or publication is performed by this package.\n"]
    with tempfile.TemporaryDirectory(prefix=".pilot-package-", dir=parent) as temporary:
        staging = Path(temporary) / BATCH_ID
        staging.mkdir()
        for episode in manifest.episodes:
            episode_dir = staging / episode.id
            episode_dir.mkdir()
            files = {
                "final.mp4": episode.output,
                "thumbnail.png": episode.thumbnail,
                "UPLOAD_PACKAGE.md": episode.upload_package,
                "captions.srt": episode.project / "assets/audio/narration.exact.srt",
                "captions.json": episode.project / "assets/audio/narration.captions.json",
                "words.json": episode.project / "assets/audio/narration.words.json",
                "narration.txt": episode.project / "narration.txt",
                "audio-provenance.json": episode.project / "assets/audio/provenance.json",
            }
            for name, source in files.items():
                if not source.is_file() or not source.resolve().is_relative_to(episode.project):
                    raise ValueError(f"{episode.id}: missing or unsafe export input {name}")
                source_hash = sha256(source)
                target = episode_dir / name
                if name == "UPLOAD_PACKAGE.md":
                    copy = source.read_text(encoding="utf-8-sig")
                    copy = copy.replace(episode.output.relative_to(episode.project).as_posix(), "final.mp4")
                    copy = copy.replace(episode.thumbnail.relative_to(episode.project).as_posix(), "thumbnail.png")
                    target.write_text(copy, encoding="utf-8")
                    combined.extend([f"\n---\n\n# {episode.id}\n", copy])
                else:
                    shutil.copyfile(source, target)
                    if sha256(target) != source_hash:
                        raise ValueError(f"{episode.id}: source changed during copy of {name}")
                exported.append({"path": target.relative_to(staging).as_posix(),
                                 "bytes": target.stat().st_size, "sha256": sha256(target),
                                 "source_path": source.relative_to(root).as_posix(),
                                 "source_sha256": source_hash})
            media = checks[episode.id]["media"]
            summaries.append({"id": episode.id, "format": episode.format,
                              "title": media["metadata"]["title"],
                              "duration_seconds": media["duration_seconds"],
                              "width": media["width"], "height": media["height"],
                              "fps": media["fps"], "voice": media["voice"],
                              "audio": checks[episode.id]["audio"],
                              "source_fingerprint": checks[episode.id]["source_fingerprint"]})
        # Catch edits occurring during extraction/copy without re-rendering anything.
        for episode in manifest.episodes:
            row = next(item for item in report["episodes"] if item["id"] == episode.id)
            if (source_fingerprint(episode, manifest)[0] != row["source_fingerprint"]
                    or deliverable_hashes(episode) != row["deliverable_hashes"]):
                raise ValueError(f"{episode.id}: inputs changed while exporting")
        if sha256(manifest.report_path) != report_hash or sha256(manifest.path) != manifest_hash:
            raise ValueError("Batch manifest/report changed while exporting")
        (staging / "UPLOAD_ALL.md").write_text("\n".join(combined), encoding="utf-8")
        (staging / "README.md").write_text(
            "# BizNex first six\n\nSix verified 1080x1920 / 30 fps MP4s, matching thumbnails, "
            "upload copy and speech-aligned captions. Each episode has its own folder.\n\n"
            "Voice: Kokoro af_heart; pace and pauses are directed, semantic emotion is not verified. "
            "Music and foley use original procedural synthesis. These are fictional educational "
            "stories, not testimonials or predicted results.\n\n"
            "Read UPLOAD_ALL.md before publication. This export performs no posting. "
            "DELIVERY_MANIFEST.json records source/delivery hashes and technical checks; "
            "SHA256SUMS.txt covers every other packaged file.\n", encoding="utf-8")
        write_json(staging / "DELIVERY_MANIFEST.json", {
            "schema_version": 1, "batch_id": manifest.batch_id, "status": "verified",
            "source_manifest": manifest.path.relative_to(root).as_posix(),
            "source_manifest_sha256": manifest_hash, "verification_report_sha256": report_hash,
            "episodes": summaries, "files": exported,
            "published_by_packager": False, "emotion_fidelity_verified": False,
        })
        hashes = [f"{sha256(path)}  {path.relative_to(staging).as_posix()}"
                  for path in sorted(staging.rglob("*")) if path.is_file()]
        (staging / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
        staged_zip = Path(temporary) / archive.name
        archive_directory(staging, staged_zip)
        staging.rename(destination)
        staged_zip.rename(archive)
    digest = sha256(archive)
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return {"directory": str(destination), "archive": str(archive), "sha256": digest}


def contact_sheet(manifest_path: Path, *, episode_ids: list[str] | None = None,
                  root: Path = ROOT) -> Path:
    """Sample decoded final-video frames, explicitly separate from delivery verification."""
    root = root.resolve()
    manifest = load_production_batch_manifest(manifest_path, repository_root=root)
    selected = [ep for ep in manifest.episodes if not episode_ids or ep.id in episode_ids]
    if not selected or (episode_ids and set(episode_ids) != {ep.id for ep in selected}):
        raise ValueError("Unknown or empty episode selection")
    output = (root / "output/deliveries/biznex-first-six-review").resolve()
    if not output.is_relative_to(root / "output"):
        raise ValueError("Review output must remain inside repository output")
    output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=19)
    tile_width, tile_height, row_height = 270, 480, 550
    sheet = Image.new("RGB", (850, len(selected) * row_height + 60), "#15191f")
    draw = ImageDraw.Draw(sheet)
    draw.text((15, 15), "ACTUAL VIDEO FRAMES | visual review, not a delivery approval", font=font, fill="white")
    samples = []
    for row, episode in enumerate(selected):
        if not episode.output.is_file():
            raise ValueError(f"{episode.id}: final.mp4 does not exist")
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "json", str(episode.output)], check=True,
                               capture_output=True, text=True, timeout=30)
        duration = float(json.loads(probe.stdout)["format"]["duration"])
        y = 60 + row * row_height
        draw.text((15, y), f"{episode.id} | {duration:.3f}s", font=font, fill="white")
        for column, fraction in enumerate((0.10, 0.50, 0.85)):
            at = duration * fraction
            frame = output / f"{episode.id}-{column+1}.png"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(episode.output), "-ss", f"{at:.6f}", "-frames:v", "1",
                            "-vf", f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=decrease",
                            str(frame)], check=True, capture_output=True, timeout=60)
            with Image.open(frame) as source:
                panel = source.convert("RGB")
                sheet.paste(panel, (15 + column * 280, y + 30))
            draw.text((15 + column * 280, y + 515), f"{at:.3f}s", font=font, fill="#b7c5d8")
            samples.append({"episode_id": episode.id, "at_seconds": round(at, 6),
                            "frame": frame.name, "video_sha256": sha256(episode.output)})
    destination = output / "contact-sheet.png"
    sheet.save(destination)
    write_json(output / "frames.json", {"status": "visual_review_only", "samples": samples})
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("package", "contact-sheet"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--episodes", nargs="+", help="Contact-sheet selection only")
    args = parser.parse_args()
    if args.command == "package":
        if args.episodes:
            parser.error("Package export always requires all six; --episodes is review-only")
        print(json.dumps(package_delivery(args.manifest), indent=2))
    else:
        print(contact_sheet(args.manifest, episode_ids=args.episodes))


if __name__ == "__main__":
    main()
