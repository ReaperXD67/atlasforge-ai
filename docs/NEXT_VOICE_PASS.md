# Next-video voice performance lab

This experiment applies only to future videos. **The Second Question** and its
production inputs remain unchanged. The existing voice provider, pinned model and
synthetic af_heart reference are reused; this adds no model download or paid call.

## Decision and primary-source review · 6 November 2026

The current delivery is technically intelligible, but its emotional performance
was not validated by a listening panel. Fourteen separately generated short takes
can reset phrasing. Broad English acting descriptions are experimental, and a
neutral synthetic reference supplies limited human expressive detail. These are
plausible limitations, not a proven diagnosis of every audible issue.

| Candidate / inspected revision | License, maintenance and cost | Decision |
| --- | --- | --- |
| [CosyVoice3](https://github.com/QwenAudio/CosyVoice/tree/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc), same pinned commit; latest commit 25 May 2026 UTC, not archived | Apache-2.0 code and model card; MIT Matcha dependency. Already installed. Prior measured peak PyTorch allocation 3.512 GiB; cold load 32.455 s. Its [instruction list](https://github.com/QwenAudio/CosyVoice/blob/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc/cosyvoice/utils/common.py) and [tokenizer](https://github.com/QwenAudio/CosyVoice/blob/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc/cosyvoice/tokenizer/tokenizer.py) expose soft/happy/sad controls and native breath/sigh/emphasis tokens. | **Adapt first:** compare thought groups, documented templates and a restrained native cue, preserving the same words/reference/seed. Token support does not establish a natural result. |
| [Chatterbox Turbo](https://github.com/resemble-ai/chatterbox/tree/ab55923c27757c90cfcc407baa57dc25a7d25217), 4 November 2026; [weights](https://huggingface.co/ResembleAI/chatterbox-turbo/tree/749d1c1a46eb10492095d68fbcf55691ccf137cd), 15 December 2025 | MIT code and weights; maintained, 350M model, distilled one-step decoder and native reaction tags. Current source **ignores `exaggeration`, `cfg_weight` and `min_p`** in Turbo. Python 3.11 dependency pins include Torch 2.6, Transformers 5.2, Gradio 6.8 and an unpinned Perth Git dependency; watermarking is built in. | **Defer installation:** reactions could justify a controlled later trial, but it is not an emotion-strength upgrade. Another isolated stack/download needs a measurable benefit over installed CosyVoice. Maintainer efficiency claims have not been benchmarked here. |
| [Pocket TTS](https://github.com/kyutai-labs/pocket-tts/tree/0d2010682f3ec336890f55cb2acc0f22abbc1d8d), 5 November 2026; [weights](https://huggingface.co/kyutai/pocket-tts/tree/db04f0e653473e5c7333c69686ac92b7460b0c1d), 21 October 2026 | **MIT code; CC-BY-4.0 model weights**, with a gated access agreement. Active 4.0.1 package, CPU voice cloning; 100M and newer 18.2M/6.9M/1.9M variants. Torch ≥2.5, NumPy ≥2; exported voice states avoid repeated reference processing. Official CPU speed claims are hardware-specific and unmeasured locally. | **Defer for emotion; consider for fast drafts:** no explicit emotional instruction API was established in this review, and inline silence is listed unsupported. Small size alone is not evidence of a better performance. |

No upstream code was copied for this lab. Native control strings are used through
the existing Apache-licensed model API. Detailed existing model/runtime provenance
and setup remain in [EXPRESSIVE_VOICE.md](EXPRESSIVE_VOICE.md).

## Controlled comparison

[`next-video-audition.json`](../config/expressive-voice/next-video-audition.json)
contains a new fictional decision scene, not the next video's final approved script.
Every version has the same clean transcript, seed and hashed synthetic reference:

1. Separate sentences with broad acting instructions.
2. Complete thoughts using the same instructions.
3. Complete thoughts using documented soft, neutral and happy templates.
4. The same templates with one native breath at the question.

The comparisons isolate useful choices: grouping, instruction specificity, then
one nonverbal cue. Appended silence is reported separately from generated speech.
The model runs once for all takes, speed stays 1.0, and there is no pitch/tempo DSP.

From a prepared full checkout:

```powershell
.venv/Scripts/python.exe scripts/voice_performance_lab.py `
  --plan config/expressive-voice/next-video-audition.json `
  --output output/expressive-voice/next-video-audition --mode prepare

.venv/Scripts/python.exe scripts/voice_performance_lab.py `
  --plan config/expressive-voice/next-video-audition.json `
  --output output/expressive-voice/next-video-audition --mode run
```

`prepare` validates without inference. `run` invokes the unchanged isolated worker
once, strips application credentials, runs cached independent CPU ASR and exports
four comparison WAVs plus `experiment-results.json`. It refuses to overwrite
existing takes and only writes under ignored `output/`. Use a fresh directory for
another run. `--mode summarize` rebuilds comparison WAVs/reports from existing
hash-checked takes without model inference.

Native synthesis tags are excluded from caption text. Changed/missing words,
unknown controls, wrong reference hashes, altered takes and incomplete evidence
are rejected. ASR mismatches remain visible; none are silently repaired or selected.
The report provides cold-load time, per-variant inference time, real-time factor,
memory and transcript evidence. It deliberately does not auto-select a winner.

Listen for intention, continuity, credible breathing, restraint and persona
consistency. Record a preference separately from transcript correctness. Increased
pitch variation, longer duration or an ASR pass cannot establish human emotion,
speaker identity, retention or ElevenLabs parity.

## Measured audition

The real local comparison completed all 15 takes with one model load. Cold load
was **34.437 s**, measured model-session time **177.885 s**, and peak PyTorch allocation
**3.514 GiB**. The session timer excludes earlier model-file hashing/imports and later CPU ASR. All generated samples were finite and
unclipped. The original reference SHA-256 remained
`45b687b4567ca160de01382212e4bd0860c75b163175650b1ee5b65add438da6`.

| Variant | Final audio | Synthesis time | Inference RTF¹ | Independent ASR |
| --- | ---: | ---: | ---: | --- |
| A: separate sentences | 16.41 s | 39.440 s | 2.602 | 6/6 match |
| B: complete thoughts, same instructions | 18.18 s | 34.649 s | 1.982 | 3/3 match |
| C: documented templates | 19.50 s | 36.625 s | 1.948 | 2/3 match; `asked` recognized as `ask` |
| D: templates plus one native breath | 19.58 s | 32.539 s | 1.724 | 3/3 match |

¹ Inference seconds divided by generated speech seconds, excluding cold load and
authored silence. Lower is faster. This is one ordered trial, not a randomized
hardware benchmark; warm-up/order can affect comparisons. B used 12.1% less
synthesis wall time than A on this run. It provides the conservative structural
choice for the next film: fewer independent resets with every word recognized.
No listening winner is asserted. D's recognized words do not prove its breath
sounds natural, so the new film does not automatically inherit that cue.

Actual WAVs and receipts are retained under ignored
`output/expressive-voice/next-video-audition/`: `a-fragments.wav`, `b-thoughts.wav`,
`c-presets.wav`, `d-native-cue.wav`, `experiment-results.json`, the original worker
report and independent ASR evidence. The failed C comparison remains available.

## Prepare a future film

The separate [`prepare_story_voice.py`](../scripts/prepare_story_voice.py) command
accepts a new project's exact `script.txt` and a single performance plan. The plan
has the same reference/hash/seed/transcript fields as the audition, followed by
`beats` instead of `variants`. Each beat has clean `text`, a documented `preset`
or experimental `delivery`, optional allowlisted `synthesis_text` cues, and an
optional `pause_after_ms`. Full thoughts can contain several visual sentence beats.

```powershell
.venv/Scripts/python.exe scripts/prepare_story_voice.py `
  --project videos/biznex-the-yes-machine `
  --plan config/expressive-voice/biznex-the-yes-machine.json `
  --output output/expressive-voice/the-yes-machine --mode prepare

.venv/Scripts/python.exe scripts/prepare_story_voice.py `
  --project videos/biznex-the-yes-machine `
  --plan config/expressive-voice/biznex-the-yes-machine.json `
  --output output/expressive-voice/the-yes-machine --mode run
```

`prepare` and `export` require a new project. `run` can resume a completed voice
stage only after verifying the exact script, semantic performance plan, every
canonical audio/caption/take hash and independent ASR evidence. Changed inputs
fail with a fresh-project instruction; they never overwrite a finished version.
`--mode verify` performs that read-only check explicitly. `--mode export` can
consume an existing successful worker/ASR run without running the model again.
Any ASR mismatch blocks export. Portable project `VOICE_PLAN.json` files may use
plan-relative reference paths; the reference still must match its recorded hash.

Verified exports include 48 kHz `assets/audio/narration.wav`, exact `narration.srt`,
root `timing.json` with per-word/phrase timing and 30 fps rounded duration, and
`VOICE_DELIVERY.json` with narration/reference/timing/SRT hashes. Original selected
takes and portable performance/ASR/reference provenance accompany the audio.
All word anchors come from independent per-take evidence bounded by actual sample
counts; no even-word timing is substituted. Caption words remain the approved
script even when synthesis uses a nonverbal control. Production export requires
matching recognized words and intact hashes; emotion and identity flags remain
unverified until a separate listening review.

The first new-film integration, **The Yes Machine**, delivered **26.270 s** of
narration for **54 approved words**, with a **26.300 s / 789-frame** timeline.
All five thought groups passed independent ASR on the first run. Model-session time was
**78.759 s** including model loading, excluding preflight/imports and ASR. Its SHA-256 is
`450c5fd365282b9806c726b77d97622407034ad76eea0ed6c78609d6ec707ed0`.
The script uses candid, rueful, quiet, curious and relieved semantic directions;
no laugh/breath cue was auto-selected from the audition. The old film's frozen
source files and final video were rechecked against their prior hashes and remain
unchanged. This describes verified voice preparation; final rendering is a
separate pipeline stage.
