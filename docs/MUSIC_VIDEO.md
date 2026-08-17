# Remotion Music Film workflow

AtlasForge now has a separate music-first path for faceless event films. It does not force a song
through the long-form explainer timeline.

## Make the Bosston × Pragon racing sample

1. Start Studio with `./scripts/start_studio.ps1` and open `http://127.0.0.1:8741/`.
2. Select **Remotion Lab** in the top bar.
3. Click **Upload your final song** and choose MP3, WAV, M4A, AAC, FLAC, or OGG. The file is
   written only to `output/.studio/uploads/`.
4. Wait for the local analyzer to show BPM, downbeats, and energy sections.
5. Set the event title and choose a 30, 60, 90, or 180-second cut. Use 60 seconds for the first
   boss review.
6. Leave **CLIP-ranked footage** on. Enable **Wan hero shot** only if ComfyUI is ready and you can
   accept the extra local render time.
7. Play the Remotion preview. Its orange track pulse and motion are driven by the uploaded master;
   it is a graphics proof, not fake footage.
8. Click **Build beat-synced race film**. The job downloads real race-circuit footage, rejects weak
   visual matches locally, quantizes cuts to musical bars, creates the opening event card, renders
   at 1080p60, and muxes the supplied song at 320 kbps AAC.
9. Open the latest render and watch it once before showing it externally. Publishing stays off.

The final song must be uploaded before a real sync render can be produced. AtlasForge cannot infer
the rhythm or emotional arc of a file it has not received.

## What the free path does

- Librosa detects onset strength, tempo, beats, downbeats, and a normalized energy curve locally.
- Hard cuts use four- or eight-beat phrases and never drop below two seconds, avoiding frantic
  random cutting while landing cleanly on the musical grid. Soft crossfades are reserved for
  narrated films because they weaken race-trailer downbeats.
- A racing shot grammar moves from circuit geography to mechanical details, velocity, peak action,
  and event closure.
- Pexels Video supplies real footage. Local CLIP compares the actual candidate thumbnails to the
  shot brief; duration, resolution, creator diversity, and semantic relevance all affect selection.
- Wan 2.2 is limited to one high-value hero shot. This keeps the RTX 4070 Laptop GPU usable and
  prevents local diffusion from becoming the bottleneck.
- Remotion powers the deterministic live preview and beat-reactive graphics. FFmpeg/NVENC remains
  the final local renderer because it is faster and more reliable for dozens of real clips.
- The uploaded track remains the master. AtlasForge does not duck it under narration or replace it
  with generated music in music-film mode.

Free stock cannot guarantee Sepang itself, a specific car model, official Bosston/Pragon logos, or
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
3. **One Veo 3.1 Lite hero shot** — add `GOOGLE_API_KEY`, enable premium scenes, keep the limit at
   one, and use `veo-3.1-lite-generate-preview`. Google currently lists no free API tier and prices
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
