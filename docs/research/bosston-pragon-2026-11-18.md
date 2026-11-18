# BOSSTON | Pragon: lyric-film pipeline decisions

Reviewed 18 November 2026 for the supplied Chinese song and reference branding.
The immediate goal is a full-song film whose supplied lyrics retain their spelling,
follow the vocals, and drive distinct verse, bridge and chorus treatments. Musical
energy can drive picture changes; a beat grid cannot establish sung-word timing.

## Existing implementation and local evidence

[`lyrics.py`](../../src/daily_video_factory/lyrics.py) already splits CJK characters,
matches supplied text against Faster Whisper observations in monotonic order, and
labels interpolated character timing. This protects repeated hooks from moving
backwards and keeps ASR spelling out of the displayed lyrics. The cue exporter
requires at least 62% observed anchors and valid, nonoverlapping bounds. Below that
threshold it writes a review draft rather than a ready cue export.

The local environment reports Faster Whisper 1.2.1, CTranslate2 4.8.1, PyTorch 2.13.0,
librosa 0.11.0 and Demucs 4.1.0. This is package metadata, not proof that all native
imports or models work. A multilingual Faster Whisper small model is cached.
WhisperX, stable-ts, qwen-asr, beat-this and torchaudio are not installed in this
environment. Installed FFmpeg 9.0 enables libass, HarfBuzz, x264 and NVENC.

## Primary-source comparison

| Source inspected | License and maintenance evidence | Decision and cost |
| --- | --- | --- |
| [Faster Whisper `6cb639e7`](https://github.com/SYSTRAN/faster-whisper/tree/6cb639e70786aea42b9233006ae60eaf07190bdb); installed [v1.2.1](https://github.com/SYSTRAN/faster-whisper/releases/tag/v1.2.1), released 31 October 2025 | [MIT code](https://github.com/SYSTRAN/faster-whisper/blob/6cb639e70786aea42b9233006ae60eaf07190bdb/LICENSE). Latest inspected commit dated 12 November 2026 fixes batched operation without VAD. Cached [small model](https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120) card declares MIT. | **Retain.** Existing integration, cached multilingual weights and supplied-text matching avoid another runtime. Use Chinese recognition; preserve timestamps from sample zero. Singing still needs entrance review. |
| [Qwen3-ASR `7c6daf77`](https://github.com/QwenLM/Qwen3-ASR/tree/7c6daf77a2421100f5fb066495372c00129d39ff), package 0.0.6 | [Apache-2.0 code](https://github.com/QwenLM/Qwen3-ASR/blob/7c6daf77a2421100f5fb066495372c00129d39ff/LICENSE) and [ForcedAligner-0.6B weights](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B/tree/c7cbfc2048c462b0d63a45797104fc9db3ad62b7). Latest inspected commit, 26 June 2026, announces native Transformers support; repository not archived. | **Defer installation; prioritize an isolated accuracy trial if current anchors fail.** Chinese forced alignment accepts supplied text. Its card lists alignment for speech; the separate ASR model lists singing. Do not infer proven sung-lyric accuracy. Package pins Transformers 4.57.6 and Accelerate 1.12.0 and adds several text/audio/UI packages. Raw 0.6B BF16 parameters alone imply about 1.2 GB, before runtime overhead. |
| [WhisperX `b904f02b`](https://github.com/m-bain/whisperX/tree/b904f02b7e1f26fd10fb04840d655ff27e88e464), [v3.8.6](https://github.com/m-bain/whisperX/releases/tag/v3.8.6), 25 May 2026 | [BSD-2-Clause code](https://github.com/m-bain/whisperX/blob/b904f02b7e1f26fd10fb04840d655ff27e88e464/LICENSE); additional alignment models retain separate terms. Latest inspected commit, 12 November 2026, adds accelerator detection. | **Defer.** A second alignment network and broader PyTorch/audio stack need a measured improvement on this song. Speaker diarization offers no immediate benefit. |
| [stable-ts `e312072c`](https://github.com/jianfch/stable-ts/tree/e312072cc024ae9fceb25b057d7d18524873a02b) | [MIT](https://github.com/jianfch/stable-ts/blob/e312072cc024ae9fceb25b057d7d18524873a02b/LICENSE). Repository archived; final inspected commit, 30 May 2026, explicitly marks development indefinitely paused. | **Defer dependency.** Confining realignment to reviewed phrase windows is useful, but its maintenance state does not justify replacing the current backend. No upstream code copied. |
| [Demucs `829d2189`](https://github.com/adefossez/demucs/tree/829d21890023800713e5dd231c67e43ecc06069b), 26 October 2026 | [Code MIT](https://github.com/adefossez/demucs/blob/829d21890023800713e5dd231c67e43ecc06069b/LICENSE). Maintainer says feature work is inactive. The current [weight-license section](https://github.com/adefossez/demucs/blob/829d21890023800713e5dd231c67e43ecc06069b/README.md#license) says weight rights are unclear and flags the six-source model's likely noncommercial terms. | **Defer new inference for this film.** Package availability and code MIT do not resolve weight licensing. Vocal isolation remains a possible future experiment using separately reviewed weights; do not silently assume this installed model is suitable for branded commercial delivery. |
| [Beat This! `b95c8ab0`](https://github.com/CPJKU/beat_this/tree/b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c), [v1.1.0](https://github.com/CPJKU/beat_this/releases/tag/v1.1.0), 14 April 2026 | [MIT code](https://github.com/CPJKU/beat_this/blob/b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c/LICENSE); [README](https://github.com/CPJKU/beat_this/blob/b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c/README.md#license) explicitly extends MIT to published weights and notes training-data limitations. Latest inspected commit, 28 May 2026, clarifies checkpoint licensing. | **Retain as an optional existing adapter; defer installation for this delivery.** Main checkpoints are about 78 MB and need PyTorch plus audio/rotary packages. Beat positions are useful cut candidates, not lyric alignment. Avoid replacing an already established canonical analysis mid-edit. |
| [HyperFrames v0.9.65](https://github.com/heygen-com/hyperframes/releases/tag/v0.9.65), `32ff8b33`, published 18 November 2026 UTC | [Apache-2.0](https://github.com/heygen-com/hyperframes/blob/v0.9.65/LICENSE). Current release includes Windows process cleanup and preview/keyframe fixes; repository actively receiving commits on review day. | **Retain existing composition route.** Reuse deterministic scene motion and registry treatments where they fit. CLI freshness alone is not proof of better editing or faster rendering. |

## Applied improvement

The parser previously ignored English `[Post-Chorus]`, `[Bridge]` and `[Final Chorus]`
headers and consequently inherited the preceding section. It now recognizes these
musical sections, including the space-separated Post Chorus spelling. Unknown bracketed
stage directions remain omitted; vocal annotations still change only the singer.
This makes the supplied section plan available to later editing without treating
arbitrary production directions as sung text or new sections.

The song also exposed split Latin ASR names: matching only `oston` can discard the
earlier `B` onset. A small original preprocessing helper now joins contiguous fragments
only when their concatenation exactly matches a supplied Latin lyric lexeme. The spans
must not overlap and their intervening gaps cannot exceed 150 ms. The merged token keeps
the first fragment's start, last fragment's end and lowest confidence. A fragment that
is itself a complete supplied word is protected, so `a way` remains two words when
`away` also occurs in the song. Unrelated names, CJK interruptions, longer pauses and
sentence boundaries are not crossed. Reports disclose any joins; this changes token
grouping without claiming newly measured internal syllable boundaries.

Targeted validation: **28 tests passed** across lyric parsing, alignment, cue export and
lyric-film rendering contracts; Ruff passed for the changed Python files. Tests exercise
the supplied section sequence, mixed Latin/CJK lyrics, preserved vocal/direction handling,
first-syllable onset retention, conservative confidence, unchanged ordinary English words,
exact lexeme matching, punctuation, long gaps and overlapping spans. These checks do not
measure the actual song's sync or subjective visual quality.

## Production follow-up: optional Chinese normalization

The project timing pass installed **opencc-python-reimplemented 0.1.7** locally;
it is not a new base `pyproject.toml` dependency. The installed distribution's
`LICENSE.txt` explicitly contains **Apache License 2.0** (SHA-256
`18f3fedf9eac72e6054260489c764c1e54f63cf2b16055523f561ffeec7bc908`). This agrees
with the [official pinned license](https://github.com/yichen0831/opencc-python/blob/b85452e384a3650109809fe5fefacb2ae4fe89d2/LICENSE.txt).
Its installed `opencc/NOTICE.txt` credits OpenCC dictionary data and configurations,
matching the [upstream notice](https://github.com/yichen0831/opencc-python/blob/b85452e384a3650109809fe5fefacb2ae4fe89d2/opencc/NOTICE.txt).
Preserve those notices if redistributing the package or its data.

The [0.1.7 PyPI release](https://pypi.org/project/opencc-python-reimplemented/0.1.7/)
dates to 11 February 2023. The official repository's latest inspected commit,
[`b85452e3`](https://github.com/yichen0831/opencc-python/commit/b85452e384a3650109809fe5fefacb2ae4fe89d2),
is the same day's version bump; the repository is not archived, but recent active
maintenance is not established. It is pure Python with no declared runtime dependencies.
**Adopt only for this optional preparation pass:** convert Traditional recognition
tokens to Simplified for comparison, while keeping displayed text locked to the
supplied lyrics. Conversion does not establish vocal timing or correct an ASR omission.

## Production follow-up: Chrome 157 capture compatibility

The production run exposed a specific compatibility issue in the pinned HyperFrames
0.8.152 fast capture path. Local Chrome's executable reports **157.0.8103.51**.
The [0.8.152 capture implementation](https://github.com/heygen-com/hyperframes/blob/v0.8.152/packages/engine/src/services/drawElementService.ts)
sets the older `layoutsubtree` attribute. Chrome's [API change announcement](https://github.com/WICG/html-in-canvas/issues/179)
documents its replacement with `content="drawable"`; drawn children also need a
`drawable` marker. That matches the attribute error observed in this production.

Upstream explicitly corrected this in
[`9c3258cc`](https://github.com/heygen-com/hyperframes/commit/9c3258ccbf8f88e0f6656cd358e95f926a09160c),
12 November 2026. The inspected **0.9.65**
[implementation](https://github.com/heygen-com/hyperframes/blob/v0.9.65/packages/engine/src/services/drawElementService.ts)
detects the browser's API form and applies both required markers. Its
[browser regression test](https://github.com/heygen-com/hyperframes/blob/v0.9.65/packages/engine/src/services/drawElementCanvasForm.browser.test.ts)
reproduces the same missing-marker error and checks the injected canvas. This is
verified source evidence for a relevant fix, not a locally tested speed or parity result.

The pinned [0.9.65 CLI reference](https://github.com/heygen-com/hyperframes/blob/v0.9.65/docs/packages/cli.mdx)
supports 1–24 workers but treats the requested count as a ceiling: an eligible
drawElement render still uses one worker. Low-memory mode selects one screenshot
worker and disables calibration. `--browser-gpu` controls browser rendering;
`--gpu` controls FFmpeg hardware encoding. Increasing encoding speed does not remove
the browser's composition work. Automatic fallback and advertised capture speedups
are upstream behavior claims, not performance measured on this film.

**Defer the renderer upgrade until after this delivery.** Keep the current successful
0.8.152 screenshot run (`--experimental-fast-capture=false`, one worker). For the next
film, benchmark an isolated copy of a short representative composition: current
screenshot baseline, 0.9.65 screenshots with one/two/four workers, then 0.9.65 hardware
fast capture with one worker. Record wall time, peak memory, actual selected capture
route, fallbacks and frame-by-frame visual differences before changing the project pin.
After the main film's complete capture finished, an authorized isolated two-second
trial exercised the exact same Canvas code, plates, logo, font and opening lyric
from original timeline 2–4 seconds. Neither the production renderer pin nor the
production composition was changed. Both exact npm versions were warmed using
`--version` before timing and then run sequentially with one browser worker.

| Variant | Runtime-confirmed route | CLI wall time | Capture stage | Decoded output |
| --- | --- | --- | --- | --- |
| HyperFrames 0.8.152, fast capture off | screenshot, hardware GPU | 14.875 s | 8.511 s | 60 frames, 1080p30, 2.000 s |
| HyperFrames 0.9.65, fast capture on | drawElement, hardware GPU | 18.002 s | 11.433 s | 60 frames, 1080p30, 2.000 s |

The new path therefore **worked on Chrome 157**, without the old drawable-marker
exception. It did not improve speed in this short run. Main-film verification and
a CPU sharing encode overlapped the trial; CPU contention was not controlled or
measured. CLI wall includes startup, and one two-second run cannot establish sustained
capture performance. Both exports passed full decode and meaningful-image checks.
The agent inspected paired frames 0, 30 and 59: camera placement, branding, Chinese
title, first lyric and picture detail matched at those samples. PSNR was 39.33–40.23 dB
and mean absolute RGB difference 1.69–1.91/255 between lossy exports; neither these
metrics nor three stills establish full-frame equivalence. Keep the delivery pin.

Reproduce preparation with
`python videos/bosston-pragon-good-fortune/benchmark_capture.py --warm-packages`;
only `--run` starts the sequential browser trials. The staged fixture and
[`latest-results.json`](../../output/bosston-capture-benchmark/latest-results.json)
live under ignored local output. The frozen trial's logs, paired stills, source
hashes and summary are in
[`runs/20261118T055807-513566Z`](../../output/bosston-capture-benchmark/runs/20261118T055807-513566Z/SUMMARY.md).
All four checked production HTML/JS source hashes remained unchanged. No global
package was installed.

## Delivery checks and next useful experiment

### Evidence from this recording

The first supplied lyric text did not describe this WAV. The user then supplied the
matching New Year lyrics, and all 71 revised display lines were retained. Traditional
ASR tokens were converted to Simplified Chinese with local OpenCC 0.1.7 for matching;
the displayed text was never replaced by the recognizer's spelling.

An additional MIT-licensed Faster Whisper medium model was downloaded for the film,
revision `08e178d48790749d25932bbc082711ddcfdfbc4f`, model SHA-256
`9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae`.
Both unconstrained recognition passes struggled with the layered opening. The existing
CTranslate2/Whisper `find_alignment` path then aligned the exact user-confirmed text
using acoustic cross-attention in three focused windows, correcting the closing
phrase splits without adding another alignment runtime. Final anchor coverage is
79.86%; remaining token timings are explicitly estimated. These are model-derived
boundaries, not independently human-auditioned timing measurements. The frozen
project evidence records the inputs, outputs and remaining few-tenths uncertainty.

The canonical music analyzer's native Windows Numba beat operation crashed. The
project adapter calls that same analyzer's energy, spectral and onset operations,
records BPM and beat grid as unavailable, and uses vocal phrases for editing.
It does not substitute an undocumented beat detector. The tested HyperFrames version
also needed experimental `drawElementImage` capture disabled for the installed Chrome;
the project's render wrapper explicitly selects the working screenshot path.

Keep the master recording unchanged, cache raw ASR observations and export exact supplied
text. Inspect first entrances, repeated hooks, countdowns and the final chorus against the
audio. Flag weak lines individually even when global anchor coverage clears the export
gate. Use a single canonical music map for cuts and energy accents. A later aligner trial
should compare manually marked entrances and exits from at least 12 phrases, including
repeated hooks and long held vowels, reporting median and worst timing error, runtime,
GPU memory and download size before adopting another model.

Picture QA should inspect readable Chinese glyphs and title-safe text, source-brand
fidelity, section transitions and the final fade. Verify the actual encoded MP4 through
full decoding and zero-offset source-audio comparison. [FFmpeg's ASS filter](https://ffmpeg.org/ffmpeg-filters.html#ass)
uses the installed libass renderer; the local GPL-enabled FFmpeg build is invoked as a
tool and no binary is included in this change. No new dependency, model or upstream
source code was installed or vendored by this research pass.
