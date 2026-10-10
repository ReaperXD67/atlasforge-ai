"""Prepare mixed videos with cached approved narration and measured ASR timings.

No render, publishing, paid provider calls or evenly-spaced caption timestamps.
Generated planning files are intentionally reproducible from the creative spec.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from prepare_local_shorts_batch import ASSET_SOURCE, ROOT, local_whisper


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold()).encode("ascii", "ignore").decode()
    ones = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
    def spoken(number: int) -> str:
        if number < 20:
            return ones[number]
        if number < 100:
            return tens[number // 10] + (ones[number % 10] if number % 10 else "")
        if number < 1000:
            return ones[number // 100] + "hundred" + (spoken(number % 100) if number % 100 else "")
        return str(number)
    text = re.sub(r"\b\d+\b", lambda match: spoken(int(match[0])), text)
    return re.sub(r"[^a-z0-9]", "", text)


def phrase_time(words: list[dict[str, Any]], phrase: str) -> float:
    joined = "".join(canonical(word["text"]) for word in words)
    needle = canonical(phrase)
    if not needle:
        raise ValueError("Spoken beat cannot be empty")
    boundaries, cursor = {0}, 0
    for word in words:
        cursor += len(canonical(word["text"]))
        boundaries.add(cursor)
    position = next((match.start() for match in re.finditer(re.escape(needle), joined)
                     if match.start() in boundaries and match.end() in boundaries), -1)
    if position < 0:
        raise ValueError(f"Caption alignment cannot locate spoken beat: {phrase}")
    consumed = 0
    for word in words:
        consumed += len(canonical(word["text"]))
        if consumed > position:
            return float(word["start"])
    raise ValueError(f"No measured timestamp for {phrase}")


def validate_alignment(words: list[dict[str, Any]], source: str, duration: float) -> None:
    if not words or canonical(" ".join(w["text"] for w in words)) != canonical(source):
        raise ValueError("ASR coverage differs from the spoken source")
    previous_end = 0.0
    for word in words:
        start, end = float(word["start"]), float(word["end"])
        if not np.isfinite(start) or not np.isfinite(end) or not 0 <= start < end <= duration + .06:
            raise ValueError("ASR word timing is outside the measured audio")
        if start < previous_end - .02:
            raise ValueError("ASR words overlap or are out of order")
        previous_end = end


def measured_words(whisper: Any, wav: Path, source: str) -> list[dict[str, Any]]:
    segments, _ = whisper.transcribe(str(wav), language="en", word_timestamps=True,
                                    beam_size=10, initial_prompt=source,
                                    condition_on_previous_text=False, vad_filter=False)
    words: list[dict[str, Any]] = []
    pending: list[str] = []
    for segment in segments:
        for word in segment.words or []:
            text = word.word.strip()
            if not text:
                continue
            if word.end <= word.start:
                # ASR occasionally assigns a pronoun a zero-length interval.
                # Preserve it inside the adjacent measured word bundle, never
                # invent a new uniformly-spaced acoustic boundary.
                pending.append(text)
                continue
            words.append({"text": " ".join([*pending, text]),
                          "start": round(float(word.start), 3), "end": round(float(word.end), 3)})
            pending.clear()
    if pending and words:
        words[-1]["text"] += " " + " ".join(pending)
    return words


def document_plans(project: Path, spec: dict[str, Any], ep: dict[str, Any], meta: dict[str, Any]) -> None:
    short = ep["format"] == "shorts"
    total = meta["total_duration_s"]
    canvas = "1080x1920" if short else "1920x1080"
    workflow = "faceless-explainer" if short else "general-video"
    (project / "BRIEF.md").write_text(f'''---
workflow: {workflow}
mode: autonomous
length: {"20–35 seconds" if short else "5–6 minutes"}
format: {canvas}
language: English
voice: af_heart
---

# {ep['title']}

Audience problem: {ep['audience_problem']}
Promise: {ep['packaging_promise']}

The user authorized generating three Shorts and two full videos, refining the pipeline, and pushing changes to GitHub main. Preserve the earlier approved female voice: local Kokoro af_heart, speed {spec['speed']}. No paid calls or automatic YouTube upload. No guaranteed reach, clients or income.

Business Repair Lab is an experimental broader BizNex angle: early before/after, a visible fictional worked example and a reusable action. Dark ink, warm cream and gold; ASR-measured captions and spoken-cue reveals. Reuse owned music and sound effects. Every package includes a final MP4, thumbnail, title, description, hashtags and verification report.

Analytics supplied: Sept 11–Oct 8, 2026 overview 161 views, 0.8 watch hours, +1 subscriber; Shorts search traffic 57.8%, Shorts-feed 19.0%, stayed to watch 54.2%. These channel aggregates do not establish individual-video CTR or retention failures.
''', encoding="utf-8")
    (project / "frame.md").write_text('''---
name: Business Repair Lab
colors:
  ink: "#17191c"
  cream: "#f4eedf"
  muted: "#b3b0a8"
  gold: "#efc66a"
  green: "#bce5bd"
  red: "#ffad9d"
typography:
  display: {family: Montserrat, weight: 900}
  body: {family: Montserrat, weight: 700}
  mono: {family: IBM Plex Mono, weight: 400}
spacing: {density: generous, minimum: 16, maximum: 120}
components: {corners: restrained, radius: 16, depth: flat}
---

# Case file, not a sales slide

The subject is a message or one-page offer being repaired. Ink/cream fields alternate with gold markup; green indicates a clearer option and red marks an actual caution. Type is forceful but sentence-level demo text remains readable. Keep essential content above the bottom 17%; portrait also leaves the right control rail clear. Use three semantic framings, not one card repeated forever. Message reconstructions and cafés are illustrative, not real client results.

Motion reveals each new object or line on its measured spoken cue, including the later half. Explicit paused GSAP fromTo timelines; no clock, randomness, loops, bouncing, breathing or late drifting. Short still holds allow reading. No invented success counters, earnings screenshots, client logos or forced subscribe intro.
''', encoding="utf-8")
    script = f"# SCRIPT — {ep['id']}\n\n**Voice:** Kokoro af_heart\n**Voice settings:** speed {spec['speed']}\n**Voice direction:** Warm, conversational, clear female narration.\n"
    storyboard = f'''---
format: {canvas}
duration: {total:.3f}s
message: "{ep['packaging_promise']}"
arc: how-to-process with worked example
audience: beginners building a small service business
mode: autonomous
music: minimal project-owned pulse under clear narration
---

## Video direction

Business Repair Lab palette and fonts from frame.md. Rhythm: immediate demo → diagnose → repair → self-test → usable action. Compose message, offer, comparison and checklist scenes from dynamic-content-sequencing and discrete-text-sequence. Each added line arrives on its measured phrase; do not dump the scene at its start. Alternate asymmetric, full-width and paired framings (portrait uses stacked comparisons). Foreground is the repaired object, midground its annotation, background the case-file field and section index. Deliberate still read after the last reveal; no lazy drift, breathing, random motion, fake evidence or off-brand visuals. Bottom17% reserved for captions. Scene cuts carry the same subject.
'''
    expanded = f"# Expanded production direction\n\n{ep['title']}\n\nSee frame.md for exact palette and embedded typography. Immediate demonstration, diagnosis, repair, read and action; no inflated claims or stock filler.\n"
    for i, cue in enumerate(meta["cues"]):
        end = meta["cues"][i + 1]["start"] if i + 1 < len(meta["cues"]) else total
        duration = end - cue["start"]
        src = f"compositions/frames/{cue['id']}.html"
        script += f"\n## Line {i + 1} — {cue['title']} (Frame {i + 1})\n\n**Time:** {cue['start']:.3f} – {end:.3f}s\n**Delivery:** Show the example, then land the useful repair.\n\n    {cue['text']}\n"
        shot_lines = []
        boundaries = sorted(set([0.0, *cue["beats"], round(duration, 3)]))
        for j, (a, b) in enumerate(zip(boundaries, boundaries[1:], strict=False)):
            item = cue["display"][min(j, len(cue["display"]) - 1)]
            shot_lines.append(f"Scene {j + 1} ({a:.3f}–{b:.3f}s): {cue['kind']} actor; reveal ‘{item}’ on the corresponding spoken phrase, then hold the read. Foreground object, supporting markup, case-file background.")
        storyboard += f'''\n## Frame {i + 1} — {cue['title']}

- scene: A {cue['kind']} demonstration makes the spoken advice concrete.
- duration: {duration:.3f}s
- voiceover: "{cue['text']}"
- transition_in: cut
- poster: {min(duration - .2, max(cue['beats'][-1] + .5, .8)):.3f}s
- status: outline
- src: {src}
- type: {"hook" if i == 0 else "cta" if i == len(meta['cues']) - 1 else "feature_showcase"}
- persuasion: Before/after + concretization + progressive disclosure
- beat: {"recognition and curiosity" if i == 0 else "clarity and confidence"}
- blueprint: compose
- focal: the {cue['kind']} example
- roles: repaired object = foreground · markup = supporting · case-file field = background

narrativeRole: {cue['title']}.
keyMessage: {cue['display'][-1]}

{chr(10).join(shot_lines)}
'''
        expanded += f"\n## Scene {i + 1}: {cue['title']}\n\nConcept: {cue['kind']} repair in a practical case-file lab. Mood: warm, sharp and useful. BG ink/cream field, MG example, FG gold annotations. Choreography: reveal each displayed item on the measured narration beat; hold the completed read; cut to the next demonstration.\n{chr(10).join(shot_lines)}\n"
    (project / "SCRIPT.md").write_text(script, encoding="utf-8")
    (project / "STORYBOARD.md").write_text(storyboard, encoding="utf-8")
    (project / ".hyperframes").mkdir(exist_ok=True)
    (project / ".hyperframes/expanded-prompt.md").write_text(expanded, encoding="utf-8")
    (project / "THUMBNAIL_COPY.txt").write_text(ep["thumbnail_headline"] + "\n", encoding="utf-8")
    description = ep["description"]
    if not short:
        chapters = []
        for i in [0, 3, 6, 10, 14, 16]:
            seconds = int(meta["cues"][i]["start"])
            chapters.append(f"{seconds // 60:02d}:{seconds % 60:02d} {meta['cues'][i]['title']}")
        description += "\n\nChapters:\n" + "\n".join(chapters)
    upload = f"# Upload package\n\n## Title\n\n{ep['title']}\n\n## Description\n\n{description}\n\n## Hashtags\n\n{' '.join(ep['hashtags'])}\n\n## Files\n\n- Video: renders/final.mp4\n- Thumbnail: assets/thumbnails/thumbnail.png\n- Voice: af_heart\n- Runtime: {total:.3f} seconds\n\nNo automatic upload. {('Shorts cover selection depends on the upload surface; an in-video cover is included.' if short else 'Landscape thumbnail supplied separately.')}\n"
    (project / "UPLOAD_PACKAGE.md").write_text(upload, encoding="utf-8")
    hook = ep["segments"][0]["text"].split(". ")[0]
    payoff_cue = meta["cues"][1]
    payoff = payoff_cue["text"].split(". ")[0]
    write_json(project / "EDITORIAL.json", {
        "schema_version": 1, "script": "SCRIPT.md", "thumbnail_copy": "THUMBNAIL_COPY.txt",
        "audience_problem": ep["audience_problem"], "hook": {"text": hook, "at_seconds": 0},
        "payoff": {"text": payoff, "at_seconds": payoff_cue["start"]},
        "packaging": {"title": ep["title"], "thumbnail_text": ep["thumbnail_headline"],
                      "promise": ep["packaging_promise"], "evidence_anchor": payoff, "reviewed": True},
        "sources": ep["sources"],
        "retention_beats": [{"at_seconds": cue["start"], "purpose": cue["title"]} for cue in meta["cues"]],
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--creative", type=Path, required=True)
    parser.add_argument("--only", help="Optional episode ID for a repair/retry")
    args = parser.parse_args()
    spec = json.loads(args.creative.read_text(encoding="utf-8-sig"))
    if spec["schema_version"] != 1 or spec["voice"] != "af_heart":
        raise ValueError("Unsupported schema or unapproved voice")
    ids = [ep["id"] for ep in spec["episodes"]]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Duplicate episode IDs")
    if args.only and args.only not in ids:
        raise ValueError("Unknown episode ID in --only")
    projects = [(ROOT / ep["project"]).resolve() for ep in spec["episodes"]]
    if len(set(projects)) != len(projects):
        raise ValueError("Duplicate project paths")
    kokoro = whisper = None
    manifest = []
    for ep in spec["episodes"]:
        relative = Path(ep["project"])
        if relative.is_absolute() or ".." in relative.parts or ep["format"] not in {"shorts", "youtube"}:
            raise ValueError("Invalid project path or production format")
        project = (ROOT / relative).resolve()
        contained = project.relative_to(ROOT / "videos")
        if not contained.parts:
            raise ValueError("Project must be a child of videos, not its root")
        if not (project / "BRIEF.md").exists():
            raise ValueError("Initialize and brief projects before generating audio")
        short = ep["format"] == "shorts"
        manifest.append({"id": ep["id"], "project": ep["project"], "format": ep["format"],
                         "output": "renders/final.mp4", "thumbnail": "assets/thumbnails/thumbnail.png",
                         "upload_package": "UPLOAD_PACKAGE.md", "voice_manifest": "audio_request.json",
                         "editorial_manifest": "EDITORIAL.json", "min_seconds": 20 if short else 300,
                         "max_seconds": 35 if short else 360})
        if args.only and args.only != ep["id"]:
            continue
        cache = project / ".production-cache"
        cache.mkdir(exist_ok=True)
        voice_dir = project / "assets/voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        (project / "assets/bgm").mkdir(parents=True, exist_ok=True)
        shutil.copytree(ASSET_SOURCE / "sfx", project / "assets/sfx", dirs_exist_ok=True)
        chunks, cues, words = [], [], []
        offset, rate = 0.0, 24000
        for i, segment in enumerate(ep["segments"]):
            request = {"text": segment["text"], "voice": spec["voice"], "speed": spec["speed"],
                       "lang": "en-us", "sentence_pause": .18, "clause_pause": .08, "version": 1}
            fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            wav = cache / f"{fingerprint}.wav"
            alignment = cache / f"{fingerprint}.json"
            if not wav.exists():
                if kokoro is None:
                    from kokoro_onnx import Kokoro
                    model = Path.home() / ".cache/hyperframes/tts/models/kokoro-v1.0.onnx"
                    voices = Path.home() / ".cache/hyperframes/tts/voices/voices-v1.0.bin"
                    kokoro = Kokoro(str(model), str(voices))
                samples, rate = kokoro.create(segment["text"], voice=spec["voice"], speed=spec["speed"],
                                              lang="en-us", sentence_pause=.18, clause_pause=.08)
                sf.write(wav, samples, rate)
            samples, rate = sf.read(wav, dtype="float32")
            if samples.ndim != 1 or rate != 24000:
                raise ValueError("Cached approved narration must be 24 kHz mono")
            duration = len(samples) / rate
            wav_sha = hashlib.sha256(wav.read_bytes()).hexdigest()
            if alignment.exists():
                cached = json.loads(alignment.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and cached.get("wav_sha256") != wav_sha:
                    raise ValueError("Cached audio changed after word alignment; regenerate this cue")
                aligned = cached["words"] if isinstance(cached, dict) else cached
            else:
                if whisper is None:
                    whisper = local_whisper()
                aligned = measured_words(whisper, wav, segment["text"])
            if canonical(" ".join(w["text"] for w in aligned)) != canonical(segment["text"]):
                if whisper is None:
                    whisper = local_whisper()
                aligned = measured_words(whisper, wav, segment["text"])
            try:
                validate_alignment(aligned, segment["text"], duration)
            except ValueError as error:
                print(f"SOURCE: {segment['text']}\nASR: {' '.join(w['text'] for w in aligned)}", flush=True)
                raise ValueError(f"{ep['id']} cue {i + 1}: review ASR coverage before production") from error
            write_json(alignment, {"wav_sha256": wav_sha, "words": aligned})
            beats = [round(phrase_time(aligned, phrase), 3) for phrase in segment["beat_phrases"]]
            if beats != sorted(beats):
                raise ValueError(f"{ep['id']} cue {i + 1}: spoken beat phrases are out of order")
            cues.append({**segment, "start": round(offset, 3), "end": round(offset + duration, 3), "beats": beats})
            words.extend({**w, "start": round(w["start"] + offset, 3), "end": round(w["end"] + offset, 3)} for w in aligned)
            chunks.extend([samples, np.zeros(round(.10 * rate), dtype=np.float32)])
            offset += duration + .10
            print(f"{ep['id']}: cue {i + 1}/{len(ep['segments'])}, {duration:.2f}s", flush=True)
        total = round(offset + .32, 3)
        minimum, maximum = (20, 35) if short else (300, 360)
        if not minimum <= total <= maximum:
            raise ValueError(f"{ep['id']}: measured {total}s outside {minimum}–{maximum}s; revise narration")
        chunks.append(np.zeros(round(.32 * rate), dtype=np.float32))
        sf.write(voice_dir / "01.wav", np.concatenate(chunks), rate)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1",
                        "-i", str(ASSET_SOURCE / "bgm/track.wav"), "-t", str(total), "-af",
                        f"afade=t=in:st=0:d=0.15,afade=t=out:st={total - .8:.3f}:d=0.8",
                        "-c:a", "aac", "-b:a", "192k", str(project / "assets/bgm/bed.m4a")], check=True)
        for i, word in enumerate(words):
            word["id"] = f"w{i}"
        meta = {"voice_lock": {"provider": "kokoro", "voice": spec["voice"], "speed": spec["speed"]},
                "timing_source": "faster-whisper-small.en measured ASR word alignment (estimated, not native timestamps)",
                "cues": cues, "total_duration_s": total,
                "voices": [{"frame": 1, "path": "assets/voice/01.wav", "duration_s": total, "words": words}],
                "bgm_pending": False, "bgm": {"path": "assets/bgm/bed.m4a", "duration_s": total, "volume": .055},
                "sfx": [{"file": "assets/sfx/chime.wav", "offset_s": cues[1]["start"] + .2, "duration_s": .57, "volume": .09}]}
        write_json(project / "audio_request.json", {"provider": "kokoro", "voice": spec["voice"], "speed": spec["speed"],
                    "lang": "en-us", "lines": [{"id": s["id"], "text": s["text"]} for s in ep["segments"]], "bgm": {"mode": "project-owned"}})
        write_json(project / "audio_meta.json", meta)
        write_json(project / "EPISODE.json", {**ep, "duration_s": total, "cues": cues})
        document_plans(project, spec, ep, meta)
        print(f"{ep['id']}: READY {total}s", flush=True)
    write_json(args.creative.with_suffix(".production.json"), {"schema_version": 1, "batch_id": spec["batch_id"], "expected_voice": "af_heart", "episodes": manifest})


if __name__ == "__main__":
    main()
