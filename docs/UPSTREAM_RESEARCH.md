# Social production and expressive voice research

Inspected **6 November 2026**. This record distinguishes upstream capabilities,
our implementation decisions, and results that still need audience or listening tests.
No proprietary ElevenLabs code, voice, account, or model was reverse engineered.

## Decisions and provenance

| Source and inspected revision | License and maintenance evidence | Fit and decision |
| --- | --- | --- |
| [latent-spaces/brag 0.5.0, `669ab928`](https://github.com/latent-spaces/brag/tree/669ab9286aa28b6c3ee30e75f181ee74319d012a) | [MIT](https://github.com/latent-spaces/brag/blob/669ab9286aa28b6c3ee30e75f181ee74319d012a/LICENSE); release commit 23 October 2026; repository not archived. Bundled music has separate CC BY 4.0 attribution. | **Adapt the workflow**, not another renderer. It is a project launch-video skill using HyperFrames, with concept, composition, poster, and share-copy gates. AtlasForge already renders HyperFrames. Useful principles are product-specific proof, an immediate question, readable text holds, and a deliberately chosen poster. It is not evidence of viral reach or a social-account manager. No upstream code or media copied. |
| [resemble-ai/chatterbox, `ab55923c`](https://github.com/resemble-ai/chatterbox/tree/ab55923c27757c90cfcc407baa57dc25a7d25217) | [Code MIT](https://github.com/resemble-ai/chatterbox/blob/ab55923c27757c90cfcc407baa57dc25a7d25217/LICENSE); [model card MIT](https://huggingface.co/ResembleAI/chatterbox). The 4 November README update explicitly says it is retired research, unmaintained since August 2026, despite the GitHub archived flag being false. | **Retain existing compatibility; defer expansion.** The repository already pins `chatterbox-tts==0.1.7`. Its `generate()` accepts exaggeration, CFG, temperature and a voice reference. Existing PyTorch/torchaudio and model downloads are substantial. New per-beat numeric controls reuse that adapter; they do not make semantic emotion fidelity measurable. Preserve its watermarking. No new model installed. |
| [QwenLM/Qwen3-TTS, `022e286b`](https://github.com/QwenLM/Qwen3-TTS/tree/022e286b98fbec7e1e916cb940cdf532cd9f488e) | [Code Apache-2.0](https://github.com/QwenLM/Qwen3-TTS/blob/022e286b98fbec7e1e916cb940cdf532cd9f488e/LICENSE); [1.7B VoiceDesign weights Apache-2.0](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign). Latest inspected commit fixes fine-tuning on 17 March 2026; not archived, but this is not proof of frequent current maintenance. | **Defer adoption; prioritize an isolated comparison.** Instruction-driven voice design fits an original brand narrator. `qwen-tts` 0.1.1 pins transformers 4.57.3 and accelerate 1.12.0, plus torchaudio, Gradio, SoX and ONNX Runtime. That is too much to add to the main runtime without measurements. The 1.7B model's raw BF16 parameters alone imply roughly 3.4 GB before activations and other models; 8 GB GPU fit is an inference, not a tested guarantee. Hindi is absent from the listed ten-language release. |
| [SWivid/F5-TTS, `600e5fdf`](https://github.com/SWivid/F5-TTS/tree/600e5fdfbf319f84735557aca80a7aaf60d487e6) | Code MIT; pretrained [model license CC BY-NC 4.0](https://huggingface.co/SWivid/F5-TTS), confirmed by the repository README. Maintainer compatibility fix on 3 November 2026. | **Defer for this commercial advertising pipeline.** Multi-style/chunk inference is relevant, but code licensing does not grant commercial use of the published weights. A separately licensed model would need its own review. CUDA/PyTorch/vocoder and optional ASR add memory and packaging cost. No code or weights installed. |
| [m-bain/whisperX, `5d3678b8`](https://github.com/m-bain/whisperX/tree/5d3678b8535698a2826a5db9eb3e4105aef85dd9) | [BSD-2-Clause code](https://github.com/m-bain/whisperX/blob/5d3678b8535698a2826a5db9eb3e4105aef85dd9/LICENSE). Maintainer merged optional-torchaudio alignment support on 22 October 2026. Alignment and diarization weights have separate model terms. | **Adapt the alignment principle, defer dependency.** AtlasForge already aligns approved text and stores word times with faster-whisper. WhisperX adds alignment, PyTorch 2.8, torchvision and pyannote components. Diarization is unnecessary for a single owned narrator. Test a caption-timing corpus first; add this only if it beats current alignment enough to justify the stack. |

Repository metadata, revision dates, licenses, relevant source and package manifests
were read from primary GitHub sources; model terms were checked on their publisher's
Hugging Face cards. Repository stars are not used as a quality measurement. A license
on software or weights does not grant rights to someone else's voice recording.

## What changed in AtlasForge

An optional `VoiceDirection` plan keeps each spoken beat separate from emotion,
energy, pace, and the following pause. It rejects transcript drift, unknown fields,
unsupported emotion labels, empty beats, and out-of-range controls. Instructions are
never inserted into the spoken text or captions.

- OpenAI's existing adapter sends separate instructions for each beat and assembles
  the requested pauses. Its configured speech model must support instructions.
- The existing Chatterbox adapter maps labels to bounded exaggeration, adjusts
  individual beats with pitch-preserving tempo processing, and keeps planned pauses.
  It bypasses the old global words-per-minute pass for directed narration.
- Kokoro retains the configured voice, multiplies its baseline speed by each beat's
  pace, and inserts the requested pauses. Its report explicitly lists emotion and
  energy as ignored; this controls rhythm, not semantic emotion.
- Other providers receive the approved plain transcript. The report says that
  direction was not applied; fallback never implies equivalent expression.
- All narration writes `narration.direction-report.json` with selected provider,
  configured order, attempted providers, fallback state, duration and direction mode.
  `emotion_fidelity_verified` remains false until an actual listening evaluation.
- Long sentences now respect provider character limits without losing words. An
  oversized single token fails explicitly. Failed providers cannot leave stale word
  timestamps that are silently reused for a different voice.

This implementation uses original project code and existing dependencies. The
research informed integration choices; no upstream skill, code, asset or model was
vendored. Existing provider and voice settings remain valid.

## Use a directed narration plan

Start from [the example plan](../config/voice-directions/biznex-evidence-first.json).
Each beat contains `text`, one of `neutral`, `curious`, `serious`, `reassuring`, or
`excited`, `energy` from 0 to 1, `pace` from 0.85 to 1.15, and `pause_after_ms` from
0 to 1500. The final beat has no trailing pause. The plan is production direction,
not a new unreviewed script: its concatenated text must match the approved narration.

```python
from pathlib import Path
from daily_video_factory.config import load_settings
from daily_video_factory.media.ffmpeg import FFmpeg
from daily_video_factory.providers.tts import NarrationGenerator
from daily_video_factory.voice_direction import VoiceDirection

settings = load_settings(Path("config/default.yaml"))
plan = VoiceDirection.load(Path("config/voice-directions/biznex-evidence-first.json"))
result = NarrationGenerator(settings, FFmpeg()).run(
    plan.narration, Path("output/voice-audition"), direction=plan,
)
print(result.provider, result.value)
```

The configured provider order still controls billing and availability. Calling this
example may call a configured paid provider; no paid audition was run for this change.
Exact duration fitting, when explicitly requested by the caller, can scale the whole
delivery after synthesis; review the final timing before rendering story beats.

## Validation and acceptance criteria

Tests cover long sentences and paragraph boundaries, transcript preservation,
OpenAI's instruction/text separation, Chatterbox beat controls and pauses, stale
caption cleanup, and honest fallback reporting. They use fake providers and audio
arrays; passing tests establishes routing and timing behavior, not perceived quality.

Before switching the brand narrator, compare the existing `af_heart` voice against
an original or explicitly authorized candidate using the same short scripts. Keep
pronunciation mistakes, word omissions, listening preferences, synthesis time,
GPU memory and cost per finished minute. The [local voice proof](VOICE_DIRECTION.md)
uses the existing `af_heart` narrator. Retain the old narrator unless the new one
improves that comparison. Then compare retention on original published episodes;
voices, effects and repository popularity cannot by themselves establish reach.
