"""Create one validated delivery ZIP and a labelled visual review sheet."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from daily_video_factory.shorts_delivery import validate_short_delivery

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--creative", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.creative.read_text(encoding="utf-8"))
    out = ROOT / "output" / spec["batch_id"]
    out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 21)
    small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
    sheet = Image.new("RGB", (1600, 1950), "#151515")
    draw = ImageDraw.Draw(sheet)
    package_text = ["# BizNex: four Atomy Quick Truths\n", "Voice: approved Kokoro af_heart. Format: portrait 1080×1920 / 30 fps.\n"]
    summary = []
    files = []
    for row, ep in enumerate(spec["episodes"]):
        project = (ROOT / ep["project"]).resolve()
        project.relative_to(ROOT / "videos")
        video = project / "renders/final.mp4"
        thumb = project / "assets/thumbnails/thumbnail.png"
        validate_short_delivery(
            video, thumb, upload_package=project / "UPLOAD_PACKAGE.md",
            voice_manifest=project / "audio_request.json", expected_voice="af_heart",
        )
        meta = json.loads((project / "audio_meta.json").read_text())
        total = meta["total_duration_s"]
        draw.text((18, row * 480 + 8), f"{row + 1:02}  {ep['id']}  |  01-explainer  |  {total:.1f}s  |  af_heart", font=font, fill="white")
        snapshots = sorted((project / "snapshots").glob("frame-*-at-*.png"))
        if len(snapshots) < 5:
            raise ValueError(f"{ep['id']}: missing five-state browser review")
        # Thumbnail followed by four sampled internal scene states, when available.
        previews = [thumb] + [snapshots[i] for i in (0, 1, 2, 4)]
        for col, path in enumerate(previews):
            with Image.open(path) as source:
                panel = source.convert("RGB")
                panel.thumbnail((300, 400))
                sheet.paste(panel, (18 + col * 316, row * 480 + 47))
            draw.text((18 + col * 316, row * 480 + 452), "THUMBNAIL" if col == 0 else f"SCENE {col}", font=small, fill="#dddddd")
        package_text.extend([f"\n## {row + 1}. {ep['title']}\n", f"Length: {total:.3f}s\n",
                             f"\n{ep['description']}\n", "\n" + " ".join(ep["hashtags"]) + "\n"])
        summary.append({"id": ep["id"], "project": ep["project"], "duration_seconds": total,
                        "voice": "af_heart", "delivery_passed": True,
                        "video": f"{ep['id']}/final.mp4", "thumbnail": f"{ep['id']}/thumbnail.png"})
        files.extend([(video, f"{ep['id']}/final.mp4"), (thumb, f"{ep['id']}/thumbnail.png"),
                      (project / "UPLOAD_PACKAGE.md", f"{ep['id']}/UPLOAD_PACKAGE.md")])
    review = out / "batch-review.png"
    sheet.save(review)
    text = out / "UPLOAD_ALL.md"
    text.write_text("\n".join(package_text), encoding="utf-8")
    validation = out / "DELIVERY_SUMMARY.json"
    validation.write_text(json.dumps({"batch_id": spec["batch_id"], "episodes": summary}, indent=2) + "\n", encoding="utf-8")
    archive = out / "biznex-four-shorts.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as delivery:
        for path, name in files:
            delivery.write(path, name)
        for path in (text, validation, review):
            delivery.write(path, path.name)
    print(f"Package: {archive}\nReview: {review}\nMetadata: {text}")


if __name__ == "__main__":
    main()
