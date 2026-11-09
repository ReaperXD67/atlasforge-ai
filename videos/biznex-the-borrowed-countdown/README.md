# The Borrowed Countdown

**The timer was loud. My reason was missing.** An original fictional miniature
about noticing when urgency has replaced a reason to choose.

The new visual world is a physical countdown on a sculptural desk: hinged digits,
moving shadows and a ceramic decision token. A camera move reveals the digits'
shallow construction, then follows the token onto its own path. It uses original
code-authored geometry, the pinned local Three.js/GSAP stack and synthetic narration;
no image or video model is used.

## Production

Rendered and inspected **9 November 2026**: 23.9 seconds, 717 frames, 13 shots,
1080 × 1920 at 30 fps, H.264 and stereo 48 kHz AAC. The nine-stage pipeline passed
in 393.5 seconds using already prepared narration. Full media decode, all five
encoded-speech checks, exact captions and audio alignment passed. All ten decoded
contact sheets (78 unique frames) were inspected with no blocking sampled findings.
Full-speed playback and subjective listening were not verified by these checks.

Final MP4 SHA256: `02d020817b8a86c4a1e686c4e8b9e112eacdab7d1af7c3dc4afa6b45a46bf857`.

The owner has paused automatic runs; this release was explicitly requested.

From the repository root, after the reviewed recipe is prepared:

```powershell
.venv/Scripts/python.exe scripts/run_story_pipeline.py videos/biznex-the-borrowed-countdown
.venv/Scripts/python.exe scripts/run_story_pipeline.py videos/biznex-the-borrowed-countdown --execute --resume
```

The voice stage retains complete thought groups and verifies the exact spoken
words. The scene recipe anchors action to measured speech; render, encoded audio
and decoded frame checks precede editorial review. Packaging and social release
remain separate operations after the actual film is inspected.

See [the brief](BRIEF.md), [script](script.txt), [voice plan](VOICE_PLAN.json),
[composition direction](composition-brief.md), [publishing copy](UPLOAD_COPY.md)
and [credits](CREDITS.md). The source checkout omits local model weights and
generated WAV/MP4 files. See [the render receipt](renders/final.report.json), [audio checks](qa/audio/encoded-audio-verification.json)
and [sampled review](DELIVERY_REVIEW.json) for the delivered edition.

BizNex is an independent educational community discussing informed choices around
Atomy. This illustrative story is not a customer testimonial or an official Atomy
announcement. Technical checks cannot establish emotional realism or audience reach.

Published once on 9 November 2026: [YouTube](https://www.youtube.com/shorts/mizAF51be5U),
[Instagram](https://www.instagram.com/p/Dfg3FalKNsv/) and [Facebook](https://www.facebook.com/reel/1495079932486622).
YouTube processing, public visibility and exact subtitles were verified through the API;
Meta owner, public visibility, AI labels and full captions were observed in the browser.
