# 有你，兄弟同心

**Current version: V2, completed and verified, a personal tribute to 拿督斯里谢惠福 / Hock Siew.** The user confirmed him in the seaside photograph and the central light-blue-shirt figure in the group photograph. Benz's later song is a separate project.

V2 introduces Hock Siew in its first frame and shows him throughout every named lyric. Six reference-led solo moving takes retain his likeness and familiar burgundy clothing. The existing group-photo animation is reused as a crop showing only Hock Siew. Other performers appear only in reviewed, face-free details of hands, work, rain and water. The original seaside photograph closes the film with Mandarin wishes.

The 196.760-second song and all forty supplied lyric lines are unchanged. The 44-shot edit has approximately 125.4 seconds of recognizable Hock Siew, 179.1 seconds of native moving footage and 17.7 seconds of original photographs. Twelve intentional, non-adjacent returns to his portrait are recorded as musical motifs. Context footage is not replayed. Generated scenes are artistic interpretations, rather than documentary events.

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
