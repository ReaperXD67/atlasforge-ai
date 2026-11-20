"""Generate local CPU relative-depth maps for numbered V4 nonhuman artwork only.

Adapted from ../bosston-pragon-good-fortune/generate_ai_depth.py; keeps the
Apache-2.0 Small model, pinned tensors, explicit DINOv2 architecture and 2–98
percentile normalization. Estimated 2.5D is not true geometry or generated video.
No network calls, provider uploads, real-person photos or alpha foregrounds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from safetensors.torch import load_file
from transformers.models.depth_anything.configuration_depth_anything import DepthAnythingConfig
from transformers.models.depth_anything.modeling_depth_anything import (
    DepthAnythingForDepthEstimation,
    DepthAnythingNeck,
    DepthAnythingDepthEstimationHead,
    DepthAnythingPreTrainedModel,
)
from transformers.models.dinov2.modeling_dinov2 import Dinov2Backbone

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ART = (ROOT / "assets/art-v4").resolve()
OUT = ROOT / "assets/depth-v4"
REPORT = ROOT / "depth-provenance-v4.json"
UPSTREAM_SCRIPT = REPO / "videos/bosston-pragon-good-fortune/generate_ai_depth.py"
MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"
CACHE = REPO / "output/bosston-ai-v3/depth/model" / REVISION
LICENSE_URL = "https://raw.githubusercontent.com/DepthAnything/Depth-Anything-V2/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf/LICENSE"
LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
MODEL_HASHES = {
    "config.json": "c56698d3643dde1f83ea2212759e6b31a22b8f827246a36dd007ee8a22b3ff75",
    "preprocessor_config.json": "d41175c0d889477ca8fc67191e540faef14baf6275157b3fdecf78469e6bbf84",
    "model.safetensors": "3152477ce0d8d6978d76b995120de97cb5b928701fd0f817769f59e249a16b70",
    "README.md": "319566441daaac0c5ed83e75a8fd19bae0863f3275e23f147c06fe0906edf6fb",
}
ART_NAME = re.compile(r"^(0[1-9]|1[0-8])-[a-z0-9-]+\.png$")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class ExplicitDepthAnything(DepthAnythingForDepthEstimation):
    """Same installed Apache-2.0 forward/layers and checkpoint tensors as upstream."""

    def __init__(self, config):
        DepthAnythingPreTrainedModel.__init__(self, config)
        self.backbone = Dinov2Backbone(config.backbone_config)
        self.neck = DepthAnythingNeck(config)
        self.head = DepthAnythingDepthEstimationHead(config)
        self.post_init()


def assert_art(path: Path) -> tuple[str, tuple[int, int]]:
    path = path.resolve(strict=True)
    if path.parent != ART or not ART_NAME.fullmatch(path.name):
        raise ValueError(f"Only numbered 01–18 nonhuman art-v4 PNG inputs allowed: {path}")
    with Image.open(path) as image:
        if image.format != "PNG":
            raise ValueError(f"Artwork must be PNG: {path}")
        if "transparency" in image.info or (
            "A" in image.getbands() and image.getchannel("A").getextrema() != (255, 255)
        ):
            raise ValueError(f"Transparent foregrounds are prohibited: {path}")
        if image.width < 256 or image.height < 256:
            raise ValueError(f"Artwork is unexpectedly small: {path}")
        return digest(path), image.size


def publish(report: dict) -> None:
    report["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["depth_count"] = len(report["depths"])
    report["expected_scene_count"] = 18
    present = {int(stem[:2]) for stem in report["depths"]}
    report["missing_scene_indices"] = sorted(set(range(1, 19)) - present)
    report["total_map_inference_seconds"] = round(
        sum(record["inference_seconds"] for record in report["depths"].values()), 3
    )
    temporary = REPORT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plates", nargs="*", type=Path,
                        help="Optional explicit inputs, still restricted to assets/art-v4/01–18*.png")
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.threads <= 32:
        raise ValueError("CPU threads must be between 1 and 32")
    started = time.perf_counter()
    selected = sorted(args.plates or [p for p in ART.glob("*.png") if ART_NAME.fullmatch(p.name)])
    if not selected:
        raise ValueError("No numbered artwork inputs are present")
    sources = {}
    indices = set()
    for plate in selected:
        plate = plate.resolve()
        checksum, size = assert_art(plate)
        index = int(plate.name[:2])
        if index in indices:
            raise ValueError(f"Duplicate artwork scene number: {index}")
        indices.add(index)
        sources[plate.stem] = (plate, checksum, size)
    downloads = []
    for name, expected in MODEL_HASHES.items():
        model_file = CACHE / name
        if not model_file.is_file() or digest(model_file) != expected:
            raise ValueError(f"Pinned cached model missing or checksum changed: {model_file}")
        downloads.append({"file": name, "sha256": expected,
                          "size_bytes": model_file.stat().st_size, "reused": True})
    license_source = REPO / "output/bosston-ai-v3/depth/LICENSE-DepthAnything.txt"
    if not license_source.is_file() or digest(license_source) != LICENSE_SHA256:
        raise ValueError("Pinned cached Apache-2.0 license missing or changed")
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(license_source, OUT / "LICENSE-DepthAnything.txt")
    existing = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.is_file() else {}
    records = existing.get("depths", {})
    pending = []
    skipped = []
    for stem, (plate, checksum, size) in sources.items():
        target = OUT / f"{stem}.png"
        record = records.get(stem, {})
        if (record.get("source_sha256") == checksum and record.get("model_revision") == REVISION
                and [record.get("width"), record.get("height")] == list(size)
                and target.is_file() and record.get("depth_sha256") == digest(target)):
            skipped.append(stem)
        else:
            pending.append(stem)
    report = {
        "schema_version": 1,
        "model": MODEL_ID, "revision": REVISION,
        "model_url": f"https://huggingface.co/{MODEL_ID}/tree/{REVISION}",
        "license": "Apache-2.0", "license_url": LICENSE_URL,
        "license_sha256": LICENSE_SHA256,
        "license_file": "assets/depth-v4/LICENSE-DepthAnything.txt",
        "weights_sha256": MODEL_HASHES["model.safetensors"],
        "model_files": downloads,
        "adapted_from": UPSTREAM_SCRIPT.relative_to(REPO).as_posix(),
        "adapted_from_sha256": digest(UPSTREAM_SCRIPT),
        "architecture": "Installed Transformers explicit DepthAnything + DINOv2, strict original tensors",
        "device": "cpu", "threads": args.threads, "torch": torch.__version__,
        "model_parameters": existing.get("model_parameters"),
        "network_used": False, "provider_uploads": False, "native_ai_video": False,
        "security_policy_changes": False,
        "input_policy": "Only direct numbered 01–18 opaque PNGs in assets/art-v4. Symbolic nonhuman artwork only; no user photographs or alpha foregrounds.",
        "limits": "Estimated monocular relative 2.5D, not true geometry or metric depth. Can mis-rank paper relief, mist and empty fields. Use restrained camera shifts; cannot reveal unseen surfaces or synthesize native video.",
        "normalization": "Predicted relative depth, percentiles 2–98 clipped to uint8 0–255; white is near",
        "last_run": {"generated": [], "skipped_unchanged": skipped},
        "depths": records,
    }
    if not pending:
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        publish(report)
        print(f"All {len(skipped)} selected depth maps unchanged; no inference needed.", flush=True)
        return
    torch.set_num_threads(args.threads)
    config = DepthAnythingConfig(**json.loads((CACHE / "config.json").read_text()))
    model = ExplicitDepthAnything(config).eval()
    model.load_state_dict(load_file(CACHE / "model.safetensors", device="cpu"), strict=True)
    processor = json.loads((CACHE / "preprocessor_config.json").read_text())
    mean = torch.tensor(processor["image_mean"]).reshape(1, 3, 1, 1)
    std = torch.tensor(processor["image_std"]).reshape(1, 3, 1, 1)
    report["model_parameters"] = sum(p.numel() for p in model.parameters())
    for stem in pending:
        tick = time.perf_counter()
        plate, checksum, (width, height) = sources[stem]
        image = Image.open(plate).convert("RGB")
        scale = 518 / min(width, height)
        iw, ih = int(round(width * scale / 14) * 14), int(round(height * scale / 14) * 14)
        prepared = image.resize((iw, ih), Image.Resampling.BICUBIC)
        tensor = torch.from_numpy(np.asarray(prepared, dtype=np.float32).copy()).permute(2, 0, 1).unsqueeze(0) / 255
        with torch.inference_mode():
            prediction = model(pixel_values=(tensor - mean) / std).predicted_depth
            raw = torch.nn.functional.interpolate(prediction.unsqueeze(1), size=(height, width), mode="bicubic", align_corners=False)[0, 0].numpy()
        low, high = np.percentile(raw, [2, 98])
        if not np.isfinite(raw).all() or high - low < 1e-6:
            raise ValueError(f"Invalid or constant relative-depth prediction: {stem}")
        depth = np.clip((raw - low) / (high - low), 0, 1)
        target = OUT / f"{stem}.png"
        temporary = target.with_suffix(".png.tmp")
        Image.fromarray(np.round(depth * 255).astype(np.uint8)).save(temporary, format="PNG")
        temporary.replace(target)
        records[stem] = {
            "path": target.relative_to(ROOT).as_posix(),
            "source_path": plate.relative_to(ROOT).as_posix(),
            "source_sha256": checksum, "depth_sha256": digest(target),
            "model_revision": REVISION, "width": width, "height": height,
            "input_width": iw, "input_height": ih,
            "inference_seconds": round(time.perf_counter() - tick, 3),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "near_is_white": True, "texture_color_space": "linear / NoColorSpace",
            "raw_percentile_2": float(low), "raw_percentile_98": float(high),
        }
        report["last_run"]["generated"].append(stem)
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        publish(report)
        print(f"Depth ready {stem}: {records[stem]['inference_seconds']}s", flush=True)
    print(f"Published {len(records)} total depth maps; generated {len(pending)}, reused {len(skipped)}.", flush=True)


if __name__ == "__main__":
    main()
