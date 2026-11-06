# BizNex cinematic replacement acceptance

The user rejected the six delivered pilots as too plain on 6 November 2026. The first public
pilot and its receipts are preserved; the five unpublished follow-ups are held in the queue.
The replacement [Second Question film](../videos/biznex-second-question/README.md) is now rendered.
Its [actual export review](../videos/biznex-second-question/REVIEW.md) records 85 decoded-frame samples,
all 1,223 frames decoded, and 14/14 final-mix ASR matches. A source preview, attractive still or
passing encoder check alone is not evidence of creative quality or audience response.

## Evidence and reference limits

The [supplied reel](https://www.instagram.com/p/De90LRWT20V/) was inspected earlier in the
authorized browser: duration 74.68 seconds, selected moments with a presenter, editing
demonstrations, a stylized character, inset footage and short captions. The fresh read-only
web request on 6 November was throttled. We have no complete transcript, cut list, audio
analysis or verified retention data for it. Do not invent those measurements or copy its
footage, narrator, script or music. The useful direction is a changing visual argument with
human presence and concrete demonstrations.

Baseline measurements were made from all six actual `renders/final.mp4` files, rather than
their HTML previews. The local report `output/social/cinematic-benchmark/baseline.json`
records each video hash. The existing 18-frame decoded contact sheet was inspected again.
All six use the same broad desk-and-paper composition; the source timelines divide each
into five story beats. A story beat is not a distinct camera shot.

| Delivered pilot | MP4 container duration | Longest authored beat | Full-frame scene-change detections |
| --- | ---: | ---: | ---: |
| Two paper doors | 27.50s | 12.12s | 0 |
| Card under the cup | 26.50s | 6.48s | 0 |
| Missing index card | 26.90s | 9.08s | 0 |
| Two ribbons | 26.50s | 7.46s | 0 |
| Receipt fold | 26.10s | 10.84s | 0 |
| Three empty boxes | 30.80s | 8.60s | 0 |

Detection method: FFmpeg decode, downscale to 270 x 480, select frame-to-frame scene scores
greater than 0.30. This detects large image changes; it can miss cuts and count large motion
as a change. Zero detections does not mean zero animation, and the detector is not a quality
or retention score. Beat lengths come from measured `timing.json`. Container durations can
include a small audio tail beyond the authored frame duration. Reproduce one decode with:

```powershell
ffmpeg -hide_banner -nostdin -threads 2 -i videos/biznex-two-paper-doors/renders/final.mp4 -filter_threads 1 -vf 'scale=270:480,select=gt(scene\,0.30),showinfo' -an -f null -
```

Once the replacement MP4 exists, compare actual exports with the reusable local measurement
script. It preserves the scene-detection settings above and adds full-frame grayscale change
statistics at 8 samples/second and 90 x 160 pixels. The latter include captions, cuts, camera
movement and subject movement; they do not isolate acting or establish a better film. The
report records both input hashes, stream properties and FFmpeg version, and assigns no score
or pass/fail. Missing adjacent samples are reported as unknown, not zero motion.

```powershell
.\.venv\Scripts\python.exe scripts/compare_cinematic_exports.py --baseline videos/biznex-two-paper-doors/renders/final.mp4 --candidate videos/biznex-second-question/renders/final.mp4 --output output/social/cinematic-benchmark/comparison.json
```

This command does not render or publish. Both local files must exist and remain unchanged
during analysis. By default it refuses videos longer than 600 seconds. Compare the same
measurement settings and inspect the films themselves; do not use this report as an audience
experiment result.

## Proposed production gate

These are creative hypotheses for this replacement, not platform requirements or promises
of reach. Record actual timestamps and outcomes against the final MP4 before claiming a pass.

| Area | Baseline weakness | Replacement evidence required |
| --- | --- | --- |
| Opening | A heading and small paper props explain the premise | A legible human action or unresolved choice in the first two seconds; no logo preamble. It must make sense muted. |
| Shot language | One broad desk arrangement with small reframings | At least three distinct shot scales and six purposeful shot/visual beats; show environment, face/reaction and close evidence. Transitions must change understanding, not merely decorate. |
| Subject movement | Mostly flat prop transforms | At least two usable moving-subject shots with stable identity, anatomy and objects; an image pan alone does not satisfy this. Reject visible face/hand warping. |
| Narrative | Long explanation before the purpose note | A specific decision, a credible obstacle and a changed action; the final reveal answers the opening. Every factual sentence must be necessary. |
| Pacing | Long factual beats up to 12.12 seconds | Map visual actions to spoken beats; avoid more than four seconds without new story information or deliberate reaction. A quiet emotional hold is allowed when its purpose is recorded. |
| Voice | One measured narrator timbre; naturalness not established by timing | Listen to the whole exported mix. Document at least three intentional delivery changes, clear words and pauses; disclose the actual provider and controls. Reject stitched syllables, unexplained accents, overacting and music masking. |
| Caption and sound craft | Correct word timing but a repeated lower text band | Review real phone-size frames for text/face conflicts; inspect word seams. Listen for motivated sound events, clean transitions and intelligible narration. No effect quota substitutes for judgment. |
| Facts and rights | Sourced U.S. examples with fiction disclosure | Retain current official source/date/market mapping, spoken fiction disclosure and no invented testimonial, earnings or medical claim. Record origin, license and voice consent for every acquired asset. |
| Delivery | Six technically passing exports | Actual final H.264 1080 x 1920 at 30fps with stereo 48kHz audio, media/source hashes, captions and thumbnail; all existing production checks still pass. |

Review the actual prototype end to end with sound, then at phone size and muted. Capture
decoded frames covering the opening, subject motion, factual evidence and payoff, plus every
transition. Write timestamped defects and fixes. Compare the final MP4 against the baseline
using the same scene detector, while making the creative decision from the film itself.
Do not mark an unheard mix or unrendered composition approved. Scale to more episodes only
after the prototype meets this gate; do not release held jobs as a shortcut.

## Character-motion inputs delivered

The replacement project `videos/biznex-second-question` now has two original silent
image-to-video clips, `assets/motion/mira-night.mp4` and `mira-morning.mp4`. Each is H.264,
384 x 672, 20fps, 65 frames and 3.25 seconds. They were generated locally with the existing
cached Wan2.2 TI2V 5B model; no paid API or additional model download was used. Both decoded
successfully with 65 distinct frames. Thirteen chronological frames per clip were inspected:
the night shot shows a blink and a doubtful expression; the morning shot shows writing-hand
and expression movement. This sampled review does not establish full-speed playback or final
1080 x 1920 crop quality. The clips have no spoken performance or lip-sync.

`MOTION_PROVENANCE.json` records reference/output hashes, prompts, seeds, settings, the model's
[Apache-2.0 license source](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B), decode results and
review limitations. The HyperFrames local media inventory also registers both clips. Generated
media and review sheets remain ignored; the reproducible script and provenance are source files.

```powershell
# Inspect one planned local job; no generation by default.
.\.venv\Scripts\python.exe scripts/generate_cinematic_motion.py --shot mira-night
# With cached weights and exclusive GPU availability, start local ComfyUI then submit one job.
.\scripts\start_comfyui.ps1
.\.venv\Scripts\python.exe scripts/generate_cinematic_motion.py --shot mira-night --execute
.\.venv\Scripts\python.exe scripts/generate_cinematic_motion.py --shot mira-morning --execute
```

Run from the repository root. The generator refuses existing outputs and nonlocal ComfyUI
endpoints. Preserve successful candidates; do not rerun to overwrite them. Coordinate GPU
ownership with voice inference, and release ComfyUI models after its queue empties. Final
editing must use the measured clip durations and inspect the actual scaled result.

## Audience test after creative acceptance

No audience lift is measured yet. Keep the existing experiment IDs and predeclared metrics,
but identify the replacement as a new creative version. Evaluate at comparable 24/72-hour
ages and within each platform; retain missing values. YouTube says recommendations consider
view choice, duration, percentage viewed and satisfaction, and do not require a minimum
posting cadence. Faster cutting alone is not a ranking rule.
[YouTube Shorts guidance](https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en).

Keep Shorts feed exposure and stayed-to-watch separate from thumbnail impressions and CTR;
average view duration/percentage viewed use engaged viewers. Store only definitions that
match the exported field. [YouTube metric definitions](https://support.google.com/youtube/answer/12220281).
Meta's current Facebook guidance emphasizes original production and substantial creative
contribution; a copied reel with cosmetic changes is not the strategy.
[Meta originality guidance, March 2026](https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/).

Use qualified clicks, saves/shares and useful questions alongside watch metrics. A single
post or insufficient impressions cannot establish a winning format, reach guarantee or
Atomy conversion rate. The analytics report must continue to disclose sample limitations.
