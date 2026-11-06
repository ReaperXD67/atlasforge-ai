"""Rebuild the hero's licensed local Foley sources as 48 kHz stereo stems."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SOURCES = [
    ("kenney-click-001.ogg", "click.wav", "ccfb7fa0cccdd9faec0eb16033c732b1e308d139d80f799161495d58f7adcdb9"),
    ("kenney-switch-001.ogg", "switch.wav", "3b74efad87f1e69dbd1d05c5ad952ab90859b5a3d11da6ec5bd79b4f03b42afa"),
    ("ylmir-rain-01.ogg", "rain.wav", "4f659f68cf5219007d0bb0969a1862491ceee4057fda4c491c6001e8608fa2cb"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?", default=Path("videos/biznex-second-question"))
    args = parser.parse_args()
    root = args.project / "assets/audio"
    provenance_path = root / "FOLEY_PROVENANCE.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    derived = []
    for source, name, expected in SOURCES:
        if hashlib.sha256((root / source).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Licensed source changed: {source}")
        data, rate = sf.read(root / source, always_2d=True, dtype="float32")
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        divisor = math.gcd(rate, 48000)
        data = resample_poly(data, 48000 // divisor, rate // divisor, axis=0)
        modifications = "Resampled to stereo 48 kHz PCM16; amplitude retained."
        if name == "click.wav":
            data = np.pad(data, ((0, max(0, 12000 - len(data))), (0, 0)))
            modifications += " Silence padded to 0.25 s; click itself not stretched."
        if name == "rain.wav":
            loop = data.copy()
            fade = 12000
            ramp = np.linspace(0, 1, fade, endpoint=False, dtype=np.float32)[:, None]
            while len(data) < 1968000:
                join = data[-fade:] * (1 - ramp) + loop[:fade] * ramp
                data = np.concatenate((data[:-fade], join, loop[fade:]))
            data = data[:1968000]
            modifications += " Source is explicitly loopable; repeated with 0.25 s overlap crossfade and trimmed to 41 s."
        peak = float(np.abs(data).max())
        if peak >= 1:
            raise ValueError(f"Resampled source would clip: {source}")
        target = root / name
        sf.write(target, data, 48000, subtype="PCM_16")
        derived.append({"file": name, "parent_file": source, "license": "CC0-1.0",
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        "duration_seconds": len(data) / 48000, "sample_rate": 48000,
                        "channels": 2, "peak_linear_before_quantization": peak,
                        "modifications": modifications})
    provenance["derived_assets"] = derived
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(derived, indent=2))


if __name__ == "__main__":
    main()
