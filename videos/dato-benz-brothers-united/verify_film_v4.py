"""Verify V4 image-only provenance, frozen lyric clock and encoded delivery.

Preflight inspects source/plan/build artifacts only. Full verification requires
an explicitly supplied completed file. A technical pass is not client acceptance,
likeness recognition, a listening review, or a claim of native generated video.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import correlate, correlation_lags

from prepare_film import ffmpeg, probe, read_json, sha256, write_json

ROOT = Path(__file__).resolve().parent
RENDERER = ROOT / "v4-renderer"
QA = ROOT / "renders/v4/qa"
FPS, WIDTH, HEIGHT, FRAMES, DURATION, SAMPLE_RATE = 24, 1920, 1080, 4723, 196.760, 48000
AUDIO_SHA = "60ee65f074f36b2d31660bee652e111cd84538e51b74a0685cbd895291cd6547"
CAPTION_SHA = "6d3a6b8f711526f7944b5d391cb16340fd1e17db761d1dd41b4d76598a75bd10"
PHOTO_ORIGINALS = {
    "assets/references-v3/originals/photo_2026-11-19_17-27-29.jpg": {
        "sha256": "e2c23d422b02ad1a8188069c91c65b46321f781e0f93832122c5a362e12ef497",
        "original_filename": "photo_2026-11-19_17-27-29.jpg", "dimensions": [960, 1280]},
    "assets/photos/brothers.jpg": {
        "sha256": "f689bf5ee345970581f6839c0afbc8b8347fd06b9454732680452e79e2e901ae",
        "original_filename": "photo_2026-11-19_14-36-56.jpg", "dimensions": [1280, 853]},
    "assets/photos/seaside.jpg": {
        "sha256": "f82de273f4ca26487851dd402ecc7557c190c5f4af1c6dbeaca69f0fefa55b71",
        "original_filename": "photo_2026-11-19_14-36-47.jpg", "dimensions": [960, 1280]},
}
NAME_STARTS = (29.54, 81.04, 90.42, 149.32, 154.8, 158.4)
VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".gif"}
ART_NAME = re.compile(r"^(?:0[1-9]|1[0-8])-[a-z0-9-]+\.png$")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command, timeout=900):
    result = subprocess.run([str(x) for x in command], capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-3500:])
    return result.stdout


def local(value: str, base: Path = ROOT) -> Path:
    require(isinstance(value, str) and not re.match(r"^[a-z]+://", value, re.I),
            f"Remote or invalid input path: {value}")
    path = (base / value).resolve()
    require(path.is_relative_to(base.resolve()) and path.is_file(), f"Missing/outside local input: {value}")
    return path


def paths_in(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from paths_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from paths_in(child)
    elif isinstance(value, str) and Path(value).suffix.lower() in VIDEO_SUFFIXES:
        yield value


class CompositionHTML(HTMLParser):
    """Read authored cue DOM without executing the renderer or JavaScript."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cues, self.audio, self.videos, self.root = [], [], [], None
        self._cue, self._depth = None, 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "video":
            self.videos.append(attrs)
        if tag == "audio":
            self.audio.append(attrs)
        if attrs.get("id") == "root":
            self.root = attrs
        if self._cue is not None:
            self._depth += 1
        elif tag == "div" and re.fullmatch(r"cue-\d+", attrs.get("id", "")):
            self._cue, self._depth = {"attrs": attrs, "text": ""}, 1

    def handle_data(self, text):
        if self._cue is not None:
            self._cue["text"] += text

    def handle_endtag(self, tag):
        if self._cue is not None:
            self._depth -= 1
            if self._depth == 0:
                self.cues.append(self._cue)
                self._cue = None


def crop_check(scene, layer):
    path = local(layer["src"])
    require(layer["src"] in PHOTO_ORIGINALS, f"Unapproved/generated human photo in {scene['id']}")
    original = PHOTO_ORIGINALS[layer["src"]]
    require(sha256(path) == original["sha256"], f"Original photo bytes changed: {path.name}")
    with Image.open(path) as image:
        width, height = image.size
    require([width, height] == original["dimensions"], f"Photo source dimensions changed: {path.name}")
    crop = layer.get("crop", [0, 0, width, height])
    require(isinstance(crop, list) and len(crop) == 4 and all(math.isfinite(v) for v in crop),
            f"Invalid literal photo crop in {scene['id']}")
    x, y, cw, ch = crop
    require(x >= 0 and y >= 0 and cw > 0 and ch > 0 and x + cw <= width and y + ch <= height,
            f"Out-of-bounds photo crop in {scene['id']}")
    output_height = float(layer.get("height", 7))
    output_width = float(layer.get("width", output_height * cw / ch))
    require(output_height > 0 and output_width > 0 and abs(output_width / output_height - cw / ch) <= .002,
            f"Photo aspect ratio would stretch in {scene['id']}")
    forbidden = {"depthSrc", "depth", "depthMap", "depthStrength", "displacementMap", "displacement",
                 "warp", "morph", "filter", "filters", "retouch", "faceRestore", "colorGrade"}
    require(not forbidden.intersection(layer), f"Photo deformation/retouch field in {scene['id']}")
    require(not layer.get("rotation"), f"Photo rotation field requires explicit separate review: {scene['id']}")
    for endpoint in (layer.get("from", {}), layer.get("to", {})):
        if isinstance(endpoint, dict):
            require(endpoint.get("opacity", 1) == 1, f"Photo opacity changes in {scene['id']}")
    return {"scene": scene["id"], "source": layer["src"], "source_sha256": original["sha256"],
            "original_filename": original["original_filename"], "dimensions": [width, height],
            "literal_crop": crop, "display_aspect_ratio": output_width / output_height,
            "depth_on_photo": False}


def preflight():
    plan_path, cue_path = ROOT / "edit-plan-v4.json", ROOT / "captions.json"
    plan, cues = read_json(plan_path), read_json(cue_path)
    require(sha256(ROOT / "assets/bgm.wav") == AUDIO_SHA == plan["original_audio_sha256"],
            "Frozen original soundtrack SHA-256 changed")
    require(sha256(cue_path) == CAPTION_SHA == plan["canonical_caption_sha256"],
            "Frozen canonical caption SHA-256 changed")
    require(len(cues) == 40, "Expected exactly 40 canonical lyric cues")
    previous = 0.
    for cue in cues:
        require(previous <= cue["start"] < cue["end"] <= DURATION, "Canonical cue order/bounds failed")
        previous = cue["end"]
    require((plan["width"], plan["height"], plan["fps"]) == (WIDTH, HEIGHT, FPS)
            and abs(plan["duration"] - DURATION) < 1e-9, "V4 canvas/song clock changed")
    require(plan.get("native_ai_video") is False and plan.get("generated_humans") is False,
            "V4 must declare image-only/no generated human pixels")
    require(not list(paths_in(plan)), "Video input found in image-only V4 plan")
    scenes = plan["scenes"]
    require(len(scenes) == 54 and len({s["id"] for s in scenes}) == 54, "Expected 54 unique V4 shots")
    artwork = read_json(ROOT / "artwork-v4.json")
    require(artwork.get("native_ai_video") is False and artwork.get("generated_human_pixels") is False
            and artwork.get("private_photo_uploads_this_version") == 0, "V4 art provenance violates identity policy")
    art_records = {record["path"]: record for record in artwork["records"]}
    depth_records = read_json(ROOT / "depth-provenance-v4.json")["depths"]
    # Exact worker execution ledgers supplement the root manifest; authored
    # storyboard prompts alone are not execution provenance.
    ledgers = list(dict.fromkeys([*artwork.get("additional_prompt_ledgers", []),
                                 "art-v4-worker-a.json", "art-v4-worker-b.json"]))
    for value in ledgers:
        ledger = read_json(local(value))
        constraints = ledger.get("constraints", {})
        if isinstance(constraints, dict) and constraints.get("human_reference_photos_used") is False:
            for record in ledger.get("assets", []):
                if isinstance(record, dict) and record.get("path") and record.get("sha256"):
                    art_records[record["path"]] = {**record, "human_reference_input": False,
                                                   "provenance_basis": value}
    used_paths, photos, previous = set(), [], 0.
    for scene in scenes:
        require(abs(scene["start"] - previous) < 1e-7 and scene["end"] > scene["start"],
                f"Gap/overlap or reversed shot: {scene['id']}")
        previous = scene["end"]
        source = scene["src"]
        require(Path(source).parent.as_posix() == "assets/art-v4" and ART_NAME.fullmatch(Path(source).name),
                f"Non-art background plate: {source}")
        for value in [source, *(layer["src"] for layer in scene.get("layers", []) if layer.get("kind", "art") == "art")]:
            require(value in art_records and art_records[value].get("human_reference_input") is False,
                    f"Unproven nonhuman generated-art input: {value}")
            require(sha256(local(value)) == art_records[value]["sha256"], f"Art provenance hash changed: {value}")
            used_paths.add(value)
        if scene.get("depthSrc"):
            record = depth_records.get(Path(source).stem)
            require(record and record["source_path"] == source and record["path"] == scene["depthSrc"],
                    f"Background/depth binding mismatch in {scene['id']}")
            require(record["source_sha256"] == sha256(local(source))
                    and record["depth_sha256"] == sha256(local(scene["depthSrc"])),
                    f"Depth provenance hash mismatch in {scene['id']}")
            require(0 <= float(scene.get("depthStrength", .4)) <= .8, "Unrestrained depth strength")
            used_paths.add(scene["depthSrc"])
        for layer in scene.get("layers", []):
            require(layer.get("kind", "art") in {"art", "photo"}, "Non-image V4 layer")
            used_paths.add(layer["src"])
            if layer.get("kind") == "photo":
                photos.append(crop_check(scene, layer))
            else:
                require(Path(layer["src"]).parent.as_posix() == "assets/art-v4", "Non-art foreground")
    require(abs(previous - DURATION) < 1e-9 and math.ceil(previous * FPS) == FRAMES,
            "V4 shots do not cover the complete 196.760-second song / 4723-frame export")
    names = [c for c in cues if "Hock Siew" in c["text"] or "谢惠福" in c["text"]]
    require(len(names) == len(NAME_STARTS) and all(abs(a["start"] - b) < 1e-8 for a, b in zip(names, NAME_STARTS)),
            "Expected six frozen Hock Siew/name anchors")
    coverage = []
    for cue in names:
        cursor, covered = cue["start"], []
        for scene in scenes:
            if scene["end"] <= cursor or scene["start"] >= cue["end"]:
                continue
            if scene["start"] > cursor + 1e-7:
                break
            if not any(layer.get("kind") == "photo" for layer in scene.get("layers", [])):
                break
            require(scene.get("transition", {}).get("kind", "cut") == "cut",
                    f"Photo name interval has a partial entry transition: {scene['id']}")
            covered.append(scene["id"])
            cursor = min(cue["end"], scene["end"])
            if cursor >= cue["end"] - 1e-7:
                break
        require(cursor >= cue["end"] - 1e-7, f"Entire name cue lacks authentic photo coverage: {cue['start']}")
        coverage.append({"start": cue["start"], "end": cue["end"], "text": cue["text"],
                         "photo_shots": covered, "complete_interval_covered": True})
    receipt_path = RENDERER / "build-receipt.json"
    receipt = read_json(receipt_path)
    require(receipt["plan_sha256"] == sha256(plan_path) and receipt["scene_count"] == 54
            and receipt["cue_count"] == 40 and receipt.get("native_ai_video") is False,
            "Renderer build receipt is stale or incompatible")
    copies, frozen = {}, []
    for item in receipt["inputs"]:
        original = local(item["source"])
        require(original.suffix.lower() not in VIDEO_SUFFIXES, "Video found in build inputs")
        checksum = sha256(original)
        require(checksum == item["sha256"] and original.stat().st_size == item["bytes"],
                f"Build source hash/size changed: {item['source']}")
        if item.get("local"):
            target = local(item["local"], RENDERER)
            require(sha256(target) == checksum and target.stat().st_size == item["bytes"],
                    f"Renderer copied bytes differ: {item['local']}")
            copies[item["source"]] = item["local"]
        frozen.append({"source": item["source"], "local": item.get("local"), "sha256": checksum})
    require(used_paths | {plan["audio"], plan["captions"]} <= {i["source"] for i in receipt["inputs"]},
            "A plan input is absent from frozen build receipt")
    for item in receipt["vendors"] + receipt["sources"]:
        require(sha256(local(item["path"], RENDERER)) == item["sha256"],
                f"Renderer/vendor source changed after build: {item['path']}")
    html_path = RENDERER / "index.html"
    html = html_path.read_text(encoding="utf-8")
    parsed = CompositionHTML()
    parsed.feed(html)
    require(not parsed.videos and len(parsed.audio) == 1 and len(parsed.cues) == 40,
            "DOM must contain one canonical audio, no video and 40 cues")
    for index, (node, cue) in enumerate(zip(parsed.cues, cues)):
        attrs = node["attrs"]
        require(attrs["id"] == f"cue-{index}" and node["text"] == cue["text"]
                and abs(float(attrs["data-start"]) - cue["start"]) < 1e-8
                and abs(float(attrs["data-duration"]) - (cue["end"] - cue["start"])) < 1e-8,
                f"DOM lyric text/timing differs at cue {index}")
    require(parsed.audio[0]["src"] == copies[plan["audio"]]
            and float(parsed.audio[0]["data-start"]) == 0
            and abs(float(parsed.audio[0]["data-duration"]) - DURATION) < 1e-8,
            "DOM original song binding differs")
    embedded, _ = json.JSONDecoder().raw_decode(html.split("window.V4_PLAN=", 1)[1])
    expected = copy.deepcopy(plan)
    expected["captions"] = cues
    expected["audio"] = copies[plan["audio"]]
    for scene in expected["scenes"]:
        for field in ("src", "depthSrc"):
            if scene.get(field):
                scene[field] = copies[scene[field]]
        for layer in scene.get("layers", []):
            layer["src"] = copies[layer["src"]]
        if scene.get("transition", {}).get("mask"):
            scene["transition"]["mask"] = copies[scene["transition"]["mask"]]
    require(embedded == expected, "Embedded render plan/cues differs from frozen source plan")
    renderer = (RENDERER / "renderer.mjs").read_text(encoding="utf-8")
    require("photo.quaternion.copy(item.camera.quaternion)" in renderer
            and "Photo ${l.id||''} would be stretched" in renderer,
            "Renderer photo-facing/aspect guard no longer present")
    return plan, cues, {
        "passed": True, "stage": "source_plan_build_preflight", "shots": 54,
        "caption_cues": 40, "duration_seconds": DURATION, "expected_frames": FRAMES,
        "song_sha256": AUDIO_SHA, "canonical_captions_sha256": CAPTION_SHA,
        "plan_sha256": sha256(plan_path), "build_receipt_sha256": sha256(receipt_path),
        "index_sha256": sha256(html_path), "dom_cue_text_and_timing_exact": True,
        "embedded_plan_exact": True, "image_only_input_paths": True,
        "artwork_no_human_reference_provenance": True,
        "semantic_limits": "Path/hash/provenance checks cannot algorithmically prove that no person-like shape exists in generated art; visual review remains separate.",
        "photo_layers": photos, "name_cue_coverage": coverage,
        "frozen_inputs": frozen, "visual_acceptance": "not assessed",
    }


def stereo(path):
    data = run([ffmpeg(), "-v", "error", "-xerror", "-i", path, "-map", "0:a:0", "-vn",
                "-ac", "2", "-ar", SAMPLE_RATE, "-f", "f32le", "-"])
    return np.frombuffer(data, dtype="<f4").reshape((-1, 2))


def audio_check(video):
    original, encoded = stereo(ROOT / "assets/bgm.wav"), stereo(video)
    require(len(original) == round(DURATION * SAMPLE_RATE), "Original source sample clock changed")
    require(abs(len(original) - len(encoded)) <= 1024, "Encoded audio sample count differs beyond AAC padding")
    count = min(len(original), len(encoded))
    correlations, gains = [], []
    for channel in range(2):
        x, y = original[:count, channel].astype(np.float64), encoded[:count, channel].astype(np.float64)
        correlations.append(float(np.corrcoef(x, y)[0, 1]))
        gain = float(np.dot(x, y) / np.dot(x, x))
        gains.append(20 * math.log10(gain) if gain > 0 else float("-inf"))
    require(all(math.isfinite(v) and v >= .98 for v in correlations), "Zero-offset original-song correlation failed")
    require(all(math.isfinite(v) and abs(v) <= .15 for v in gains), "Original-song gain changed")
    lag_samples = []
    for at in (24., 82., 140., 180.):
        a, b = round(at * SAMPLE_RATE), round((at + 3) * SAMPLE_RATE)
        for channel in range(2):
            x, y = original[a:b, channel].astype(np.float64), encoded[a:b, channel].astype(np.float64)
            x -= x.mean(); y -= y.mean()
            response = correlate(y, x, mode="full", method="fft")
            lags = correlation_lags(len(y), len(x), mode="full")
            window = np.abs(lags) <= 2400
            best = int(lags[window][np.argmax(response[window])])
            require(abs(best) <= 1, f"Measured song lag differs at {at}s / channel {channel}: {best} samples")
            lag_samples.append({"start_seconds": at, "length_seconds": 3, "channel": channel,
                                "best_lag_samples": best, "search_window_samples": [-2400, 2400]})
    payload = run([ffmpeg(), "-v", "error", "-i", video, "-map", "0:a:0", "-c:a", "copy", "-f", "adts", "-"])
    return {"zero_offset_compared_samples_per_channel": count, "original_samples": len(original),
            "encoded_samples": len(encoded), "per_channel_correlation": correlations,
            "per_channel_gain_db": gains, "minimum_correlation": .98, "gain_tolerance_db": .15,
            "lag_checks": lag_samples, "lag_tolerance_samples": 1,
            "encoded_aac_sha256": hashlib.sha256(payload).hexdigest(),
            "limits": "Signal correspondence and sampled local lag; not a human listening review or independent proof of vocal alignment."}


def frame(video, at):
    raw = run([ffmpeg(), "-v", "error", "-ss", f"{at:.9f}", "-i", video,
               "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"])
    return Image.open(io.BytesIO(raw)).convert("RGB")


def contact_sheets(video, plan, cues):
    QA.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(ROOT / "assets/fonts/NotoSerifCJKsc-Regular.otf"), 18)
    pages = []
    for offset in range(0, 54, 16):
        scenes = plan["scenes"][offset:offset + 16]
        sheet = Image.new("RGB", (1920, 48 + math.ceil(len(scenes) / 4) * 325), "#10272b")
        draw = ImageDraw.Draw(sheet)
        draw.text((14, 9), f"V4 actual encoded frames / shots {offset + 1}–{offset + len(scenes)}", font=font, fill="#f3ddad")
        for slot, scene in enumerate(scenes):
            at = math.floor((scene["start"] + scene["end"]) / 2 * FPS) / FPS
            image = frame(video, at)
            x, y = slot % 4 * 480, 48 + slot // 4 * 325
            sheet.paste(image.resize((480, 270), Image.Resampling.LANCZOS), (x, y))
            draw.text((x + 8, y + 273), f"{scene['id']} / {at:.3f}s", font=font, fill="#f3ddad")
            lyric = next((cue["text"] for cue in cues if cue["start"] <= at < cue["end"]), "[instrumental / dedication]")
            draw.text((x + 8, y + 299), lyric, font=font, fill="white")
        target = QA / f"shot-midpoints-{offset // 16 + 1:02}.png"
        sheet.save(target)
        pages.append(target.relative_to(ROOT).as_posix())
    names = [cue for cue in cues if any(abs(cue["start"] - at) < 1e-8 for at in NAME_STARTS)]
    proof = Image.new("RGB", (1920, 6 * 390 + 48), "#10272b")
    draw = ImageDraw.Draw(proof)
    draw.text((14, 9), "V4 encoded name anchors / first, middle, last frame inside each cue", font=font, fill="#f3ddad")
    full = []
    for row, cue in enumerate(names):
        samples = [math.ceil(cue["start"] * FPS) / FPS,
                   math.floor((cue["start"] + cue["end"]) / 2 * FPS) / FPS,
                   (math.ceil(cue["end"] * FPS) - 1) / FPS]
        for col, at in enumerate(samples):
            image = frame(video, at)
            target = QA / f"name-anchor-{row + 1:02}-{('first','middle','last')[col]}.png"
            image.save(target)
            full.append(target.relative_to(ROOT).as_posix())
            x, y = col * 640, 48 + row * 390
            proof.paste(image.resize((640, 360), Image.Resampling.LANCZOS), (x, y))
            draw.text((x + 8, y + 363), f"{at:.3f}s / {cue['text']}", font=font, fill="#f3ddad")
    proof.save(QA / "name-anchors.png")
    frame(video, 1.5).save(QA / "opening-authentic-photo.png")
    frame(video, DURATION - 4).save(QA / "closing-dedication.png")
    return {"shot_midpoint_sheets": pages, "sampled_shots": 54, "name_anchor_full_frames": full,
            "name_anchor_sheet": (QA / "name-anchors.png").relative_to(ROOT).as_posix(),
            "closing_dedication": (QA / "closing-dedication.png").relative_to(ROOT).as_posix(),
            "review_status": "technical capture only; pending visual review; no client acceptance claimed"}


def verify(video, make_sheets=False):
    require(video.is_file(), f"Completed master file not found: {video}")
    plan, cues, source_checks = preflight()
    metadata = probe(video)
    pictures = [s for s in metadata["streams"] if s.get("codec_type") == "video"]
    sound = [s for s in metadata["streams"] if s.get("codec_type") == "audio"]
    require(len(pictures) == len(sound) == 1, "Expected exactly one video and one original-song audio stream")
    v, a = pictures[0], sound[0]
    require((v["width"], v["height"]) == (WIDTH, HEIGHT) and Fraction(v["avg_frame_rate"]) == FPS
            and v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p", "Wrong 1080p24 H.264 format")
    require(a["codec_name"] == "aac" and a["channels"] == 2 and int(a["sample_rate"]) == SAMPLE_RATE,
            "Wrong stereo48k AAC soundtrack format")
    require(abs(float(v.get("start_time", 0))) < 1e-6 and abs(float(a.get("start_time", 0))) < 1e-6,
            "Picture/audio clock does not start at zero")
    require(abs(float(metadata["format"]["duration"]) - DURATION) <= 1 / FPS + .001,
            "Container duration differs beyond one 24fps frame")
    require(int(v.get("nb_frames", FRAMES)) == FRAMES, "Stream frame count differs from4723")
    progress = run([ffmpeg(), "-v", "error", "-xerror", "-i", video, "-map", "0:v:0", "-map", "0:a:0",
                    "-progress", "pipe:1", "-nostats", "-f", "null", "-"]).decode("utf-8")
    counts = re.findall(r"^frame=(\d+)$", progress, re.M)
    require(counts and int(counts[-1]) == FRAMES and "progress=end" in progress,
            "Every-frame video/audio decode did not complete with4723 frames")
    audio = audio_check(video)
    result = {"passed": True, "stage": "full_encoded_technical_verification",
              "verified_at_utc": datetime.now(timezone.utc).isoformat(),
              "file": str(video), "sha256": sha256(video), "bytes": video.stat().st_size,
              "width": WIDTH, "height": HEIGHT, "fps": FPS, "frames": int(counts[-1]),
              "duration_seconds": float(metadata["format"]["duration"]), "source_song_seconds": DURATION,
              "frame_rounding_seconds": FRAMES / FPS - DURATION,
              "full_video_audio_decode": True, "audio": audio, "preflight": source_checks,
              "ffmpeg_binary": ffmpeg(), "ffmpeg_version": run([ffmpeg(), "-version"]).decode().splitlines()[0],
              "ffprobe_version": run(["ffprobe", "-version"]).decode().splitlines()[0],
              "native_ai_video": False, "generated_human_pixels": False,
              "acceptance_status": "not assessed; technical pass does not imply visual/client approval",
              "limits": ["Monocular artwork depth is estimated2.5D, not true geometry.",
                         "Source bytes/crop/aspect are checked; displayed pixels are scaled/resampled during composition.",
                         "DOM checks prove authored text/time, not OCR readability of every encoded frame.",
                         "Contact sheets are samples; human review is required for appearance, edit quality and emotional effect."]}
    if make_sheets:
        result["encoded_visual_samples"] = contact_sheets(video, plan, cues)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="Completed full master MP4; never inferred from partial renders")
    parser.add_argument("--preflight", action="store_true", help="Only source/plan/build checks; no video opened")
    parser.add_argument("--contact-sheets", action="store_true", help="Capture encoded shot/name/dedication PNGs")
    args = parser.parse_args()
    if not args.preflight and args.file is None:
        parser.error("Use --preflight or --file path-to-completed-master.mp4")
    QA.mkdir(parents=True, exist_ok=True)
    target = QA / ("source-preflight.json" if args.preflight else "technical-verification.json")
    try:
        result = preflight()[2] if args.preflight else verify(args.file.resolve(), args.contact_sheets)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired, IndexError) as error:
        result = {"passed": False, "stage": "source_plan_build_preflight" if args.preflight else "full_encoded_technical_verification",
                  "error": str(error), "file": str(args.file) if args.file else None,
                  "verified_at_utc": datetime.now(timezone.utc).isoformat(), "acceptance_status": "not assessed"}
    write_json(target, result)
    print(json.dumps({key: result.get(key) for key in ("passed", "stage", "error", "frames", "shots", "caption_cues")}, indent=2))
    print(f"Receipt: {target}")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
