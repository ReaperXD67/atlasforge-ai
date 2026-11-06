# Voice direction and the local audio proof

These CLI/provider workflows require a full repository checkout. The portable cinematic source bundle supplies prepared narration and separate `sources/REBUILD.md` instructions; it does not include the general narration CLI, legacy pilot inputs or these optional local profiles.

Voice direction controls delivery without changing the approved transcript. Both
`narrate` and `narrate-script` accept `--direction path/to/plan.json`. The example
[plan](https://github.com/ReaperXD67/atlasforge-ai/blob/main/config/voice-directions/biznex-evidence-first.json) separates spoken words
from emotion, energy, pace, and pauses. A punctuation, case or word mismatch with
the narration is rejected before synthesis; whitespace differences are allowed.

| Provider | Applied controls | Report mode |
| --- | --- | --- |
| Kokoro | Configured voice; baseline speed × beat pace; explicit pauses | `pace_and_pauses_only` |
| CosyVoice 3 (optional isolated worker) | Reference voice plus semantic instructions; explicit pauses | `reference_conditioned_semantic_instructions` |
| OpenAI | Per-beat instructions and explicit pauses; requires an instruction-capable speech model | `per_beat_instructions` |
| Chatterbox | Bounded exaggeration approximation; pitch-preserving beat pace; pauses | `numeric_prosody_approximation` |
| Other configured providers | Plain approved transcript | `plain_transcript_fallback` |

Kokoro ignores emotion, energy and free-form `delivery` instructions. The system does not claim that speed or
silence expresses the requested emotion. Provider selection and fallback are written
to `narration.direction-report.json`; `semantic_emotion_supported` and
`emotion_fidelity_verified` remain false for the local Kokoro proof. Chatterbox is
retained for compatibility but its upstream is retired; see [research](https://github.com/ReaperXD67/atlasforge-ai/blob/main/docs/UPSTREAM_RESEARCH.md).

The optional CosyVoice path adds actual model instruction conditioning. It does not
establish ElevenLabs parity, guaranteed emotion fidelity, or exact speaker identity.
See [the isolated expressive voice workflow](EXPRESSIVE_VOICE.md) for its pinned
dependencies, audition method and current measured results. `delivery` is an optional
per-beat field; it remains separate from the exact spoken/caption transcript.

## Verified local proof · 6 November 2026

The same **37-word transcript** was rendered twice using the existing **af_heart**
Kokoro voice, then aligned with the cached Whisper `small.en` model. Both real CLI
calls completed with Hugging Face and Transformers offline flags enabled, a local-only
provider list, and no paid API call or model download.

| Measurement | Baseline | Directed |
| --- | --- | --- |
| WAV duration | 14.175 s | 15.575 s |
| Format | 48 kHz mono | 48 kHz mono |
| Voice | `af_heart` | `af_heart` |
| Kokoro speed | 0.97 | 0.9215 → 0.873 → 0.97 |
| Explicit inserted silence | None requested | 300 ms and 400 ms |
| Exact script words / caption cues | 37 / 11 | 37 / 11 |
| Last word end | 13.48 s | 14.92 s |
| Caption timing | Monotonic; inside audio | Monotonic; inside audio |
| Peak sample amplitude | 0.8414 | 0.8414 |

The directed raw waveform contains exactly 7,200 zero samples at 3.800–4.100 s
and 9,600 at 6.675–7.075 s, measured at its 24 kHz generation rate. These are added
pauses; the speech itself can contain natural silence. The mastered export is 1.4 s
longer. Caption text matched the approved transcript; cue bounds were checked
against both exported WAV durations. Canonical caption alignment does not by itself
prove that the synthesizer pronounced every word correctly.
This proves usable rhythm control with the retained narrator. Listener preference,
semantic emotion fidelity and improved audience retention have **not** been established.

The local deliverables are intentionally Git-ignored:

```text
output/social/voice-proof/
  transcript.txt
  verification.json
  baseline/narration.wav
  baseline/narration.exact.srt
  baseline/narration.direction-report.json
  directed/narration.wav
  directed/narration.exact.srt
  directed/narration.performance.json
  directed/narration.direction-report.json
```

## Reproduce with cached models

Run from the repository root. The [local-only profile](https://github.com/ReaperXD67/atlasforge-ai/blob/main/config/profiles/biznex-local-voice-proof.yaml)
selects only Kokoro `af_heart` and CPU/int8 Whisper alignment. This requires the
existing `local-tts` and `transcription` extras, FFmpeg, and cached Kokoro/Whisper
assets. Offline mode deliberately fails if required model files are unavailable.

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HOME = Join-Path $env:USERPROFILE '.cache\huggingface'

.\.venv\Scripts\python.exe -c "from pathlib import Path; from daily_video_factory.voice_direction import VoiceDirection; p=Path('output/social/voice-proof'); p.mkdir(parents=True,exist_ok=True); p.joinpath('transcript.txt').write_text(VoiceDirection.load(Path('config/voice-directions/biznex-evidence-first.json')).narration,encoding='utf-8')"

.\.venv\Scripts\python.exe -m daily_video_factory.cli narrate `
  --text-file output/social/voice-proof/transcript.txt `
  --output output/social/voice-proof/baseline `
  --config config/profiles/biznex-local-voice-proof.yaml

.\.venv\Scripts\python.exe -m daily_video_factory.cli narrate `
  --text-file output/social/voice-proof/transcript.txt `
  --output output/social/voice-proof/directed `
  --config config/profiles/biznex-local-voice-proof.yaml `
  --direction config/voice-directions/biznex-evidence-first.json
```

On the tested workstation, Windows Application Control blocked the generated
`atlasforge.exe` launcher; the equivalent Python module invocation above worked.
Its normal user Hugging Face cache contained complete Kokoro files. The separate
project-local cache had unusable snapshot links, so it was not used or modified.

`--target-seconds` remains available on both narration commands. It resizes the
finished delivery and caption timings together, so it also changes the duration
of inserted pauses. Omit it when preserving the direction plan's timing matters.

## Checks

The focused voice/provider suite passes 31 tests, including instruction/transcript
separation, oversized-sentence handling, Kokoro identity/speed/pause routing,
Chatterbox routing, exact text validation and stale-caption cleanup on fallback.
The two existing CLI tests also pass. Actual baseline and directed CLI executions
establish that the added `--direction` option reaches the new runtime correctly.

## First six pilot production audio

The [first-six production manifest](https://github.com/ReaperXD67/atlasforge-ai/blob/main/config/batches/biznex-first-six.production.json)
now points to six prepared projects with actual directed `af_heart` narration,
measured captions, and original scored stereo mixes. Audio preparation and the
source/story/packaging validators completed successfully on 6 November 2026.
This table records **audio readiness**; final video delivery is established by the
render batch's `BATCH_REPORT.json`.

| Project under `videos/` | Timeline / stereo mix duration |
| --- | --- |
| `biznex-two-paper-doors` | 27.500 s |
| `biznex-card-under-the-cup` | 26.500 s |
| `biznex-missing-index-card` | 26.900 s |
| `biznex-two-ribbons` | 26.500 s |
| `biznex-receipt-fold` | 26.066667 s |
| `biznex-three-empty-boxes` | 30.766667 s |

Each project contains `assets/audio/final_mix.wav` (48 kHz stereo), the separate
narration, score and foley, captions, provenance, `timing.json`, `EDITORIAL.json`,
`SCRIPT.md` and publishing copy. Word anchors use ASR evidence constrained to each
beat's known synthesis sample window, preventing a missed character name from
occupying the preceding silent pause. The mix is padded only with silence to the
next 30 fps frame boundary; audio is never cut to meet the duration gate.

Rebuild all audio/data using the cached local engines:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_pilot_batch.py
```

The preparer reuses a single Kokoro pipeline and resumes matching narration from
its fingerprint. It does not change HTML/CSS/JavaScript compositions. Once visual
checks and the six required thumbnails are ready, the existing delivery runner
serializes rendering, mastering, and verification:

```powershell
.\.venv\Scripts\python.exe -m daily_video_factory.cli render-production-batch `
  --manifest config/batches/biznex-first-six.production.json --dry-run

.\.venv\Scripts\python.exe -m daily_video_factory.cli render-production-batch `
  --manifest config/batches/biznex-first-six.production.json --resume
```

The runner checks each composition before encoding, creates a temporary render,
masters stereo AAC audio, validates media/voice/thumbnail/editorial evidence, and
promotes only a verified file to `renders/final.mp4`. Keep project sources frozen
during each render; a changed source fingerprint fails the delivery gate.
