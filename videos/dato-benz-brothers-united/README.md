# 有你，兄弟同心

**Current status: V3 source generation and edit preflight are complete; the local full-song render is in progress.** The user preferred Seedance 2.5 and authorized the new cinematic MV with natural backgrounds. Seventeen generation attempts produced fourteen admitted new takes plus two reused environmental sources. Final encoding, original-audio verification and review of the encoded frames are still pending. No V3 delivery or user/boss creative acceptance is claimed. V2 remains a rejected technical archive.

[V3-DIRECTION.md](V3-DIRECTION.md) describes the authored direction and actual allocation. The [generation ledger](generation-jobs-v3.json), [admitted sources](native-clips-v3.json), [source review](SOURCE-REVIEW-V3.json) and [45-shot edit plan](edit-plan-v3.json) record what was generated, excluded, cropped and selected. The original 196.760-second song and all forty frozen lyric cues are unchanged. No generated portrait became an identity anchor.

[REALISM-RESEARCH.md](REALISM-RESEARCH.md) retains the failure audit and [REALISM-PILOT.md](REALISM-PILOT.md) the earlier test protocol. The pilot pair used the original `17-27-29` photograph (Hock Siew is the left-hand man) and original seaside photograph. Both completed at 1920×1080/24fps and passed decoding, which does not prove personal likeness. Research itself spent zero credits.

Three new frontal full-body photographs are catalogued in [reference-intake-v3.json](reference-intake-v3.json). They strengthen body/outfit evidence but are near-duplicates, not multiple angles or motion evidence. Selected original references were uploaded to Runway for the pilot and may be reused for the authorized V3 production; private media and signed URLs are excluded from Git. [pilot-v3.json](pilot-v3.json) records the short-test jobs, inputs and realized charges; [CLIENT-STATUS.json](CLIENT-STATUS.json) records current production and acceptance. Benz's later song is separate.

## Review the short pair

- Untouched Kling output: `assets/pilot-v3/kling-o3-pro-portrait-01.mp4`.
- Untouched Seedance 2.5 output: `assets/pilot-v3/seedance-2.5-portrait-01.mp4`.
- [PILOT-REVIEW.md](PILOT-REVIEW.md): scoped sampled observations; the later user preference is Seedance 2.5.
- [PILOT-TECHNICAL.json](PILOT-TECHNICAL.json): output hashes, dimensions, cadence, duration, audio absence and decode results.

The user preferred Seedance 2.5 after viewing these raw clips. Neither has music, grading, retiming, face restoration or a selective edit to hide defects. Portrait framing does not validate full-body proportions, hands, feet or gait. Chronological still samples cannot establish natural movement or personal recognition, and the model choice does not accept every later V3 take.

Recheck the existing local files from the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe videos/dato-benz-brothers-united/inspect_pilot.py
```

## V3 production

Fourteen new takes are admitted for the edit: eight Seedance 2.5 protagonist sources with 75 seconds of requested generation (seven ten-second takes and a five-second room repair), and six ten-second Gen-4.5 face-free contexts. Only the legacy full-frame `sea-dawn` and `wet-footsteps` clips are reused. The initial room-medium, tea-pour and table takes were excluded for clipped headroom, near-overflowing tea and excessive steam respectively. Their replacements and costs remain in the ledger. Old generated protagonist scenes are excluded.

All seventeen attempts passed full decoding and were examined through ten chronological samples each, with additional crop/transition proofs. This is sampled editorial source admission, not full-speed naturalness review, exact-person recognition or user approval. The five-second medium-room repair supplies only its admitted 0.2–4.8 second interval.

Mandatory crops remove unwanted or malformed details from boat-wide (1280×720), window (1600×900), waterfront (1280×720), doorway (704×396) and tea-context (720×405) shots. The source pixel areas and crop positions are enforced in the manifest/EDL; a 1920×1080 output does not make all those crops native 1080p detail. The doorway crop excludes an added badge/watch; the tea crop excludes a malformed teapot/stray object. New Gen-4.5 contexts are native 1280×720, whereas the Seedance files are 1920×1080 before cropping.

The preflighted 45-shot plan contains 184.75 seconds of native movement and 12.042 seconds of original photographs. Of the native footage, 146.633 seconds are distinct source intervals and 38.117 seconds are declared non-adjacent protagonist reprises across fourteen motifs. Contextual intervals are not replayed. The film opens on the moving seaside portrait; only the final dedication uses the authentic photograph. Matched identity slots are not a claim of genuine captured motion.

The V3 renderer is [prepare_film_v3.py](prepare_film_v3.py), with [verify_film_v3.py](verify_film_v3.py) for full-song format/audio/caption and sampled encoded-picture checks. It retains 24fps, lossless FFV1 segment staging and one final H.264 encode. Natural colour/texture are preserved without default sharpening, grain, beauty restoration or interpolated motion. Letterbox defaults to zero to protect headroom. The admitted manifest and complete edit passed preflight, including negative checks for missing mandatory crops and protagonist retiming. Rebuild from the repository root:

```powershell
.venv\Scripts\python.exe videos/dato-benz-brothers-united/prepare_film_v3.py --render --share
.venv\Scripts\python.exe videos/dato-benz-brothers-united/verify_film_v3.py videos/dato-benz-brothers-united/renders/v3/Hock-Siew-Personal-Tribute-V3.mp4 --contact-sheets
```

The local full-song render has started; final export, audio verification and encoded-frame review remain pending. The expected master path is `renders/v3/Hock-Siew-Personal-Tribute-V3.mp4`, with a smaller `-720p.mp4` copy. Technical checks remain separate from user/boss creative acceptance.

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

The archived V1/V2 work used 2,224 credits; the raw pilot used 425 after the Max upgrade, leaving 6,851 verified before V3. V3's fourteen base submissions used 6,160credits, and three repairs added 580: **6,740used across seventeen attempts;111remaining verified**. The repair spend comprises a five-second Seedance room replacement (340) and two ten-second Gen-4.5 context replacements (240). Excluded attempts remain charged and recorded in the [V3 ledger](generation-jobs-v3.json). No additional credits were purchased. Source generation is complete; the remaining balance does not represent an automatic retake batch.

## V1 archive

The earlier ensemble edit remains intact under `renders/Hock-Siew-Brothers-United-Cinematic[ -720p].mp4`, with its original `prepare_film.py`, `edit-plan.json`, [DELIVERY.json](DELIVERY.json), [REVIEW.md](REVIEW.md) and [DIRECTION.md](DIRECTION.md). It is retained for comparison alongside the rejected V2; V3 is the active production after the user selected the Seedance test. The directory name retains the project's earlier working title.
