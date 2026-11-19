# 有你，兄弟同心

**Completed and verified.** The user confirmed that this song is for Hock Siew / 拿督斯里谢惠福 and identified him in the seaside photograph. A later song will be a separate Benz tribute; that second film has not been started.

A personal Mandarin tribute to **拿督斯里谢惠福 / Hock Siew**. The complete 196.760-second recording drives a 40-shot edit of actual generated moving footage: shared work, helping hands, companionship in the rain and a hopeful coastal dawn. A short animation of the supplied group photograph leads to the original seaside photograph and a Mandarin dedication.

The corrected forty sung lines in [lyrics.txt](lyrics.txt) are authoritative. Generated actors interpret the song symbolically; the supplied photographs provide the personal connection. The internal directory retains an earlier working name.

## Film and sources

Local exports are `renders/Hock-Siew-Brothers-United-Cinematic.mp4` and `renders/Hock-Siew-Brothers-United-Cinematic-720p.mp4`. Both passed complete decoding. The master is 1920×1080, 30fps, H.264 with the original stereo song encoded as 320kbps AAC: 5,903 frames / 196.766667 seconds, within one frame of the full recording. File sizes are 347.33MB and 102.79MB. Measured results are in [DELIVERY.json](DELIVERY.json). The 1280×720 native Runway sources are upscaled during editing; this is not native 4K footage.

- [edit-plan.json](edit-plan.json): exact frame cuts, source intervals and mild slow-motion rates. Returning shots consume different source time.
- [captions.json](captions.json), [SRT](captions.srt), [LRC](captions.lrc): forty phrase-timed lyric cues; names and places preserve the supplied spelling.
- [native-clips.json](native-clips.json), [generation-jobs.json](generation-jobs.json): admitted source ranges, hashes, prompts, task IDs and credit ledger.
- [NATIVE-REVIEW.json](NATIVE-REVIEW.json), [REVIEW.md](REVIEW.md): motion/anatomy checks and final encoded-frame review.
- [DIRECTION.md](DIRECTION.md), [MEDIA.md](MEDIA.md), [research](../../docs/research/hock-siew-native-tribute-2026-11-19.md): creative intent, provenance and implementation decisions.

## Rebuild locally

Run from the repository root in PowerShell. This renderer uses an NVIDIA GPU with working NVENC, the ImageIO FFmpeg 7.1 binary, and `ffprobe` / `ffmpeg` on PATH for inspection. The current installed system FFmpeg 9 encoder is incompatible with this machine's driver; rendering deliberately selects the tested bundled 7.1 binary.

```powershell
.venv\Scripts\python.exe -m pip install -r videos/dato-benz-brothers-united/requirements-render.txt
.venv\Scripts\python.exe videos/dato-benz-brothers-united/prepare_film.py --render --share
.venv\Scripts\python.exe videos/dato-benz-brothers-united/verify_film.py videos/dato-benz-brothers-united/renders/Hock-Siew-Brothers-United-Cinematic.mp4 --contact-sheets
```

Private inputs stay local under `assets/`: `bgm.wav`, original `photos/brothers.jpg` and `photos/seaside.jpg`, the native files listed in the manifest, and `fonts/NotoSerifCJKsc-Regular.otf`. [MEDIA.md](MEDIA.md) records their provenance. The font is SIL OFL 1.1; its notice is retained in [licenses](licenses/NotoSerifCJK-OFL.txt). Source hashes reject changed inputs. Exact cached segments are reused, and replacement exports are validated before replacing previous files.

Edit `edit-plan.json` to revise the film. `author_edit.py --write` explicitly restores the authored schedule and overwrites that file. The source validator rejects gaps, overlaps, repeated native source intervals, out-of-range trims and a changed song/caption clock. `prepare_film.py` also writes the ASS typography and source bindings. Project `.gitattributes` preserves exact file bytes across checkouts so Git line-ending conversion cannot invalidate frozen source hashes.

## Timing and budget

The first vocal begins at 22.30s; the last phrase ends at 170.10s. The final original-photo dedication begins at 184.7667s. Alignment combines local Whisper recognition, supplied-text cross-attention timing and independent cropped recognition. Hock Siew chants use phrase timing; uncertain character subdivisions are labelled estimated in [line-alignment.json](line-alignment.json). No word-perfect karaoke or human audio audition is claimed. The alignment scripts retain acoustic candidate-generation steps; `compile_captions.py` encodes the reviewed boundary decisions using local acoustic evidence. The delivered captions are frozen for rendering.

Runway generated twelve 10-second Gen-4.5 takes, eight 10-second Turbo takes and one 7-second photo animation. **1,924 existing credits were used; 326 remain**, verified against the connected workspace. No additional credits were purchased. Full-stream decoding and chronological sampled visual review admitted each take; weaker source ranges were excluded. Quality review is sampled and does not establish every-frame anatomical perfection.
