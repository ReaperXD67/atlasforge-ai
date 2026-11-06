"""Generate the two authored silent character shots with cached local Wan weights."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from daily_video_factory.config import load_settings
from daily_video_factory.models import Scene
from daily_video_factory.providers.video import ComfyUIWan22Provider

PROJECT = Path("videos/biznex-second-question")
SHOTS = {
    "mira-night": {
        "seed": 2611062101,
        "action": "one slow natural blink, a quiet inhale, then a slight thoughtful upward gaze",
        "prompt": (
            "An intimate locked-off cinematic close-up of the same fictional adult woman in the "
            "reference photograph, sitting beside a rain-streaked window at night. She stays in "
            "the same pose and location. Her eyelids close once naturally, then open; she takes "
            "one quiet breath and raises her gaze a little, reconsidering a decision. Restrained "
            "thoughtful emotion. Preserve her face, hair, cream shirt and blue-amber lighting "
            "exactly. Subtle rain streaks move on the glass. No speech, no lip-sync, no smile, "
            "no camera pan, no zoom, no new objects, no text. Continuous realistic gentle motion."
        ),
    },
    "mira-morning": {
        "seed": 2611062102,
        "action": "a small deliberate writing stroke, relaxed breathing and a very slight smile",
        "prompt": (
            "A locked-off cinematic medium close-up of the same fictional adult woman in the "
            "reference photograph, writing in her notebook beside a sunlit apartment window. "
            "Keep her seated posture, face, shirt, hands, pen and every object consistent. Her "
            "pen makes two small deliberate strokes on the page while her other hand rests "
            "still. She breathes gently and forms a small relaxed smile without looking at the "
            "camera. The sheer curtain moves very slightly. No readable writing, no speech, "
            "no lip-sync, no camera pan, no zoom, no object additions or transformations. "
            "Anatomically coherent fingers and pen grip. Quiet natural live-action motion."
        ),
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot", choices=SHOTS, required=True)
    parser.add_argument("--execute", action="store_true", help="Submit one local GPU job.")
    args = parser.parse_args()
    shot = SHOTS[args.shot]
    reference = PROJECT / "assets/plates" / f"{args.shot}.png"
    output = PROJECT / "assets/motion" / f"{args.shot}.mp4"
    if not reference.is_file():
        raise SystemExit("The authored reference plate is missing.")
    settings = load_settings(Path("config/default.yaml"))
    parameters = {
        "comfyui_width": 384, "comfyui_height": 672,
        "comfyui_frames": 65, "comfyui_fps": 20,
        "comfyui_steps": 20, "comfyui_cfg": 5.0,
        "comfyui_rife_enabled": False, "comfyui_timeout_minutes": 60,
    }
    settings.video = settings.video.model_copy(update=parameters)
    provider = ComfyUIWan22Provider(settings)
    if urlsplit(provider.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("This production script only permits a local ComfyUI endpoint.")
    record = {
        "shot": args.shot, "reference": reference.as_posix(),
        "reference_sha256": _sha256(reference), "output": output.as_posix(),
        "provider": "ComfyUIWan22Provider", "model": "Wan2.2 TI2V 5B",
        "model_source": "https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B",
        "model_license": "Apache-2.0", "model_license_checked_on": "2026-11-06",
        "model_files": ["wan2.2_ti2v_5B_fp16.safetensors", "wan2.2_vae.safetensors",
                        "umt5_xxl_fp8_e4m3fn_scaled.safetensors"],
        "synthetic_media": True, "depicts": "fictional adult, not a real testimonial",
        "seed": shot["seed"], "prompt": shot["prompt"],
        "negative_prompt": provider.negative_prompt,
        "subject_action": shot["action"], "parameters": parameters,
        "audio": "silent source; narration and score are mixed separately",
        "status": "planned", "visual_review": "pending",
    }
    if not args.execute:
        print(json.dumps(record, indent=2))
        return
    if output.exists():
        raise SystemExit("Output exists; preserve and review it before choosing a new candidate.")
    if not provider.available():
        raise SystemExit("Local ComfyUI or required cached Wan models are unavailable.")
    scene = Scene(
        index=101 if args.shot == "mira-night" else 102,
        duration_seconds=65 / 20, narration="", video_prompt=shot["prompt"],
        visual_search_query=shot["action"], reference_image=reference,
        generation_seed=shot["seed"], generation_task="image_to_video", aspect_ratio="9:16",
        ai_generation_required=True,
        ai_generation_reason="Original fictional character performance needs actual subject motion.",
    )
    print(f"Generating {args.shot}: 384x672, 65 frames, 20 steps; one local GPU job.", flush=True)
    provider.generate(scene, output)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames",
         "-of", "json", str(output)], capture_output=True, text=True, check=True,
    )
    record.update({"status": "generated_review_pending", "generated_at": datetime.now(UTC).isoformat(),
                   "output_sha256": _sha256(output), "media_probe": json.loads(probe.stdout)})
    provenance = PROJECT / "MOTION_PROVENANCE.json"
    ledger = json.loads(provenance.read_text(encoding="utf-8")) if provenance.exists() else {
        "schema_version": 1, "clips": {},
    }
    ledger["clips"][args.shot] = record
    provenance.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"shot": args.shot, "status": record["status"], "output": output.as_posix(),
                      "media_probe": record["media_probe"]}, indent=2))


if __name__ == "__main__":
    main()
