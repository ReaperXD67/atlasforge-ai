"""Prepare six real, locally voiced pilot projects from reviewed social briefs.

This writes audio and measured production data; it never renders or publishes videos.
Run from the repository root with cached Kokoro and Whisper models.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from daily_video_factory.config import load_settings
from daily_video_factory.media.audio import generate_original_music
from daily_video_factory.media.ffmpeg import FFmpeg
from daily_video_factory.media.subtitles import write_exact_caption_sidecars
from daily_video_factory.production_batch import (
    load_production_batch_manifest,
    validate_editorial_manifest,
)
from daily_video_factory.providers.tts import NarrationGenerator
from daily_video_factory.shorts_delivery import validate_shorts_upload_package
from daily_video_factory.voice_direction import VoiceDirection

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "config/social/first-six-briefs.json"
MANIFEST = ROOT / "config/batches/biznex-first-six.production.json"

STORY_ANCHORS = {
    "biznex-two-paper-doors": [
        "Which door matches why you came here?", "Mira folds two paper doors,",
        "Atomy’s U.S. guide separates consumer and distributor registration.",
        "First name your purpose.",
    ],
    "biznex-card-under-the-cup": [
        "Consumer. Distributor.", "Jon lifts his cup.",
        "Atomy’s guide lists Social Security and bank information for distributor registration.",
        "He slides that checklist beside his purpose card.",
    ],
    "biznex-missing-index-card": [
        "What did her neat little checklist leave out?", "The empty space bothers her,",
        "Atomy’s U.S. registration guide requires a sponsor and describes automatic or manual designation.",
        "She adds a fourth card:",
    ],
    "biznex-two-ribbons": [
        "Sponsor required.", "Jon follows two ribbons back to one card.",
        "The Atomy source gives him a better question:", "He replaces the vague note.",
    ],
    "biznex-receipt-fold": [
        "Which number was she about to fold away?", "Mira circles a price,",
        "Atomy or another shop:", "match the item, check the size, then compare the total.",
    ],
    "biznex-three-empty-boxes": [
        "Exact item. Size. Total cost.", "The bold price leaves questions unanswered.",
        "Atomy or another shop,", "The empty boxes were the useful part.",
    ],
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def phrase_time(words: list[dict], phrase: str) -> float:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    tokens = [normalize(word["text"]) for word in words]
    needle = [normalize(word) for word in phrase.split()]
    for index in range(len(tokens) - len(needle) + 1):
        if tokens[index:index + len(needle)] == needle:
            return float(words[index]["start"])
    raise ValueError(f"No measured speech anchor for {phrase!r}")


def constrain_word_anchors(
    words: list[dict], plan: VoiceDirection, performance: dict
) -> tuple[list[dict], int]:
    """Keep interpolated word anchors inside their known synthesized speech beat."""
    if sum(len(beat.text.split()) for beat in plan.beats) != len(words):
        raise ValueError("Voice beat word counts differ from caption word counts")
    constrained = [dict(word) for word in words]
    word_cursor = 0
    corrected = 0
    for beat, measured in zip(plan.beats, performance["beats"], strict=True):
        speech_start = measured["start_sample"] / performance["sample_rate"]
        speech_end = (measured["start_sample"] + measured["speech_samples"]) / performance["sample_rate"]
        count = len(beat.text.split())
        for word in constrained[word_cursor:word_cursor + count]:
            previous = (word["start"], word["end"])
            word["start"] = round(max(word["start"], speech_start), 4)
            word["end"] = round(min(word["end"], speech_end), 4)
            if word["start"] >= word["end"]:
                raise ValueError("An ASR anchor lies entirely outside its synthesized speech beat")
            corrected += previous != (word["start"], word["end"])
        word_cursor += count
    return constrained, corrected


def make_mix(audio: Path, shots: list[dict], duration: float, ffmpeg: FFmpeg) -> None:
    generate_original_music(duration, audio / "original_score.wav")
    # Original, seeded paper-brush and pencil-tap foley. No sampled commercial audio.
    sr = 48000
    foley = np.zeros((round(duration * sr), 2), dtype=np.float32)
    rng = np.random.default_rng(117 + sum(ord(c) for c in audio.parent.parent.name))
    for index, shot in enumerate(shots):
        start = round((float(shot["start"]) + 0.05) * sr)
        count = min(round(0.33 * sr), len(foley) - start)
        if count <= 0:
            continue
        t = np.arange(count, dtype=np.float32) / sr
        noise = rng.normal(0, 1, count).astype(np.float32)
        brush = np.convolve(noise, np.ones(24) / 24, mode="same")
        envelope = np.sin(np.pi * np.minimum(1, t / .33)) ** 2
        tap = np.sin(2 * np.pi * (640 + index * 80) * t) * np.exp(-42 * t)
        sample = (brush * envelope * .12 + tap * .045).astype(np.float32)
        foley[start:start + count, 0] += sample * .8
        foley[start:start + count, 1] += sample * .7
    sf.write(audio / "original_foley.wav", foley, sr, subtype="PCM_16")
    filters = (
        f"[0:a]apad,atrim=0:{duration:.6f},aformat=channel_layouts=stereo,asplit=2[n][side];"
        "[1:a]aformat=channel_layouts=stereo,volume=-15dB[m];"
        "[m][side]sidechaincompress=threshold=0.025:ratio=10:attack=20:release=350[duck];"
        "[2:a]aformat=channel_layouts=stereo,volume=-13dB[fx];"
        "[n][duck][fx]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=7,alimiter=limit=0.95,"
        f"apad,atrim=0:{duration:.6f}[out]"
    )
    ffmpeg.run([
        "-i", str(audio / "narration.wav"), "-i", str(audio / "original_score.wav"),
        "-i", str(audio / "original_foley.wav"), "-filter_complex", filters,
        "-map", "[out]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
        "-t", f"{duration:.6f}", str(audio / "final_mix.wav"),
    ])
    samples, rate = sf.read(audio / "final_mix.wav", dtype="float32")
    if rate != 48000 or samples.ndim != 2 or samples.shape[1] != 2:
        raise ValueError("Final mix must be 48 kHz stereo")
    # FFmpeg filter draining can omit a final fractional block. Append only
    # silence to the declared frame boundary; never cut generated speech.
    target_samples = round(duration * rate)
    if len(samples) < target_samples:
        samples = np.pad(samples, ((0, target_samples - len(samples)), (0, 0)))
        sf.write(audio / "final_mix.wav", samples, rate, subtype="PCM_16")
    if abs(len(samples) / rate - duration) > 1 / rate:
        raise ValueError("Final mix duration differs from the frame-aligned timeline")
    if not np.isfinite(samples).all() or np.max(np.abs(samples)) >= .999:
        raise ValueError("Final mix contains invalid or clipped samples")


def prepare(episode: dict, narrator: NarrationGenerator, ffmpeg: FFmpeg) -> dict:
    episode_id = episode["id"]
    if not re.fullmatch(r"[a-z0-9-]+", episode_id):
        raise ValueError("Unsafe episode id")
    project = ROOT / "videos" / episode_id
    audio = project / "assets/audio"
    audio.mkdir(parents=True, exist_ok=True)
    narration = episode["narration"]
    plan = VoiceDirection.model_validate(episode["voice_direction"])
    plan.validate_transcript(narration)
    write_json(project / "direction.json", plan.model_dump())
    (project / "narration.txt").write_text(narration + "\n", encoding="utf-8")
    digest = hashlib.sha256((plan.model_dump_json() + "af_heart|0.97|pilot-v1").encode()).hexdigest()
    cache = project / "AUDIO_PREPARATION.json"
    ready = False
    if cache.is_file() and (audio / "narration.wav").is_file():
        prior = json.loads(cache.read_text(encoding="utf-8"))
        ready = prior.get("fingerprint") == digest and all(
            (audio / name).is_file() for name in [
                "narration.words.json", "narration.captions.json", "narration.performance.json"
            ]
        )
    if not ready:
        print(f"SYNTHESIZING {episode_id}", flush=True)
        result = narrator.run(narration, audio, direction=plan)
        if result.provider != "kokoro":
            raise ValueError("The pilot voice must remain local Kokoro")
    narration_seconds = ffmpeg.duration(audio / "narration.wav")
    duration = math.ceil(narration_seconds * 30 - 1e-5) / 30
    if not 20 <= narration_seconds <= 35 or duration > 35:
        raise ValueError(f"{episode_id}: actual narration {narration_seconds:.3f}s is outside 20–35s")
    words = json.loads((audio / "narration.words.json").read_text(encoding="utf-8"))
    if " ".join(word["text"] for word in words) != narration:
        raise ValueError("Caption transcript drift")
    performance = json.loads((audio / "narration.performance.json").read_text(encoding="utf-8"))
    # ASR can miss a proper name and interpolate it into the preceding silence.
    # Synthesis gives exact beat sample bounds: constrain anchors to that measured
    # speech window, rather than inventing evenly spaced word times.
    words, corrected_anchors = constrain_word_anchors(words, plan, performance)
    if not all(0 <= word["start"] < word["end"] <= narration_seconds for word in words):
        raise ValueError("Caption timing outside actual narration")
    if any(b["start"] < a["end"] - 0.001 for a, b in zip(words, words[1:], strict=False)):
        raise ValueError("Overlapping word timing")
    write_exact_caption_sidecars(
        narration, [(word["text"], word["start"], word["end"]) for word in words],
        audio, max_words=4, minimum_seconds=.5,
    )
    captions = json.loads((audio / "narration.captions.json").read_text(encoding="utf-8"))
    beats = []
    for index, (beat, measured) in enumerate(zip(plan.beats, performance["beats"], strict=True)):
        start = measured["start_sample"] / performance["sample_rate"]
        end = (measured["start_sample"] + measured["speech_samples"] + measured["appended_pause_samples"]) / performance["sample_rate"]
        beats.append({"index": index, "id": f"beat-{index+1:02d}", **beat.model_dump(),
                      "start": round(start, 4), "end": round(end, 4)})
    shots = []
    for index, shot in enumerate(episode["shot_beats"]):
        shots.append({"index": index, **shot,
                      "start": 0.0 if index == 0 else phrase_time(words, shot["speech_anchor"])})
    for index, shot in enumerate(shots):
        shot["end"] = shots[index + 1]["start"] if index < len(shots) - 1 else duration
        if shot["start"] >= shot["end"]:
            raise ValueError("Non-increasing shot speech anchors")
    roles = ["setup", "turn", "brand", "payoff"]
    cues = [{"id": role, "text": phrase, "start": phrase_time(words, phrase)}
            for role, phrase in zip(roles, STORY_ANCHORS[episode_id], strict=True)]
    for index, cue in enumerate(cues):
        cue["end"] = cues[index + 1]["start"] if index < len(cues) - 1 else duration
    timing = {"schema_version": 1, "duration_seconds": duration,
              "narration_duration_seconds": narration_seconds,
              "fps": 30, "beats": beats, "shots": shots, "captions": captions,
              "words": words, "cues": cues,
              "timing_basis": "Synthesis sample counts for beats; ASR word anchors constrained to exact speech-beat bounds, preserving canonical text.",
              "anchors_constrained_to_speech_beats": corrected_anchors}
    write_json(project / "timing.json", timing)
    make_mix(audio, shots, duration, ffmpeg)
    write_json(project / "audio_request.json", {
        "provider": "kokoro", "voice": "af_heart", "speed": .97, "lang": "en-us",
        "direction": "direction.json", "direction_mode": "pace_and_pauses_only",
        "semantic_emotion_supported": False, "emotion_fidelity_verified": False,
        "lines": [{"id": beat["id"], "text": beat["text"]} for beat in beats],
        "bgm": {"mode": "project-owned", "source": "assets/audio/original_score.wav"},
        "sfx": {"mode": "project-owned", "source": "assets/audio/original_foley.wav"},
        "measured_duration_seconds": duration,
    })
    script = f"# SCRIPT — {episode['title']}\n\nVoice: Kokoro af_heart; baseline speed 0.97.\n\n"
    for beat in beats:
        script += (f"## Line {beat['index']+1}\n\n"
                   f"Time: {beat['start']:.3f}–{beat['end']:.3f}s. "
                   f"Pace {beat['pace']}; pause {beat['pause_after_ms']} ms.\n\n"
                   f"    {beat['text']}\n\n")
    (project / "SCRIPT.md").write_text(script, encoding="utf-8")
    (project / "THUMBNAIL_COPY.txt").write_text(episode["thumbnail_copy"] + "\n", encoding="utf-8")
    upload = (f"# Upload package\n\n## Title\n\n{episode['title']}\n\n"
              f"## Description\n\n{episode['caption']}\n\n"
              "## Hashtags\n\n#BizNex #InformedChoices #SourceCheck #Shorts\n\n"
              f"## Files\n\n- Video: renders/final.mp4\n- Thumbnail: assets/thumbnails/thumbnail.png\n"
              f"- Voice: af_heart\n- Runtime: {duration:.3f} seconds\n\n"
              "## Disclosure\n\nOriginal fictional story; AI narration and original animated visuals. "
              "Independent education, not an official Atomy corporate account. "
              "No income or health result is depicted. Confirm and disclose any actual commercial relationship before posting.\n")
    validate_shorts_upload_package(upload)
    (project / "UPLOAD_PACKAGE.md").write_text(upload, encoding="utf-8")
    editorial = {
        "schema_version": 1, "script": "narration.txt", "thumbnail_copy": "THUMBNAIL_COPY.txt",
        "audience_problem": episode["premise"],
        "hook": {"text": cues[0]["text"], "at_seconds": 0},
        "payoff": {"text": cues[-1]["text"], "at_seconds": cues[-1]["start"]},
        "packaging": {"title": episode["title"], "thumbnail_text": episode["thumbnail_copy"],
                      "promise": episode["payoff"], "evidence_anchor": cues[-1]["text"],
                      "reviewed": True},
        "sources": [{"claim": source["supported_claim"], "url": source["url"],
                     "checked_on": source["checked_on"]} for source in episode["sources"]],
        "retention_beats": sorted(
            [{"at_seconds": shot["start"], "purpose": shot["on_screen_text"]} for shot in shots]
            + [{"at_seconds": beat["start"], "purpose": "Narration turn: " + beat["text"]}
               for beat in beats if all(abs(beat["start"] - shot["start"]) > .001 for shot in shots)],
            key=lambda beat: beat["at_seconds"],
        ),
        "story": {"fictional": True, "protagonist": "Mira" if episode["sequence"] % 2 else "Jon",
                  "disclosure": episode["spoken_fiction_disclosure"], "setup_segment": "setup",
                  "turn_segment": "turn", "brand_connection_segment": "brand",
                  "payoff_segment": "payoff", "timing_manifest": "timing.json"},
        "experiment": episode["experiment"],
        "review_scope": "Packaging-to-script alignment reviewed. No claim of audience performance or automatic fact checking.",
    }
    write_json(project / "EDITORIAL.json", editorial)
    write_json(project / "AUDIO_PREPARATION.json", {
        "fingerprint": digest, "provider": "kokoro", "voice": "af_heart",
        "narration_seconds": narration_seconds, "duration_seconds": duration,
        "status": "audio_and_measured_timing_ready", "video_rendered": False,
        "exact_caption_text": True, "caption_timing_inside_audio": True,
    })
    write_json(project / "assets/audio/provenance.json", {
        "narration": {"engine": "Kokoro", "voice": "af_heart", "reference_voice_cloning": False},
        "music": {"type": "original procedural score", "generator": "daily_video_factory.media.audio.generate_original_music", "external_samples": False},
        "foley": {"type": "original seeded synthesis", "generator": "scripts/prepare_pilot_batch.py", "external_samples": False},
        "mix": {"speech_sidechain_ducking": True, "channels": 2, "sample_rate": 48000},
    })
    (project / "README.md").write_text(
        f"# {episode['title']}\n\nAn original fictional BizNex pilot about {episode['topic_family']}. "
        f"The approved af_heart narration and scored stereo mix are prepared at {duration:.3f} seconds.\n\n"
        "`timing.json` contains measured narration beats, shot anchors, words and captions. "
        "`EDITORIAL.json` records source claims, fiction disclosure and the packaging review. "
        "`UPLOAD_PACKAGE.md` contains platform copy.\n\n"
        "Rebuild audio from the repository root with:\n\n"
        f"```powershell\n.\\.venv\\Scripts\\python.exe scripts/prepare_pilot_batch.py --episodes {episode_id}\n```\n\n"
        "The preparation command requires cached local voice/transcription models and does not render or publish. "
        "Final video status must be established by the batch delivery report after rendering.\n",
        encoding="utf-8",
    )
    print(f"READY {episode_id} duration={duration:.6f} narration={narration_seconds:.3f}", flush=True)
    return {"id": episode_id, "project": f"videos/{episode_id}", "format": "shorts",
            "output": "renders/final.mp4", "thumbnail": "assets/thumbnails/thumbnail.png",
            "upload_package": "UPLOAD_PACKAGE.md", "voice_manifest": "audio_request.json",
            "editorial_manifest": "EDITORIAL.json", "min_seconds": 20.0, "max_seconds": 35.0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", nargs="*", default=[])
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("HF_HOME", str(Path.home() / ".cache/huggingface"))
    data = json.loads(BRIEFS.read_text(encoding="utf-8"))
    settings = load_settings(ROOT / "config/profiles/biznex-local-voice-proof.yaml")
    settings.voice.edge_caption_max_words = 4
    ffmpeg = FFmpeg()
    narrator = NarrationGenerator(settings, ffmpeg)
    selected = [episode for episode in data["episodes"] if not args.episodes or episode["id"] in args.episodes]
    if args.episodes and set(args.episodes) - {episode["id"] for episode in selected}:
        raise ValueError("Unknown pilot episode requested")
    rows = [prepare(episode, narrator, ffmpeg) for episode in selected]
    if not args.episodes:
        write_json(MANIFEST, {"schema_version": 1, "batch_id": "biznex-first-six",
                              "expected_voice": "af_heart", "episodes": rows})
    if MANIFEST.is_file():
        manifest = load_production_batch_manifest(MANIFEST, repository_root=ROOT)
        for episode in manifest.episodes:
            if episode.id not in {row["id"] for row in rows}:
                continue
            timing = json.loads((episode.project / "timing.json").read_text(encoding="utf-8"))
            brief = next(item for item in data["episodes"] if item["id"] == episode.id)
            validate_editorial_manifest(episode, title=brief["title"], duration_seconds=timing["duration_seconds"])
    print(f"Prepared {len(rows)} pilots. Manifest: {MANIFEST}", flush=True)


if __name__ == "__main__":
    main()
