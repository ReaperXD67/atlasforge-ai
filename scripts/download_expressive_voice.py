"""Download pinned public CosyVoice assets with bounded ranges and hash checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import httpx

from daily_video_factory.expressive_voice import (
    COSYVOICE_MODEL,
    COSYVOICE_MODEL_REVISION,
    sha256_file,
    verify_model_files,
)

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/expressive-voice/cosyvoice3-model-lock.json"


def matches(path: Path, entry: dict) -> bool:
    if not path.is_file() or path.stat().st_size != entry["size"]:
        return False
    if entry.get("sha256"):
        return sha256_file(path) == entry["sha256"]
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest() == entry["git_blob_sha1"]


def download_file(entry: dict, destination: Path, workers: int) -> None:
    path = (destination / entry["path"]).resolve()
    if not path.is_relative_to(destination.resolve()):
        raise ValueError("Model path escapes destination")
    if matches(path, entry):
        print(f"Verified cached {entry['path']}", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = path.parent / f".{path.name}.parts"
    parts.mkdir(exist_ok=True)
    if not parts.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Part directory escapes destination")
    size = entry["size"]
    chunk_size = 8 * 1024 * 1024
    url = f"https://huggingface.co/{COSYVOICE_MODEL}/resolve/{COSYVOICE_MODEL_REVISION}/{quote(entry['path'])}"

    def fetch(start: int) -> Path:
        end = min(start + chunk_size, size) - 1
        part = parts / f"{start:012d}.part"
        expected = end - start + 1
        if part.is_file() and part.stat().st_size == expected:
            return part
        for attempt in range(4):
            temporary = part.with_suffix(".partial")
            try:
                with httpx.stream("GET", url, headers={"Range": f"bytes={start}-{end}"},
                                  follow_redirects=True, timeout=httpx.Timeout(90, connect=20)) as response:
                    response.raise_for_status()
                    full_small_file = response.status_code == 200 and start == 0 and expected == size
                    if not full_small_file and (
                        response.status_code != 206 or
                        response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}"
                    ):
                        raise ValueError("Unexpected download range response")
                    count = 0
                    with temporary.open("wb") as handle:
                        for block in response.iter_bytes(1024 * 1024):
                            count += len(block)
                            if count > expected:
                                raise ValueError("Download exceeded requested range")
                            handle.write(block)
                    if count != expected:
                        raise ValueError("Incomplete download range")
                os.replace(temporary, part)
                return part
            except (httpx.HTTPError, OSError, ValueError):
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)
        raise AssertionError("Unreachable download retry state")

    starts = list(range(0, size, chunk_size))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch, start) for start in starts]
        for count, future in enumerate(as_completed(futures), start=1):
            future.result()
            if count % 16 == 0 or count == len(futures):
                print(f"{entry['path']}: {count}/{len(futures)} ranges", flush=True)
    merged = path.with_suffix(path.suffix + ".verified-download")
    with merged.open("wb") as output:
        for start in starts:
            with (parts / f"{start:012d}.part").open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
    if not matches(merged, entry):
        raise ValueError(f"Publisher hash mismatch: {entry['path']}; no model file installed")
    os.replace(merged, path)
    for start in starts:
        part = parts / f"{start:012d}.part"
        if not part.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Part file escapes destination")
        part.unlink()
    if not any(parts.iterdir()):
        parts.rmdir()
    print(f"Verified {entry['path']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "models/expressive/Fun-CosyVoice3-0.5B")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock["repository"] != COSYVOICE_MODEL or lock["revision"] != COSYVOICE_MODEL_REVISION:
        raise ValueError("Unexpected model lock revision")
    for entry in lock["files"]:
        download_file(entry, args.destination, args.workers)
    verified = verify_model_files(args.destination, LOCK)
    print(json.dumps({"verified_files": len(verified), "revision": COSYVOICE_MODEL_REVISION}))


if __name__ == "__main__":
    main()
