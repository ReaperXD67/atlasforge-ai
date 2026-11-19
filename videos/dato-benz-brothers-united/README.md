# 有你，兄弟同心

**Current status: both short realism tests are ready for user review; no candidate is accepted.** Following the user-completed Max upgrade, one Kling O3 Pro test and one Seedance 2.5 test completed. Both raw outputs are 1920×1080 at 24fps, 5.041667 seconds (121 frames), without audio, and passed full decoding. These technical checks do not establish natural likeness. Further generation and the full MV remain held until the user reviews both complete clips. V2 remains a rejected technical archive.

Read [REALISM-RESEARCH.md](REALISM-RESEARCH.md) for the failure audit and [REALISM-PILOT.md](REALISM-PILOT.md) for the test protocol. The current pair uses the original `17-27-29` photograph (Hock Siew is the left-hand man) for face, torso and actual white-shirt proportions, plus the original seaside photograph as alternate facial evidence only. No generated portrait is an identity anchor. Seedance 2.5 replaces the earlier proposed Seedance 2.0 at the user's request. The complete raw clips must be reviewed at normal speed before further tests or a full-song batch. Real footage remains the preferred natural-person material when available. Research itself spent zero credits.

Three new frontal full-body photographs are catalogued in [reference-intake-v3.json](reference-intake-v3.json). They strengthen body/outfit evidence but are near-duplicates, not multiple angles or motion evidence. The selected original references were uploaded to Runway for this authorized pair; private media and signed URLs are excluded from Git. [pilot-v3.json](pilot-v3.json) records the jobs, inputs and realized charges; [CLIENT-STATUS.json](CLIENT-STATUS.json) records current acceptance. Benz's later song is separate.

## Review the short pair

- Untouched Kling output: `assets/pilot-v3/kling-o3-pro-portrait-01.mp4`.
- Untouched Seedance 2.5 output: `assets/pilot-v3/seedance-2.5-portrait-01.mp4`.
- [PILOT-REVIEW.md](PILOT-REVIEW.md): scoped sampled observations and the pending user verdict.
- [PILOT-TECHNICAL.json](PILOT-TECHNICAL.json): output hashes, dimensions, cadence, duration, audio absence and decode results.

Watch each complete silent clip at normal speed. Neither has music, grading, retiming, face restoration or a selective edit to hide defects. Portrait framing does not validate full-body proportions, hands, feet or gait. Chronological still samples cannot establish natural movement or personal recognition.

Recheck the existing local files from the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe videos/dato-benz-brothers-united/inspect_pilot.py
```

## Archived V2

V2 placed a generated Hock Siew interpretation in its first frame and throughout every named lyric. Six reference-derived solo takes used burgundy clothing, and the earlier group-photo animation was cropped around the confirmed subject. Other performers appeared in face-free contextual details. The original seaside photograph closed the film. The client's rejection supersedes the earlier internal sampled likeness judgements.

The 196.760-second song and all forty supplied lyric lines are unchanged. The 44-shot edit marked approximately125.4seconds as protagonist coverage, with179.1seconds of native moving footage and17.7seconds of original photographs. That coverage measure is not an identity-accuracy or realism score. Twelve intentional, non-adjacent portrait returns are recorded in the edit; contextual footage is not replayed.

## Watch and inspect

- Local master: `renders/v2/Hock-Siew-Personal-Tribute-V2.mp4` — 1920×1080, native 24fps, H.264/AAC; 346.64MB.
- Local viewing copy: `renders/v2/Hock-Siew-Personal-Tribute-V2-720p.mp4` — 103.00MB.
- [DELIVERY-V2.json](DELIVERY-V2.json) and [REVIEW-V2.md](REVIEW-V2.md): measured export, full-song audio and encoded-frame findings.
- [edit-plan-v2.json](edit-plan-v2.json): exact 4,723-frame edit, source intervals, crops and explicit portrait reprises.
- [V2-DIRECTION.md](V2-DIRECTION.md), [V2-QUALITY.md](V2-QUALITY.md): subject-led direction, cadence tests, finishing decisions and primary-source research.
- [native-clips-v2.json](native-clips-v2.json), [generation-jobs-v2.json](generation-jobs-v2.json), [NATIVE-REVIEW-V2.json](NATIVE-REVIEW-V2.json): source hashes, credits, motion and likeness admission.
- [v2-context-selections.json](v2-context-selections.json), [context-review-v2.json](context-review-v2.json): face-free source crops reviewed across 88 chronological output-aspect samples.
- [lyrics.txt](lyrics.txt), [captions.json](captions.json), [SRT](captions.srt), [LRC](captions.lrc): canonical words and frozen phrase timing.

## Rebuild locally

Run from the repository root in PowerShell. The tested environment needs NVIDIA NVENC, ImageIO's FFmpeg 7.1 binary, and `ffmpeg` / `ffprobe` on PATH. System FFmpeg 9's encoder is incompatible with this machine's driver; the renderer selects the tested 7.1 binary.

```powershell
.venv\Scripts\python.exe -m pip install -r videos/dato-benz-brothers-united/requirements-render.txt
.venv\Scripts\python.exe videos/dato-benz-brothers-united/prepare_film_v2.py --render --share
.venv\Scripts\python.exe videos/dato-benz-brothers-united/verify_film_v2.py videos/dato-benz-brothers-united/renders/v2/Hock-Siew-Personal-Tribute-V2.mp4 --contact-sheets
```

Edit `edit-plan-v2.json` for revisions. `author_edit_v2.py --write` restores the authored schedule and overwrites that file. The validator requires complete song coverage, a recognizable opening and every full named lyric on Hock Siew. Replayed protagonist intervals need explicit editorial reasons. The renderer uses lossless FFV1 segment staging, a neutral grade, restrained luma detail treatment and one final H.264 picture encode; it validates replacements before replacing exports.

Private files remain local under `assets/`: the original `bgm.wav`, both confirmed photographs, native source clips and plates listed in the manifests, and `fonts/NotoSerifCJKsc-Regular.otf`. See [MEDIA.md](MEDIA.md) for provenance and the [font notice](licenses/NotoSerifCJK-OFL.txt). The tracked source contains no private media or signed provider URLs. Project `.gitattributes` preserves exact source bytes across Git checkouts.

## Timing, quality and budget

The first vocal starts at 22.30s and the final phrase ends at 170.10s. Phrase timing combines supplied-text acoustic alignment with independently cropped recognition. Hock Siew chants use phrase sync; uncertain character subdivisions are labelled estimated in [line-alignment.json](line-alignment.json). No word-perfect karaoke or human listening review is claimed.

Native 24fps avoids V1's avoidable 24→30 conversion cadence. In a tested unretimed three-second excerpt, near-duplicate adjacent pairs fell from 18 to zero. This is a scoped cadence measurement, not a claim about every scene. Archived V2 native footage is 720p, upscaled to 1080p; tight contextual crops are softer. The new raw pilot pair is 1920×1080 as returned by the providers. Neither workflow establishes native 4K or recovered ground-truth detail.

The archived V1/V2 work used 2,224 credits (1,924 + 300), leaving 26 before the user upgraded to Max. The verified post-upgrade balance was **7,276**. The current two-test pair charged **425 credits**: Kling O3 Pro 85 and Seedance 2.5 340, taking the observed balance through 7,191 to **6,851**. No Max discount was observed on these submissions. Both jobs completed and the final balance was verified at 6,851. These charges do not imply accepted footage or permission to spend the remaining balance.

## V1 archive

The earlier ensemble edit remains intact under `renders/Hock-Siew-Brothers-United-Cinematic[ -720p].mp4`, with its original `prepare_film.py`, `edit-plan.json`, [DELIVERY.json](DELIVERY.json), [REVIEW.md](REVIEW.md) and [DIRECTION.md](DIRECTION.md). It is retained for comparison alongside the rejected V2; the short realism pair is ready for user review. The directory name retains the project's earlier working title.
