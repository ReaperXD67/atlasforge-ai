# Local expressive narration

This optional regeneration guide assumes a full repository checkout and a separately installed model runtime. A portable prepared film already includes its narration; follow the archive's `sources/REBUILD.md` to render it without regenerating speech. Online configuration links below refer to full-repository extras omitted from the minimal bundle.

The optional `cosyvoice3` provider runs a separately installed model worker. It
conditions synthesis on an authorized reference recording and an instruction for
each beat. The normal Kokoro provider remains unchanged as the default local
narrator. Existing published pilots are not rebuilt by this workflow.

## Research decision · 6 November 2026

| Candidate and inspected source | License and maintenance evidence | Decision for this voice |
| --- | --- | --- |
| [CosyVoice 3](https://github.com/QwenAudio/CosyVoice/tree/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc), commit `074ca6d` (26 May 2026); [0.5B model](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512/tree/29e01c4e8d000f4bcd70751be16fa94bf3d85a18), revision `29e01c4` (3 February 2026) | Apache-2.0 code; model card declares Apache-2.0 weights. Matcha-TTS submodule `dd9105b34bf2be2230f4aa1e4769fb586a3c824e` uses MIT. Current repository is not archived. | Trial: `inference_instruct2` combines a reference waveform with emotion/delivery instructions. The 0.5B LLM is accompanied by flow/vocoder/tokenizer models, so actual memory/download costs exceed the headline model size. |
| [IndexTTS2](https://github.com/index-tts/index-tts/tree/d9e41aac89fd00b3d71497fddb287b7f24613712), commit `d9e41aa` (29 September 2026) | Current [Bilibili Model Use License](https://github.com/index-tts/index-tts/blob/d9e41aac89fd00b3d71497fddb287b7f24613712/LICENSE) covers code, weights and outputs/derivatives. It grants royalty-free use subject to restrictions, including large-business thresholds and downstream obligations; it is not MIT/Apache. | Defer for this commercial pipeline. Emotion vectors/reference conditioning are relevant, but the custom terms and larger dependency stack are less suitable than the Apache candidate. |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS/tree/022e286b98fbec7e1e916cb940cdf532cd9f488e), commit `022e286` (17 March 2026) | Apache-2.0 code and published model cards. Maintainer package pins Transformers 4.57.3; separate model variants have different controls. | Defer: the [Base voice-cloning model](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) lacks the instruction-control flag that 1.7B CustomVoice and VoiceDesign expose. CustomVoice controls preset speakers, so substituting it would not preserve the requested af_heart reference. |
| [ElevenLabs v4](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/how-do-audio-tags-work-with-eleven-v3-and-v4) | Proprietary hosted service, not an upstream implementation to copy. Current official docs recommend v4 and describe emotion, delivery and reaction tags. | Capability reference only. No paid call, model extraction or proprietary implementation reuse. No local-quality parity claim. |

CosyVoice's official instruction examples include happy/sad/angry delivery and soft
or loud speech. Broader English directions are experimental requests; a successful
API call does not prove that the performance followed them. English narration is
supported. Hindi is not listed among the nine supported languages of this model.

## Isolation and provenance

Source and model data live under ignored `models/`; audio lives under ignored
`output/expressive-voice/`. No checkpoints, reference WAVs or credentials belong in
Git. The provider strips application API/token environment variables before launching
the worker, and the worker sets Hugging Face/Transformers offline mode.

The worker verifies the pinned source commit, rejects tracked source modifications,
and hashes all 16 model/config files against
[`cosyvoice3-model-lock.json`](../config/expressive-voice/cosyvoice3-model-lock.json)
before loading. Reference identity and provenance are recorded in the report.
The reference is our original Kokoro af_heart synthesis, not an unauthorized human
recording. Both neutral and directed takes use that exact same reference and seed.

The Windows trial uses Python 3.11.9. The upstream dependency recommendations are
captured in the [inference requirements](../config/expressive-voice/cosyvoice3-requirements.txt).
The available CUDA packages were copied into the isolated environment from the
existing local ComfyUI installation: Torch 2.13.0+cu130 and torchaudio 2.11.0+cu130.
The original ComfyUI environment was not altered. This differs from upstream's
Torch/torchaudio 2.3.1 recommendation. The full resolved package list is in
[`cosyvoice3-windows-freeze.txt`](../config/expressive-voice/cosyvoice3-windows-freeze.txt).
A small worker adapter reads the local PCM reference through SoundFile because
newer torchaudio routes audio loading through TorchCodec; acoustic model code and
weights are unchanged. ONNX reference tokenization runs on CPU; the speech model
uses CUDA fp16. TensorRT, vLLM, FlashAttention and web servers are not required.

For a fresh Windows checkout with Python 3.11, `uv`, NVIDIA CUDA 13 driver support
and enough disk space, the corresponding pinned setup is below. The CUDA wheel
versions were confirmed on the official PyTorch index; the tested workstation
reused existing copies to avoid downloading those large wheels again.

```powershell
git clone https://github.com/QwenAudio/CosyVoice.git models/upstream/CosyVoice
git -C models/upstream/CosyVoice checkout 074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc
git -C models/upstream/CosyVoice submodule update --init --recursive
uv venv models/runtime/cosyvoice --python .venv/Scripts/python.exe
uv pip install --python models/runtime/cosyvoice/Scripts/python.exe `
  "torch==2.13.0+cu130" "torchaudio==2.11.0+cu130" `
  --index-url https://download.pytorch.org/whl/cu130
uv pip install --python models/runtime/cosyvoice/Scripts/python.exe `
  -r config/expressive-voice/cosyvoice3-requirements.txt `
  --build-constraint config/expressive-voice/build-constraints.txt `
  --index-url https://pypi.org/simple
.venv/Scripts/python.exe scripts/download_expressive_voice.py
uv pip check --python models/runtime/cosyvoice/Scripts/python.exe
```

The model download helper uses bounded public HTTPS ranges, resumes completed
parts and installs a file only after its publisher hash matches. It verifies all
16 pinned assets. It does not use a paid inference endpoint. The tested local
environment contains 106 compatible packages according to `uv pip check`.

## Audition and integration

The [three-line audition request](https://github.com/ReaperXD67/atlasforge-ai/blob/main/config/expressive-voice/af-heart-audition.json)
specifies a soft admission, a vulnerable question and a happy resolution. It uses
the exact supported instruction templates to establish a strong initial comparison.
Free-form hero delivery is recorded separately in the
[hero direction plan](https://github.com/ReaperXD67/atlasforge-ai/blob/main/config/voice-directions/biznex-second-question.json).
The reference WAV is supplied in the local/source delivery bundle at
`videos/biznex-second-question/assets/audio/voice-reference.wav`, beside portable
provenance including its transcript and SHA-256. Git intentionally excludes audio;
a source-only clone needs that bundle or a newly generated authorized reference
with updated provenance before narration can run.

After the pinned runtime and model files are present, run from the repository root:

```powershell
models/runtime/cosyvoice/Scripts/python.exe scripts/expressive_voice_worker.py `
  --request config/expressive-voice/af-heart-audition.json `
  --output output/expressive-voice/af-heart-audition `
  --neutral-comparison
```

Outputs contain separate neutral/directed takes, concatenated WAVs and an
`audition-report.json`. The report records text, instruction, seed, reference hash,
generation duration, inference time and peak GPU memory. Pauses are explicit silence;
speed stays 1.0 and no pitch or tempo effect is applied to simulate emotion.
`emotion_fidelity_verified` and `speaker_similarity_verified` stay false until an
actual listening review establishes a narrower claim. Numerical differences between
waveforms alone are not such a review.

To select the worker through the existing narration CLI, configure
`voice.providers: [cosyvoice3]`, its Python/upstream/model paths, an existing
`cosyvoice_reference_audio` and a nonempty `cosyvoice_reference_provenance`.
`narrate --direction ...` preserves the exact caption text and records provider
selection/fallback. A single-provider profile fails rather than silently substituting
a less expressive narrator. The worker timeout is configurable; its log is retained.
CosyVoice ignores the generic numeric `energy` and `pace` fields; delivery is model
instruction conditioning plus authored pauses, not hidden waveform manipulation.
The performance report records those ignored numeric controls explicitly.

The [local expressive profile](https://github.com/ReaperXD67/atlasforge-ai/blob/main/config/profiles/biznex-expressive-local.yaml) selects
only this worker. The hero command is:

```powershell
$env:HF_HOME = Join-Path $env:USERPROFILE '.cache\huggingface'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.venv/Scripts/python.exe -m daily_video_factory.cli narrate `
  --text-file videos/biznex-second-question/script.txt `
  --direction config/voice-directions/biznex-second-question.json `
  --config config/profiles/biznex-expressive-local.yaml `
  --output output/expressive-voice/hero-directed
```

## Current measured state

The real six-take audition completed on the RTX 4070 8 GB laptop GPU. Every take
uses the same 14.175-second original af_heart reference, seed 1986 and speed 1.0.

| Line / requested performance | Neutral | Directed | Independent `small.en` ASR |
| --- | --- | --- | --- |
| Admission / very soft voice | 2.28 s | 3.12 s | Both match the approved words |
| Vulnerable question / very sad | 3.88 s | 8.52 s | Directed matches; neutral recognizes `what is` instead of `what if` |
| Resolution / very happy | 5.52 s | 4.48 s | Both match the approved words |

All samples are finite and unclipped at the digital full-scale threshold. The
audition took **89.713 s**, including **32.455 s** model load, with peak PyTorch
allocation **3.512 GiB** and reservation **3.797 GiB**. These are PyTorch memory
statistics, not total operating-system memory. Reference features were extracted
once per type; text instructions were freshly encoded for every take. An initial
CUDA context initialization error was resolved by creating the CUDA context before
the large CPU model construction; the successful run exercised all six takes.

Listen to the ignored local artifacts in `output/expressive-voice/af-heart-audition/`:
`neutral.wav`, `directed.wav`, or `ab-comparison.wav` (**31.85 s**, each line neutral
then directed). The ordering and measured evidence are in
`ab-comparison-order.json`, `audition-report.json` and
`audition-independent-evidence.json`. Audio differences and transcript agreement
demonstrate working conditioned synthesis, not a subjective emotion/identity score
or ElevenLabs parity. The neutral recognition mismatch remains in the evidence.

The final hero narration is **40.760 seconds**, with **87 approved words** across
14 selected takes. Independent per-take ASR matches all selected text after case,
punctuation and `signup`/`sign-up`/`sign up` spelling normalization. Two original
takes were rejected: the recognizer heard an unclear signup word and the wrong
brand name. The final version replaces only those takes. The brand line uses seed
1987 with the exact original text; the signup line uses the original seed/direction
and a speech-only `signup → sign-up` pronunciation hint. Captions keep `signup`.
Both selected repairs passed ASR. Failed takes remain in ignored working output.

`scripts/assemble_expressive_takes.py` checks ASR acceptance, canonical text,
direction/seed, model/reference consistency and audio hashes before joining selected
takes. It derives word timing from each take's independent ASR and measured sample
offset, avoiding a whole-recording alignment error that placed a word outside its
known synthesis beat. `scripts/export_hero_voice_timing.py` then checks monotonicity
and bounds and exports the expressive variant. No narration was time-stretched.

The canonical project inputs are `assets/audio/narration.wav`, `narration.srt` and
`timing.json`; the timeline is **40.766667 s at 30 fps**. Selected take WAVs, portable
performance/ASR receipts, reference provenance and the A/B audition are retained
under `assets/audio/`. `VOICE_DELIVERY.json` records the final narration hash:
`60c3aefa827d175881b9136b9eccdfe1dc78c3bd9a9d1086108df18a5e0500ea`.
This establishes the audio delivery, not the separate final-video render result.

The original **40.085 s** Kokoro development baseline is retained as
`assets/audio/narration-baseline.wav` with `baseline-timing.json`. It demonstrates
rhythm and timing, while the final optional CosyVoice voice uses semantic instruction
conditioning. Subjective voice preference and emotion fidelity remain listening
judgments; no audience-reach or ElevenLabs-equivalence result has been established.
