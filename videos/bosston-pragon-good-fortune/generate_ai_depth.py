"""Create pinned CPU-AI relative-depth textures for the generated scene artwork.

Uses installed Apache-2.0 Hugging Face Depth Anything / DINOv2 model classes.
An explicit image backbone avoids the generic text-generation factory and its
unrelated optional sklearn dependency. No package or security policy is altered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import torch
from PIL import Image
from safetensors.torch import load_file
from transformers.models.depth_anything.configuration_depth_anything import DepthAnythingConfig
from transformers.models.depth_anything.modeling_depth_anything import (
    DepthAnythingDepthEstimationHead,
    DepthAnythingForDepthEstimation,
    DepthAnythingNeck,
    DepthAnythingPreTrainedModel,
)
from transformers.models.dinov2.modeling_dinov2 import Dinov2Backbone

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"
LICENSE_URL = "https://raw.githubusercontent.com/DepthAnything/Depth-Anything-V2/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf/LICENSE"
LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
MODEL_HASHES = {
    "config.json": "c56698d3643dde1f83ea2212759e6b31a22b8f827246a36dd007ee8a22b3ff75",
    "preprocessor_config.json": "d41175c0d889477ca8fc67191e540faef14baf6275157b3fdecf78469e6bbf84",
    "model.safetensors": "3152477ce0d8d6978d76b995120de97cb5b928701fd0f817769f59e249a16b70",
    "README.md": "319566441daaac0c5ed83e75a8fd19bae0863f3275e23f147c06fe0906edf6fb",
}
ORIGINAL_IDS = {
    "lantern-avenue": "avenue",
    "dragon-arena": "dragon",
    "silk-mountains": "ribbon",
    "sky-lanterns": "sunrise",
    "festival-drums": "drums",
    "golden-koi": "koi",
    "celestial-bridge": "bridge",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, directory: Path) -> dict:
    target = directory / name
    if target.is_file():
        if digest(target) != MODEL_HASHES[name]:
            raise ValueError(f"Cached pinned model file has changed: {target}")
        return {
            "file": name,
            "sha256": MODEL_HASHES[name],
            "size_bytes": target.stat().st_size,
            "reused": True,
        }
    url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}"
    temporary = target.with_suffix(target.suffix + ".part")
    with (
        httpx.Client(follow_redirects=True, timeout=httpx.Timeout(180, connect=30)) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        with temporary.open("wb") as output:
            for chunk in response.iter_bytes(1024 * 1024):
                output.write(chunk)
    checksum = digest(temporary)
    if checksum != MODEL_HASHES[name]:
        raise ValueError(f"Pinned SHA-256 mismatch for {name}")
    temporary.replace(target)
    return {
        "file": name,
        "url": url,
        "sha256": checksum,
        "size_bytes": target.stat().st_size,
        "reused": False,
    }


class ExplicitDepthAnything(DepthAnythingForDepthEstimation):
    """Installed model architecture with its sole DINOv2 backbone made explicit.

    Initialization adapts Transformers 5.14.1 (Apache-2.0, HuggingFace/TikTok).
    All installed forward/layer implementations and checkpoint tensors are intact.
    """

    def __init__(self, config):
        DepthAnythingPreTrainedModel.__init__(self, config)
        self.backbone = Dinov2Backbone(config.backbone_config)
        self.neck = DepthAnythingNeck(config)
        self.head = DepthAnythingDepthEstimationHead(config)
        self.post_init()


def read_assets(manifest: Path | None, plates: list[Path]) -> dict[str, Path]:
    if manifest is None:
        selected = plates or [ROOT / "assets/generated" / f"{stem}.png" for stem in ORIGINAL_IDS]
        return {ORIGINAL_IDS.get(p.stem, p.stem): p.resolve() for p in selected}
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    records = data.get("assets", data.get("plates", data))
    if not isinstance(records, dict):
        raise ValueError("AI asset manifest must map asset ids to paths or path records.")
    result = {}
    for key, record in records.items():
        value = (
            record
            if isinstance(record, str)
            else record.get("path", record.get("src", record.get("image")))
        )
        if not isinstance(value, str):
            raise ValueError(f"Asset {key!r} needs a path/src/image string.")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", key):
            raise ValueError(f"Unsafe asset id: {key!r}")
        path = Path(value)
        result[key] = (path if path.is_absolute() else ROOT / path).resolve()
    return result


def ensure_license(directory: Path) -> None:
    target = directory / "LICENSE-DepthAnything.txt"
    if target.is_file() and digest(target) == LICENSE_SHA256:
        return
    cached = REPO / "output/bosston-ai-v3/depth/LICENSE-DepthAnything.txt"
    if cached.is_file() and digest(cached) == LICENSE_SHA256:
        shutil.copy2(cached, target)
        return
    response = httpx.get(LICENSE_URL, timeout=30, follow_redirects=True)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != LICENSE_SHA256:
        raise ValueError("Pinned Depth Anything license checksum did not match.")
    target.write_bytes(response.content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plates", nargs="*", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "assets/depth")
    parser.add_argument("--data-dir", type=Path, default=REPO / "output/bosston-ai-v3/depth/maps")
    parser.add_argument(
        "--model-cache", type=Path, default=REPO / "output/bosston-ai-v3/depth/model" / REVISION
    )
    parser.add_argument("--report", type=Path, default=ROOT / "ai-depths.json")
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    assets = read_assets(args.manifest, args.plates)
    for path in assets.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    for directory in [args.runtime_dir, args.data_dir, args.model_cache]:
        directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        downloads = list(pool.map(lambda name: fetch(name, args.model_cache), MODEL_HASHES))
    (args.model_cache / "download-provenance.json").write_text(
        json.dumps(downloads, indent=2), encoding="utf-8"
    )
    torch.set_num_threads(max(1, args.threads))
    config = DepthAnythingConfig(**json.loads((args.model_cache / "config.json").read_text()))
    model = ExplicitDepthAnything(config).eval()
    model.load_state_dict(
        load_file(args.model_cache / "model.safetensors", device="cpu"), strict=True
    )
    processor = json.loads((args.model_cache / "preprocessor_config.json").read_text())
    mean = torch.tensor(processor["image_mean"]).reshape(1, 3, 1, 1)
    std = torch.tensor(processor["image_std"]).reshape(1, 3, 1, 1)
    records = {}
    for asset_id, plate in assets.items():
        start = time.perf_counter()
        image = Image.open(plate).convert("RGB")
        width, height = image.size
        scale = 518 / min(width, height)
        iw, ih = int(round(width * scale / 14) * 14), int(round(height * scale / 14) * 14)
        prepared = image.resize((iw, ih), Image.Resampling.BICUBIC)
        tensor = (
            torch.from_numpy(np.asarray(prepared, dtype=np.float32).copy())
            .permute(2, 0, 1)
            .unsqueeze(0)
            / 255
        )
        with torch.inference_mode():
            prediction = model(pixel_values=(tensor - mean) / std).predicted_depth
            raw = torch.nn.functional.interpolate(
                prediction.unsqueeze(1), size=(height, width), mode="bicubic", align_corners=False
            )[0, 0].numpy()
        low, high = np.percentile(raw, [2, 98])
        if not np.isfinite(raw).all() or high - low < 1e-6:
            raise ValueError(f"Invalid or constant relative depth prediction: {asset_id}")
        depth = np.clip((raw - low) / max(1e-8, high - low), 0, 1)
        runtime_path = args.runtime_dir / f"{asset_id}.png"
        Image.fromarray(np.round(depth * 255).astype(np.uint8)).save(runtime_path)
        Image.fromarray(np.round(depth * 65535).astype(np.uint16)).save(
            args.data_dir / f"{asset_id}-16bit.png"
        )
        np.save(args.data_dir / f"{asset_id}-raw.npy", raw)
        source_path = (
            plate.relative_to(ROOT).as_posix() if plate.is_relative_to(ROOT) else str(plate)
        )
        relative_depth = runtime_path.resolve().relative_to(ROOT).as_posix()
        records[asset_id] = {
            "path": relative_depth,
            "source_path": source_path,
            "source_sha256": digest(plate),
            "depth_sha256": digest(runtime_path),
            "model_revision": REVISION,
            "width": width,
            "height": height,
            "input_width": iw,
            "input_height": ih,
            "inference_seconds": round(time.perf_counter() - start, 3),
            "near_is_white": True,
            "texture_color_space": "linear / NoColorSpace",
            "normalization": "raw relative prediction, clipped percentiles 2–98, uint8 0–255",
            "raw_percentile_2": float(low),
            "raw_percentile_98": float(high),
        }
        print(f"Depth ready {asset_id}: {records[asset_id]['inference_seconds']}s", flush=True)
    ensure_license(args.runtime_dir)
    report = {
        "schema_version": 1,
        "model": MODEL_ID,
        "revision": REVISION,
        "license": "Apache-2.0",
        "license_url": LICENSE_URL,
        "license_sha256": LICENSE_SHA256,
        "weights_sha256": MODEL_HASHES["model.safetensors"],
        "device": "cpu",
        "torch": torch.__version__,
        "model_parameters": sum(p.numel() for p in model.parameters()),
        "security_policy_changes": False,
        "native_ai_video": False,
        "limits": "Monocular relative estimates are not physical geometry. Floating/bokeh foreground objects can be mis-ranked. Use restrained depth-parallax camera shifts; this does not synthesize new video content or unseen surfaces.",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "depths": records,
    }
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.report)
    print(f"Published {len(records)} depth textures: {args.report}", flush=True)


if __name__ == "__main__":
    main()
