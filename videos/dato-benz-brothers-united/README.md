# 有你，兄弟同心

**Current status: realism research complete; new generation held.** The user reports that the boss rejected V2's face/body appearance as unnatural. V2's encoding, audio and subtitle checks passed, but that did not establish acceptable likeness or natural movement. It is retained as a technical archive, not an accepted creative result.

Read [REALISM-RESEARCH.md](REALISM-RESEARCH.md) for the failure audit, current model/reference-control comparison and recommended route. [REALISM-PILOT.md](REALISM-PILOT.md) defines an originals-only reference set and a small normal-speed comparison before any new full-song batch. Real Hock Siew footage is the preferred natural-person backbone when available. Kling O3Pro and Seedance2 are proposed test candidates; neither has passed a test on the new references. Research spent zero credits.

Three new frontal full-body photographs have been catalogued in [reference-intake-v3.json](reference-intake-v3.json). The user explicitly identified Hock Siew as the left-hand man. They strengthen body/outfit evidence but are near-duplicates, not multiple angles or motion evidence. Private images remain local and have not been uploaded for generation. [CLIENT-STATUS.json](CLIENT-STATUS.json) is the current acceptance/stage record. Benz's later song is a separate project.

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

Native 24fps avoids V1's avoidable 24→30 conversion cadence. In a tested unretimed three-second excerpt, near-duplicate adjacent pairs fell from 18 to zero. This is a scoped cadence measurement, not a claim about every scene. Native footage is 720p, upscaled to 1080p; tight contextual crops are softer. No native 4K or recovered ground-truth detail is claimed.

V1 used 1,924 credits; V2 added six 10-second Turbo takes for 300. **Total: 2,224 of the authorized 2,250 existing Runway credits used; 26 remain**, verified against the workspace. No extra credits were purchased. Reused existing footage required no generation spend.

## V1 archive

The earlier ensemble edit remains intact under `renders/Hock-Siew-Brothers-United-Cinematic[ -720p].mp4`, with its original `prepare_film.py`, `edit-plan.json`, [DELIVERY.json](DELIVERY.json), [REVIEW.md](REVIEW.md) and [DIRECTION.md](DIRECTION.md). It is retained for comparison; V2 is the current delivery. The directory name retains the project's earlier working title.
