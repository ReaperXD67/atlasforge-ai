# AI Viral Lab

AI Viral Lab makes one coherent 3–10 second, vertical AI-native shot at a time. It is designed for
the social-video patterns that need temporal consistency rather than a slideshow: a character
performing to music, two fictional characters speaking, or a physically credible fictional
spectacle. The final master is 1080×1920, 60 fps, H.264, with publishing disabled.

## What is already automated

- secure local JPG/PNG/WebP subject-reference upload and validation;
- secure local master-song upload, beat/downbeat analysis, and BPM-aware prompt choreography;
- one-shot prompt contracts that lock identity, anatomy, lighting, camera, and environment;
- reference-image input to the stock ComfyUI Wan 2.2 TI2V 5B workflow;
- subject-image input to Gemini Omni Flash, with locally derived song timing in the prompt;
- native-audio preservation for cloud clips and untouched 320 kbps master-song muxing;
- vertical crop/scale, local-AI motion interpolation, color normalization, and NVENC 60 fps output;
- a local procedural impact bed for physics clips that have no source audio;
- deterministic Remotion previsualization, per-clip cost estimates, run logs, and cancel controls;
- a synthetic-media provenance record in every run; and
- no upload or publishing action.

## Use it

1. Open `http://127.0.0.1:8741/?workspace=viral`.
2. Choose **Beat Creature**, **Talking Duo**, or **Physics Spectacle**.
3. Describe one shot, not a montage. Include the subject, action, location, camera, light, and ending
   pose. The UI gives a strong example for each recipe.
4. Add a clear subject image when identity matters. A three-quarter or full-body source with a clean
   silhouette and visible feet works best for performance.
5. For **Beat Creature**, upload the actual final song. AtlasForge detects its BPM, passes the audio
   locally, places BPM/timing instructions into the video prompt, and replaces the generated
   soundtrack with your untouched master in the final file.
6. Choose a reality lane and press **Generate viral master**.
7. Watch the full result before using it. The local file remains under `output/<run>/final/video.mp4`.

## Reality lanes

| Lane | Best use | This laptop | Audio | Estimated generation price |
| --- | --- | --- | --- | --- |
| **Free Local — Wan 2.2 TI2V 5B** | reference-led dancing character; silent/impact spectacle | practical on the RTX 4070 8 GB through ComfyUI offloading | supplied song or local impact design; no honest dialogue lip sync | $0 beyond electricity |
| **Native Realism — Gemini Omni Flash** | strongest identity continuity; BPM-directed movement; speaking characters | generated in Google cloud | native synchronized voices/SFX; your supplied song is muxed locally afterward | about $0.10/s at 720p |
| **Budget Native — Veo 3.1 Lite** | prompt-led native-audio clips at lower cost | generated in Google cloud | native audio | about $0.05/s at 720p |

Google currently recommends Gemini Omni Flash as the default video model for coherence, multiple
input modalities, subject consistency, and conversational editing. See the official
[Gemini video guide](https://ai.google.dev/gemini-api/docs/video) and
[Omni guide](https://ai.google.dev/gemini-api/docs/omni). Confirm current prices before enabling
billing in the [official Gemini API pricing table](https://ai.google.dev/gemini-api/docs/pricing).

## The only manual setup still required

The free local lane is already installed on the configured machine. You only provide creative
inputs that AtlasForge cannot invent on your behalf: a legally usable reference image, the song you
are authorized to use, and the final human review.

For cloud-native voice, lip sync, and the largest realism jump:

1. Create a paid Gemini Developer API key in
   [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Paste it into the ignored local `.env` file:

   ```dotenv
   GOOGLE_API_KEY=your_key_here
   ```

3. Restart Studio with `./scripts/start_studio.ps1`.

The Docker image already contains the current Google SDK. No other package install or source-code
change is required. A 5-second Omni generation is estimated around $0.50; an 8-second generation
around $0.80. AtlasForge displays the estimate before generation and never calls the cloud lane
until you explicitly choose it and press Generate.

Gemini Omni's current API does not accept uploaded audio as a generation reference. AtlasForge does
not pretend otherwise: the song never leaves the computer, its BPM and requested timing guide the
prompt, and the exact song becomes the final audio master. This is strong beat direction, but not a
guarantee that every generated body movement lands on a waveform transient.

## Why the local lane has an honest limit

The official Wan family includes stronger audio-driven and motion-transfer models:

- Wan 2.2 S2V 14B drives a character from an image and audio for dialogue, singing, or performance.
- Wan 2.2 Animate 14B transfers motion and expression from a driving video to a character image.

Those are 14B-class workflows. They are valuable on substantially larger GPUs, but they are not a
reliable default on this 8 GB laptop. AtlasForge therefore uses the official 5B TI2V model that
[ComfyUI documents as fitting well on 8 GB VRAM](https://docs.comfy.org/tutorials/video/wan/wan2_2)
and refuses to label its free Talking Duo output as exact lip sync. The upstream capabilities are
documented by [Wan 2.2](https://github.com/Wan-Video/Wan2.2) and the
[ComfyUI S2V guide](https://docs.comfy.org/tutorials/video/wan/wan2-2-s2v).

LTX Desktop is also not the default because its official local requirements currently call for at
least 16 GB VRAM and about 160 GB of free disk. See
[LTX Desktop](https://github.com/Lightricks/ltx-desktop).

## CLI

```powershell
atlasforge viral-film `
  --recipe beat_creature `
  --concept "A ginger cat performs crisp footwork in a glossy pit garage" `
  --provider local_wan `
  --reference .\cat.png `
  --track .\song.mp3 `
  --seconds 5
```

Use `--provider gemini_omni` for the strongest native lane or `--provider veo` for the cheaper
native-audio lane. Talking Duo also accepts `--dialogue-a` and `--dialogue-b`.

## Safety and provenance

Physics Spectacle prompts are forced into fictional, unoccupied structures with no real landmark,
person, injury, emergency branding, or news framing. Every run records
`contains_synthetic_media: true`. Do not remove that disclosure or present generated footage as
documentary evidence. Reference images and music must be owned, licensed, or otherwise authorized.
