# Remotion Music Film workflow

AtlasForge has a separate music-first path for event films. It does not force a song through the
long-form explainer timeline. The Pragon profile is locked to licensed existing footage for every
human, performance, friendship, smoke, and driving scene.

## Pragon footage contract

The production does not generate characters or pretend that unrelated actors form a recurring AI
cast. It builds continuity through story order and identity-safe framing: establishing wides,
silhouettes, hands, instrument details, over-shoulders, cars, table details, embers, and smoke.

- The lyric section and singer annotation select a real-footage role: friend gathering, female-led
  dance/lifestyle, male guitar performance, ciggies break, cruise, preparation, or departure.
- Drift is deliberately scarce and appears only on a measured peak or guitar-solo phrase.
- Pexels and Pixabay results are locally reranked for the authored shot role, motion-fit to the
  musical energy, and rejected if a chosen source window crosses an internal scene cut.
- The Pragon profile fails the render when any non-outro scene lacks a licensed video clip. It never
  silently fills a missing person with an image generator or a synthetic video model.
- The one exception is `assets/pragon/outro/pragon-ember-ai-v1.png`: an owned synthetic macro ember
  keyframe used only for the final resolve. It contains no lettering. Exact `PRAGON` typography is
  rendered in post at the approved vocal/closing cue.

For Pragon or any tobacco product, obtain Malaysian legal clearance before public release. Malaysia's
Act 852 restrictions include tobacco-product advertising, promotion, and sponsorship; the pipeline
does not make a campaign lawful merely because the characters and footage are synthetic. See the
[Malaysia Ministry of Health 2024 annual report](https://www.moh.gov.my/images/04-penerbitan/laporan-tahunan/MOH_Annual_Report2024.pdf).

## Make the Pragon Sepang-after-dark film

1. Start Studio with `./scripts/start_studio.ps1` and open `http://127.0.0.1:8741/`.
2. Select **Remotion Lab** in the top bar.
3. Click **Upload your final song** and choose MP3, WAV, M4A, AAC, FLAC, or OGG. The file is
   written only to `output/.studio/uploads/`.
4. Wait for the local analyzer to show BPM, grid confidence, real/estimated downbeats, musical
   sections, rolls, hard stops, surges, and energy. A low-confidence track automatically switches
   from beat cuts to phrase pacing instead of pretending a metronome is the song.
5. Set the **Brand wordmark** separately from the event title, then write a **Custom clip prompt** that describes the subjects, locations,
   wardrobe, atmosphere, and camera language. For example: clearly adult smokers in a neon pit
   garage, cigarette embers and tire haze, wet asphalt, aggressive circuit speed, handheld flash
   photography, and no visible brands.
6. Choose a motion treatment: **Pragon neon**, **Smoke + velocity**, **Neon strobe**, **Luxury noir**,
   or **Flash editorial**. Pragon neon uses the commissioned cyan/ember palette and condensed Barlow
   typography. Add comma-separated **Beat text** phrases such as `PRAGON, REDLINE, BURN BRIGHT`.
   Short phrases work better than sentences. Choose a 30, 60, 90, or 180-second cut; use 60 seconds
   for the first boss review.
7. Leave **Licensed clips required** on. AtlasForge searches Pexels and then Pixabay when their API
   keys are configured. AI filler is blocked for the Pragon profile; the final owned ember plate is
   already part of the project and is the only synthetic shot.
8. Play the Remotion preview. Its palette and kinetic phrases follow the chosen treatment, while
   flashes and text entries use selected downbeats from the canonical music map. It is still a
   graphics proof rather than fake footage, but those same cue times are now rendered into the MP4.
9. Click **Build exceptional music film**. The job downloads directed real footage, rejects weak
   visual matches locally, varies shot length with the song structure, quantizes cuts to frames and
   musical anchors, chooses source in-points by measured motion, adds section-aware typography,
   impact frames, vignette, and micro punch-ins, writes `music/sync_report.json`, renders at 1080p60,
   and muxes the supplied song at 320 kbps AAC.
   Before building the storyboard, unprompted faster-whisper word timestamps are checked for a
   conservative exact/fuzzy match to the brand. This intentionally does not force the word
   `PRAGON` into the recognizer: forced hotwords can hallucinate brand calls over instrumental
   passages. Accepted vocal cues receive a neon wordmark hit at the measured pronunciation.
10. The completed MP4 is promoted into the main **Final film** viewer automatically. This viewer is
    a native range-streamed video at a fixed 1× playback rate; switch to **Live previsualization**
    only when you want the editable Remotion graphics proof. Publishing stays off.

The final song must be uploaded before a real sync render can be produced. AtlasForge cannot infer
the rhythm or emotional arc of a file it has not received.

## What the free path does

- FFmpeg first decodes a canonical mono PCM analysis master so the analyzer and final mux share the
  same timing origin. Librosa then measures onset strength, tempo, beats, downbeat phase, multiband
  energy, rolls/fills, silence, surges/drops, and bottom-up structural sections locally.
- Grid and downbeat confidence are explicit. Rhythmic sections use bar-aligned hard cuts; sparse or
  calm sections use structural/phrase boundaries and longer holds. Peak sections can cut faster than
  intros and outros, but no shot drops below two seconds.
- Every scene boundary is quantized to the selected output FPS. `music/sync_report.json` records the
  nearest musical anchor and timing error for every cut, and rhythmic renders fail before footage
  generation if a boundary drifts by more than one frame.
- A lyric-aware human story grammar moves through arrival, reunion, mamak/garage conversation,
  female-led dance, male guitar performance, ciggies breaks, communal driving, rare peak drift,
  quiet departure, and the final ember resolve.
- The free-form director prompt has two outputs. A compact, normalized version is rotated through
  stock searches so Pexels can retrieve specific people, places, and atmosphere instead of seeing a
  paragraph. The complete editor wording is preserved in every premium/local generation prompt.
  Requests involving smoking automatically say the people are adults and exclude children,
  teenagers, and tobacco branding.
- Pexels Video and Pixabay Video form the real-footage pool. Local CLIP compares the actual candidate
  thumbnails to the shot brief; duration, resolution, creator diversity, and semantic relevance all
  affect selection. After download, FFmpeg measures both motion and hard source cuts, then picks an
  in-point whose internal activity matches the current music section without straddling an unrelated
  cut inside the source file. The chosen offsets are persisted in `videos/edit_windows.json` and the
  timed storyboard.
- Wan 2.2, premium video generators, and generated performer lanes are disabled in the Pragon
  profile. Missing licensed coverage fails closed.
- Remotion powers the deterministic live preview and beat-reactive graphics. The browser preview is
  isolated from Studio's polling updates, runs at a lighter 30fps, and exposes a real buffering state;
  completed MP4s use the browser's native range requests and immutable cache headers. FFmpeg/NVENC remains
  the final local renderer because it is faster and more reliable for dozens of real clips. Motion
  text cues and accent times live in the timed storyboard, so the preview and final export share the
  same creative clock. Peak sections may receive two text hits and three impact accents; quieter
  sections intentionally receive fewer.
- The Pragon profile keeps all visible branding in post, asks stock providers for clearly adult
  Malaysian or Southeast Asian casting, excludes third-party logos, and finishes on an owned
  macro ember-and-smoke closing plate. Barlow and Barlow Condensed are bundled locally under the SIL
  Open Font License, so the title treatment does not change between preview and export.
- The uploaded track remains the master. AtlasForge does not duck it under narration or replace it
  with generated music in music-film mode.

The Studio Docker image installs both `music-analysis` and `visual-ranking`, so Beat This and CLIP
are active in the normal local workflow. The first run downloads their model weights; later renders
reuse the model cache. A minimal non-Studio install can still opt in with
`pip install -e ".[music-analysis,visual-ranking]"`. AtlasForge records
`analysis_backend: beat_this` in `audiomap.json`; if the learned tracker is unavailable, the
deterministic Librosa/FFmpeg analyzer remains functional and records its confidence so the edit
planner can fail soft to phrase pacing.

Add `PIXABAY_API_KEY` for the second free stock pool and `GOOGLE_API_KEY` only if you intend to use
Gemini/Veo gap rescue. Pexels remains the first stock provider; missing optional keys are skipped
cleanly rather than failing the render.

Free stock cannot guarantee Sepang itself, a specific car model, official Pragon logos, or
recognizable race participants. For those exact visuals, provide owned or licensed event footage.

## Natural voice choices for narrated faceless videos

The normal **Editorial** generator now exposes:

- **Warm documentary** — `af_heart`, slightly relaxed pace.
- **Confident female** — `af_bella`, neutral pace.
- **Grounded male** — `am_michael`, slightly slower pace.
- **Editorial blend** — a local Kokoro blend of `af_heart` and `af_bella`.
- A 0.80–1.20× pace control, applied in the voice model rather than by pitching the finished file.

Kokoro is the default free option. The optional ElevenLabs integration is the most direct premium
voice upgrade: add `ELEVENLABS_API_KEY` to `.env`, choose **ElevenLabs · premium jump**, and set the
desired `voice.elevenlabs_voice_id` in the profile/config. Do not clone a person's voice without
their explicit permission.

## Premium upgrades in order of impact

1. **Owned/licensed motorsport footage** — the largest accuracy jump. API generation cannot replace
   real footage when the actual event, cars, sponsors, or venue must be recognizable.
2. **ElevenLabs voice for narrated films** — improves prosody immediately. Its official long-form
   model is `eleven_multilingual_v2`; pricing is usage based. See the
   [ElevenLabs TTS docs](https://elevenlabs.io/docs/overview/capabilities/text-to-speech) and
   [API pricing](https://elevenlabs.io/pricing/api).
3. **One Veo 3.1 Lite fallback shot** — add `GOOGLE_API_KEY`, enable premium scenes, keep the limit at
   one, and use `veo-3.1-lite-generate-preview`. It is considered only when licensed footage was not
   selected. Google currently lists no free API tier and prices
   720p Lite at $0.05/second, so an eight-second shot is about $0.40. See the
   [official Veo guide](https://ai.google.dev/gemini-api/docs/veo) and
   [live pricing](https://ai.google.dev/gemini-api/docs/pricing).
4. **Runway Gen-4/4.5** — useful for controlled image-to-video hero shots, but it is not wired into
   this repository today. Do not paste a Runway key expecting it to work. The official API uses
   separate developer credits; see [Runway API pricing](https://docs.dev.runwayml.com/guides/pricing/).

Spend premium video credits on one impossible-to-source signature shot, not every cut. Real licensed
race footage plus good editing will usually look more expensive than a full montage of unrelated
generated clips.

## Remaining human work

The irreducible manual work is: supply the final song; supply official logos/owned event media if
they must appear; confirm music and footage usage rights; and watch the export once for brand,
continuity, safety, and factual accuracy. No YouTube publishing setup is required for generation.
