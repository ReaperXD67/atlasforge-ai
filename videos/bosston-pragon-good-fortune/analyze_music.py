"""Use canonical music-to-video analysis without the crashing Windows beat tracker.

This is an adapter, not another rhythm analyzer. It invokes the installed canonical
analyzer's decoding, energy, band-character and onset operations. Beat-dependent
fields stay unavailable; the edit follows measured lyric phrases instead.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_ANALYZER = Path.home() / ".agents/skills/music-to-video/scripts/analyze-beatgrid.py"


def canonical(path: Path):
    spec = importlib.util.spec_from_file_location("canonical_music_analyzer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load canonical analyzer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_onsets(module, audio: Path, target: Path):
    # Identical call and parameters to canonical analyze(); deliberately no beat_grid.
    y, sr, _ = module.load_audio(str(audio))
    onset_t = module.librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=module.HOP, units="time", backtrack=True
    )
    target.write_text(json.dumps([round(float(t), 3) for t in onset_t]), encoding="utf-8")


def analyze(audio: Path, analyzer: Path, output: Path):
    module = canonical(analyzer)
    print("Canonical decoder and energy_structure (no beat tracker)", flush=True)
    y, sr, duration = module.load_audio(str(audio))
    energy = module.energy_structure(y, sr, duration)
    # Canonical centered RMS includes an endpoint sample. It can generate a
    # zero-length phase at the exact media end, which is not a playable span.
    energy["phases"] = [p for p in energy["phases"] if p["end"] > p["start"]]
    print(f"Energy extracted: {len(energy['norms'])} samples, {len(energy['phases'])} phases", flush=True)
    band_status = "unavailable"
    bands = None
    try:
        bands = module.band_energy_curves(y, sr)
        module.annotate_section_feel(bands, sr, energy["phases"])
        band_status = "canonical_band_energy_curves"
    except Exception as exc:
        band_status = f"unavailable: {type(exc).__name__}: {exc}"

    # Isolate onset extraction: another native-numba crash must not lose the map.
    evidence = ROOT / "timing-evidence"
    evidence.mkdir(exist_ok=True)
    onset_file = evidence / "canonical-onsets.json"
    env = dict(os.environ)
    env.pop("NUMBA_DISABLE_JIT", None)
    env["PYTHONUTF8"] = "1"
    command = [sys.executable, str(Path(__file__).resolve()), "--onsets-worker", "--audio", str(audio),
               "--analyzer", str(analyzer), "--output", str(onset_file)]
    try:
        worker = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        (evidence / "canonical-onset-worker.log").write_text(worker.stdout + worker.stderr, encoding="utf-8")
        onsets = json.loads(onset_file.read_text(encoding="utf-8")) if worker.returncode == 0 and onset_file.exists() else []
        onset_status = "canonical_librosa_onset_detect" if worker.returncode == 0 else f"unavailable_native_worker_exit_{worker.returncode}"
    except subprocess.TimeoutExpired:
        onsets, onset_status = [], "unavailable_worker_timeout"

    events = []
    if onsets and bands is not None:
        en_max = float(bands["total"].max()) + 1e-9
        for t in onsets:
            drum, _, feel = module.classify_drum(t, bands, sr)
            frame = module.frame_at(t, sr, bands["n"])
            events.append({"t": t, "bar": -1, "beat_in_bar": -1, "step16": -1,
                           "grid": "unavailable", "drum": drum,
                           "energy": round(float(bands["total"][frame]) / en_max, 2),
                           "feel": feel, "special": None})
    elif onsets:
        events = [{"t": t, "grid": "unavailable"} for t in onsets]
    timeline = {
        "summary": f"Canonical energy-only fallback; {duration:.3f}s; {len(energy['phases'])} energy phases; {len(onsets)} measured onsets; beat grid unavailable",
        "audio": {"path": "assets/bgm.wav", "duration_sec": round(duration, 3), "sr": sr,
                  "sha256": hashlib.sha256(audio.read_bytes()).hexdigest()},
        "tempo": {"bpm": None, "beats_per_bar": None, "downbeat_phase": None, "n_beats": 0, "n_bars": 0,
                  "status": "unavailable", "reason": "Canonical librosa beat tracker crashes in native numba gufunc on this Windows environment"},
        "grid": {"beats_sec": [], "downbeats_sec": [], "status": "unavailable"},
        "energy_curve": [{"time_seconds": float(i), "energy": value} for i, value in enumerate(energy["norms"]) if i <= duration],
        "energy_phases": energy["phases"], "key_moments": energy["moments"],
        "hard_stops": energy["hard_stops"], "rolls": [],
        "silences": [{"start": p["start"], "end": p["end"]} for p in energy["phases"] if p["level"] == "VOID"],
        "events": events, "onsets_sec": onsets,
        "analysis": {"backend": "canonical_energy_without_beat_grid", "pacing": "phrase_flow",
                     "canonical_analyzer": str(analyzer),
                     "canonical_analyzer_sha256": hashlib.sha256(analyzer.read_bytes()).hexdigest(),
                     "energy_method": "canonical energy_structure: normalized 1-second RMS",
                     "spectral_character": band_status, "onsets": onset_status,
                     "beat_dependent_rolls": "unavailable", "replacement_beat_detector": False,
                     "warning": "No exact beat-sync claim. Cuts are authored to measured vocals and energy changes."},
    }
    result = module.finalize_audiomap(timeline)
    if not onsets:
        for phase in result["energy_phases"]:
            phase["density"] = "unavailable"
            phase["onsetRate"] = None
            phase["onsets"] = None
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["summary"], flush=True)
    print(f"Wrote {output}; onsets={onset_status}; spectral={band_status}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=ROOT / "assets/bgm.wav")
    parser.add_argument("--analyzer", type=Path, default=DEFAULT_ANALYZER)
    parser.add_argument("--output", type=Path, default=ROOT / "audiomap.json")
    parser.add_argument("--onsets-worker", action="store_true")
    args = parser.parse_args()
    if args.onsets_worker:
        extract_onsets(canonical(args.analyzer), args.audio, args.output)
    else:
        analyze(args.audio, args.analyzer, args.output)
