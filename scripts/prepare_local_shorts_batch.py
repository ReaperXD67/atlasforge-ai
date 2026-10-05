"""Prepare approved-voice Shorts from a local creative spec; no cloud spending.

Synthesis is cached by script/voice hash. Caption words are measured with local
Whisper, never evenly distributed across the clip. Rendering is a separate gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
ASSET_SOURCE = ROOT / "videos/atomy-smaller-leg-short/assets"


def normalize_caption_words(words: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    """Clean ASR token splits without replacing its measured word intervals."""
    normalized: list[dict[str, Any]] = []
    for original in words:
        word = dict(original)
        word["text"] = re.sub(r"(?i)^anatomy([.,!?]?)$", r"Atomy\1", word["text"].strip())
        if normalized:
            previous = normalized[-1]
            abbreviation = (
                previous["text"] == "U" and re.fullmatch(r"\.S\.?", word["text"])
            ) or (
                previous["text"] in {"U.S", "U.S."} and re.fullmatch(r"\.A\.?", word["text"])
            )
            number = re.fullmatch(r"\d+(?:,\d+)*", previous["text"]) and (
                re.fullmatch(r",\d+", word["text"]) or word["text"] == "%"
            )
            signup = previous["text"].casefold() == "sign" and word["text"].casefold() == "-up"
            if abbreviation or number or signup:
                previous["text"] = previous["text"].rstrip(".") + word["text"]
                if signup:
                    previous["text"] = "signup"
                previous["end"] = word["end"]
                continue
        if (
            re.fullmatch(r"-(?:open|guaranteed)[,.!?]?", word["text"], re.IGNORECASE)
            and word["text"].lstrip("-").strip(",.!?").casefold() in re.findall(r"[a-z]+", source.casefold())
        ):
            word["text"] = word["text"].lstrip("-")
        normalized.append(word)
    if "promises in comments" in source.casefold():
        for index in range(1, len(normalized) - 1):
            before, word, after = normalized[index - 1:index + 2]
            if (
                before["text"].casefold().strip(".,!?") == "promises"
                and word["text"].casefold() == "and"
                and after["text"].casefold().strip(".,!?") == "comments"
            ):
                word["text"] = "in"
    if "plan's rules" in source.casefold():
        for word, after in zip(normalized, normalized[1:], strict=False):
            if word["text"].casefold() == "plans" and after["text"].casefold().strip(".,!?") == "rules":
                word["text"] = "plan's"
    for index, word in enumerate(normalized):
        word["id"] = f"w{index}"
    return normalized


def caption_coverage_matches(words: list[dict[str, Any]], source: str) -> bool:
    def canonical(text: str) -> str:
        text = text.casefold().replace("forty four percent", "44").replace("ten thousand", "10000")
        return re.sub(r"[^a-z0-9]", "", text)

    return canonical(" ".join(word["text"] for word in words)) == canonical(source)


def local_whisper() -> Any:
    from faster_whisper import WhisperModel

    model_root = ROOT / "models/whisper/models--Systran--faster-whisper-small.en/snapshots"
    candidates = sorted(p for p in model_root.iterdir() if (p / "model.bin").is_file())
    if not candidates:
        raise FileNotFoundError("Local small.en Whisper model is required")
    return WhisperModel(str(candidates[-1]), device="cpu", compute_type="int8", cpu_threads=4)


def transcribe_words(
    whisper: Any, wav: Path, source: str, *, clip: tuple[float, float] | None = None,
) -> list[dict[str, Any]]:
    options = {"clip_timestamps": list(clip)} if clip else {}
    segments, _ = whisper.transcribe(
        str(wav), language="en", word_timestamps=True, beam_size=5,
        initial_prompt=source, condition_on_previous_text=False, vad_filter=False, **options,
    )
    words = [
        {"text": word.word.strip(), "start": round(word.start, 3), "end": round(word.end, 3)}
        for segment in segments for word in segment.words or []
        if word.word.strip() and word.end > word.start
    ]
    return normalize_caption_words(words, source)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def project_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT / "videos")
    if not (path / "hyperframes.json").is_file():
        raise ValueError(f"Initialize a HyperFrames project first: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--creative", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.creative.read_text(encoding="utf-8"))
    if spec["schema_version"] != 1 or spec["voice"] != "af_heart":
        raise ValueError("Unsupported spec or unapproved voice")
    ids = [episode["id"] for episode in spec["episodes"]]
    projects = [episode["project"] for episode in spec["episodes"]]
    if not ids or len(set(ids)) != len(ids) or len(set(projects)) != len(projects):
        raise ValueError("Batch must have unique episode IDs and projects")
    kokoro = None
    whisper = None
    batch_episodes = []
    for episode in spec["episodes"]:
        project = project_path(episode["project"])
        voice_dir = project / "assets/voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        for category in ("fonts", "bgm", "sfx"):
            shutil.copytree(ASSET_SOURCE / category, project / "assets" / category, dirs_exist_ok=True)
        request = {
            "provider": "kokoro", "voice": spec["voice"], "speed": spec["speed"],
            "lang": "en-us", "style": "Warm, curious, clear, conversational; no voice substitution.",
            "lines": [{"id": f"cue-{i + 1}", "text": s["text"]} for i, s in enumerate(episode["segments"])],
            "bgm": {"mode": "project-owned"},
        }
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        cache_path = project / "audio_meta.json"
        cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        cached_wav = voice_dir / "01.wav"
        if (
            cached.get("request_sha256") == fingerprint
            and cached_wav.is_file()
            and cached_wav.stat().st_size > 0
            and len(cached.get("cues", [])) == len(episode["segments"])
        ):
            meta = cached
            print(f"{episode['id']}: cached audio", flush=True)
        else:
            if kokoro is None:
                from kokoro_onnx import Kokoro

                model = Path.home() / ".cache/hyperframes/tts/models/kokoro-v1.0.onnx"
                voices = Path.home() / ".cache/hyperframes/tts/voices/voices-v1.0.bin"
                kokoro = Kokoro(str(model), str(voices))
            if whisper is None:
                whisper = local_whisper()
            chunks = []
            cues = []
            offset = 0.0
            sample_rate = 24000
            for index, segment in enumerate(episode["segments"]):
                samples, sample_rate = kokoro.create(
                    segment["text"], voice=spec["voice"], speed=spec["speed"], lang="en-us",
                    sentence_pause=0.18, clause_pause=0.08,
                )
                duration = len(samples) / sample_rate
                cues.append({"start": round(offset, 3), "end": round(offset + duration, 3), **segment})
                chunks.extend([samples, np.zeros(round(0.10 * sample_rate), dtype=np.float32)])
                offset += duration + 0.10
                print(f"{episode['id']}: cue {index + 1}, {duration:.2f}s", flush=True)
            total = offset + 0.5
            if not 20 <= total <= 30:
                raise ValueError(f"{episode['id']}: {total:.3f}s outside 20–30s; revise script, not speed silently")
            chunks.append(np.zeros(round(0.5 * sample_rate), dtype=np.float32))
            wav = voice_dir / "01.wav"
            sf.write(wav, np.concatenate(chunks), sample_rate)
            narration = " ".join(segment["text"] for segment in episode["segments"])
            words = transcribe_words(whisper, wav, narration)
            if len(words) < 40:
                raise ValueError(f"{episode['id']}: suspiciously short transcript")
            meta = {
                "request_sha256": fingerprint,
                "voice_lock": {"provider": "kokoro", "voice": spec["voice"], "speed": spec["speed"]},
                "timing_source": "faster-whisper-small.en ASR word alignment (estimated, not native TTS timestamps)",
                "bgm": {"path": "assets/bgm/track.wav", "volume": 0.065, "duration_s": round(total, 3)},
                "bgm_pending": False, "total_duration_s": round(total, 3), "cues": cues,
                "voices": [{"frame": 1, "path": "assets/voice/01.wav", "duration_s": round(total, 3), "words": words}],
            }
        # Reuse measured audio timings while refreshing editable visual direction
        # and project-owned sound paths, including metadata from older caches.
        meta["cues"] = [
            {"start": cue["start"], "end": cue["end"], **segment}
            for cue, segment in zip(meta["cues"], episode["segments"], strict=True)
        ]
        narration = " ".join(segment["text"] for segment in episode["segments"])
        words = normalize_caption_words(meta["voices"][0]["words"], narration)
        if not caption_coverage_matches(words, narration):
            if whisper is None:
                whisper = local_whisper()
            # Source-prompted, bounded ASR can recover an omitted word while
            # retaining measured timings; never fabricate uniformly spaced words.
            words = []
            for cue in meta["cues"]:
                words.extend(transcribe_words(
                    whisper, cached_wav, cue["text"], clip=(cue["start"], cue["end"]),
                ))
            words = normalize_caption_words(words, narration)
            if not caption_coverage_matches(words, narration):
                raise ValueError(f"{episode['id']}: caption coverage differs from the source; review local ASR")
        meta["voices"][0]["words"] = words
        # Bake the music's end fade into its local file so preview and export
        # agree even when a reusable 30-second bed is cut to a shorter episode.
        bed = project / "assets/bgm/bed.wav"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(ASSET_SOURCE / "bgm/track.wav"),
            "-t", str(meta["total_duration_s"]),
            "-af", f"afade=t=in:st=0:d=0.15,afade=t=out:st={meta['total_duration_s'] - 0.65:.3f}:d=0.65",
            str(bed),
        ], check=True, shell=False)
        meta["bgm"]["path"] = "assets/bgm/bed.wav"
        meta["sfx"] = [
            {"frame": 1, "file": "assets/sfx/impact-bass-1.wav", "offset_s": 0.06, "duration_s": 0.45, "volume": 0.12},
            {"frame": 1, "file": "assets/sfx/chime.wav", "offset_s": meta["cues"][1]["start"] + 0.25, "duration_s": 0.57, "volume": 0.12},
        ]
        for asset in (meta["bgm"]["path"], *(sound["file"] for sound in meta["sfx"])):
            asset_path = project / asset
            if not asset_path.is_file() or asset_path.stat().st_size == 0:
                raise FileNotFoundError(f"Missing project-owned audio asset: {asset_path}")
        write_json(cache_path, meta)
        write_json(project / "audio_request.json", request)
        write_json(project / "EPISODE.json", {**episode, "duration_s": meta["total_duration_s"], "cues": meta["cues"]})
        total = meta["total_duration_s"]
        narration = " ".join(s["text"] for s in episode["segments"])
        brief = f"# Batch Short: {episode['title']}\n\n- Objective: clear, engaging Atomy education for BizNex.\n- Audience: curious Atomy viewers.\n- Format: 1080×1920, 30 fps, 20–30 seconds.\n- Voice: locked to local Kokoro af_heart at {spec['speed']}; explicitly remembered approval.\n- Mode: autonomous, render authorized by the user's request.\n- Assets: original diagrams, local fonts and project-owned audio.\n- Source: {episode['source']}\n- No earnings promises, no guaranteed virality, no invented product facts.\n- Deliverables: final MP4, portrait thumbnail, title, description, hashtags, delivery report.\n"
        (project / "BRIEF.md").write_text(brief, encoding="utf-8")
        extracted = project / "capture/extracted"
        extracted.mkdir(parents=True, exist_ok=True)
        (extracted / "visible-text.txt").write_text(episode["source_note"] + "\nSource: " + episode["source"], encoding="utf-8")
        (project / "SCRIPT.md").write_text(f'## Frame 1 — {episode["message"]}\n\n"{narration}"\n', encoding="utf-8")
        shots = []
        for i, cue in enumerate(meta["cues"]):
            end = meta["cues"][i + 1]["start"] if i + 1 < len(meta["cues"]) else total
            shots.append(f'Scene {i + 1} ({cue["start"]:.3f}–{end:.3f}s): {cue["shot"]} Spoken cue: "{cue["text"]}"')
        storyboard = f'''---
format: 1080x1920
duration: {total:.3f}s
message: "{episode['message']}"
arc: concept-explainer
audience: Atomy viewers who need accurate quick answers
mode: autonomous
music: playful editorial pulse under clear female narration
---

## Video direction

One continuous concept transformation, deliberately kept in one bounded frame so the hero object carries the explanation. Four VO-paced internal scenes vary centered, stacked-diagram and inverted-close framing. BlockFrame pastel grounds, Inter display and Space Grotesk labels; three visual depth layers and bold square hard-shadow cards. Reveal each new fact on its spoken cue, especially in the back half. Smooth long-tail settles, no bounce, breathing, clocks, random motion or front-loaded slide. Short held reads follow each reveal; the final half-second is a deliberate still hold. Keep all critical content above y=1510, with side-safe margins for Shorts controls. Persistent small BizNex / U.S. PLAN label, never a claim of official endorsement. No product photos or stock filler.

## Frame 1 — {episode['message']}

- scene: One concept object transforms across a hook, definition, caveat, and memorable takeaway.
- voiceover: "{narration}"
- duration: {total:.3f}s
- transition_in: cut
- poster: {meta['cues'][1]['start'] + 1:.3f}s
- status: outline
- src: compositions/frames/01-explainer.html
- type: feature_showcase
- persuasion: Question–answer pairing + progressive disclosure + concrete metaphor
- beat: curiosity, surprise, clarity
- blueprint: compose
- focal: the transforming concept diagram
- roles: hero diagram = foreground subject · supporting labels = midground · dot grid and stripes = background
- sfx: impact-bass, chime

narrativeRole: Resolve one misconception using a single evolving metaphor rather than four disconnected slides.
keyMessage: {episode['message']}

Compose: keep one visual actor continuous; spread four reveal sequences across the measured narration, with velocity-matched swaps between internal scenes.
{chr(10).join(shots)}
'''
        (project / "STORYBOARD.md").write_text(storyboard, encoding="utf-8")
        package = f"# Upload package\n\n## Title\n\n{episode['title']}\n\n## Description\n\n{episode['description']}\n\n## Hashtags\n\n{' '.join(episode['hashtags'])}\n\n## Files\n\n- Video: renders/final.mp4\n- Thumbnail: assets/thumbnails/thumbnail.png\n- Voice: af_heart\n- Runtime: {total:.3f} seconds\n\nNo upload is performed automatically. For Shorts, use a strong in-video cover frame; a separate thumbnail may not be selectable on every upload surface.\n"
        (project / "UPLOAD_PACKAGE.md").write_text(package, encoding="utf-8")
        batch_episodes.append({"id": episode["id"], "project": episode["project"], "output": "renders/final.mp4",
                               "thumbnail": "assets/thumbnails/thumbnail.png", "upload_package": "UPLOAD_PACKAGE.md",
                               "voice_manifest": "audio_request.json"})
        print(f"{episode['id']}: prepared {total:.3f}s, {len(meta['voices'][0]['words'])} aligned words", flush=True)
    write_json(args.creative.with_name("atomy-quick-truths.batch.json"), {
        "schema_version": 1, "batch_id": spec["batch_id"], "expected_voice": spec["voice"], "episodes": batch_episodes,
    })


if __name__ == "__main__":
    main()
