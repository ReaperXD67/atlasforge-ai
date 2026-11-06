"""Run pinned CosyVoice3 in its own environment, with no publishing/API clients."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_video_factory.expressive_voice import (  # noqa: E402
    COSYVOICE_COMMIT,
    COSYVOICE_MODEL,
    COSYVOICE_MODEL_REVISION,
    NEUTRAL_INSTRUCTION,
    sha256_file,
    validate_request,
    verify_model_files,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, default=ROOT / "models/upstream/CosyVoice")
    parser.add_argument("--model", type=Path, default=ROOT / "models/expressive/Fun-CosyVoice3-0.5B")
    parser.add_argument("--neutral-comparison", action="store_true")
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    validate_request(request)
    upstream = args.upstream.resolve()
    commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True,
    ).strip()
    if commit != COSYVOICE_COMMIT:
        raise ValueError(f"Unreviewed upstream revision: {commit}")
    subprocess.run(["git", "-C", str(upstream), "diff", "HEAD", "--exit-code", "--quiet"], check=True)
    verified_models = verify_model_files(
        args.model, ROOT / "config/expressive-voice/cosyvoice3-model-lock.json",
    )
    # The worker must not download additional models or receive application secrets.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(upstream / "third_party/Matcha-TTS"))
    sys.path.insert(0, str(upstream))
    import cosyvoice.utils.file_utils as file_utils
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio

    def read_reference_wav(path, target_sr, min_sr=16000):
        # New torchaudio versions route load() through TorchCodec. Read our local
        # PCM reference directly instead; resampling still uses the upstream DSP.
        values, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        if sample_rate < min_sr:
            raise ValueError("Reference sample rate is too low")
        speech = torch.from_numpy(values.T.copy()).mean(dim=0, keepdim=True)
        if sample_rate != target_sr:
            speech = torchaudio.functional.resample(speech, sample_rate, target_sr)
        return speech

    file_utils.load_wav = read_reference_wav
    from cosyvoice.cli.cosyvoice import AutoModel
    from cosyvoice.utils.common import set_all_random_seed

    torch.set_num_threads(4)
    if torch.cuda.is_available():
        # Establish the Windows CUDA context before CPU checkpoint construction
        # increases host-memory pressure; fail here if the device is unavailable.
        torch.empty(1, device="cuda")
        torch.cuda.synchronize()
    reference = Path(request["reference_audio"]).resolve()
    reference_info = sf.info(reference)
    if not 3 <= reference_info.duration <= 30:
        raise ValueError("Reference must contain 3 to 30 seconds of clean speech")
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    model = AutoModel(model_dir=str(args.model.resolve()), fp16=torch.cuda.is_available())
    load_seconds = time.perf_counter() - started
    # Cache only reference-derived features. Caching the complete zero-shot input
    # would also cache prompt_text and silently discard later emotion instructions.
    reference_cache = {}
    reference_extractions = {}
    for method_name in ("_extract_speech_feat", "_extract_speech_token", "_extract_spk_embedding"):
        original = getattr(model.frontend, method_name)

        def cached_reference(path, _original=original, _name=method_name):
            if str(path) != str(reference):
                return _original(path)
            if _name not in reference_cache:
                reference_cache[_name] = _original(path)
                reference_extractions[_name] = 1
            value = reference_cache[_name]
            # Upstream adjusts length tensors in-place; keep cached originals intact.
            return tuple(item.clone() for item in value) if isinstance(value, tuple) else value.clone()

        setattr(model.frontend, method_name, cached_reference)
    modes = ["neutral", "directed"] if args.neutral_comparison else ["directed"]
    report = {
        "schema_version": 1, "provider": "cosyvoice3", "upstream_commit": commit,
        "model_id": COSYVOICE_MODEL, "model_revision": COSYVOICE_MODEL_REVISION,
        "verified_model_files": verified_models,
        "code_license": "Apache-2.0", "model_license": "Apache-2.0",
        "reference_audio": str(reference), "reference_sha256": sha256_file(reference),
        "reference_provenance": request["reference_provenance"],
        "request_sha256": sha256_file(args.request),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "torch_version": torch.__version__, "sample_rate": model.sample_rate,
        "load_seconds": round(load_seconds, 3),
        "reference_feature_extractions": reference_extractions,
        "direction_mode": "reference_conditioned_semantic_instructions",
        "semantic_emotion_supported": True, "emotion_fidelity_verified": False,
        "speaker_similarity_verified": False,
        "notes": ["Instruction support is a model capability, not a listening-quality verdict.",
                  "No pitch shifting, tempo scaling, or paid API was used.",
                  "CPU ONNX frontend and CUDA fp16 acoustic model; no TensorRT/vLLM."],
        "takes": [],
    }
    for mode in modes:
        mode_dir = args.output / mode
        mode_dir.mkdir(exist_ok=True)
        combined = []
        cursor = 0
        for index, beat in enumerate(request["beats"]):
            set_all_random_seed(beat.get("seed", 1986))
            instruction = (NEUTRAL_INSTRUCTION if mode == "neutral"
                           else beat.get("instruction", NEUTRAL_INSTRUCTION))
            start = time.perf_counter()
            chunks = [
                item["tts_speech"].detach().cpu().numpy().reshape(-1)
                for item in model.inference_instruct2(
                    beat["text"], instruction, str(reference),
                    stream=False, speed=1.0, text_frontend=False,
                )
            ]
            if not chunks:
                raise RuntimeError(f"No audio returned for {beat['id']}")
            speech = np.concatenate(chunks).astype(np.float32)
            if not np.isfinite(speech).all() or not np.any(speech):
                raise RuntimeError(f"Invalid audio returned for {beat['id']}")
            elapsed = time.perf_counter() - start
            path = mode_dir / f"{beat['id']}.wav"
            sf.write(path, speech, model.sample_rate, subtype="PCM_16")
            pause_ms = beat.get("pause_after_ms", 0) if index + 1 < len(request["beats"]) else 0
            pause_samples = round(model.sample_rate * pause_ms / 1000)
            take = {
                "mode": mode, "id": beat["id"], "text": beat["text"],
                "caption_text": beat.get("caption_text", beat["text"]),
                "instruction": instruction, "seed": beat.get("seed", 1986),
                "path": str(path.resolve()), "sha256": sha256_file(path),
                "start_sample": cursor, "speech_samples": len(speech),
                "appended_pause_samples": pause_samples,
                "duration_seconds": round(len(speech) / model.sample_rate, 5),
                "inference_seconds": round(elapsed, 3),
                "peak_abs": round(float(np.max(np.abs(speech))), 5),
            }
            report["takes"].append(take)
            combined.extend([speech, np.zeros(pause_samples, dtype=np.float32)])
            cursor += len(speech) + pause_samples
            (args.output / "audition-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            print(json.dumps({"completed": beat["id"], "mode": mode,
                              "seconds": take["duration_seconds"]}), flush=True)
        sf.write(mode_dir / "narration.wav", np.concatenate(combined), model.sample_rate,
                 subtype="PCM_16")
    report["total_seconds"] = round(time.perf_counter() - started, 3)
    if torch.cuda.is_available():
        report["cuda_peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        report["cuda_peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
    (args.output / "audition-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({"report": str((args.output / "audition-report.json").resolve())}), flush=True)


if __name__ == "__main__":
    main()
