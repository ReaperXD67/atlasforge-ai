# Rendered delivery review · 6 November 2026

The final file is `renders/final.mp4`, **40.766667 seconds**, **1080 × 1920 at 30 fps**,
with H.264/yuv420p video and stereo AAC at 48 kHz. All **1,223 frames** and the complete audio
stream decoded successfully. The source snapshot matches the verified render sidecar.

SHA256: `511bb20e58f0b7497899f22e400af553d0c54b8338ede961f1cf88d5578945b6`

The [machine-readable review record](DELIVERY_REVIEW.json) includes the measured results,
review scope and hashes of the underlying evidence files.

## Actual-frame inspection

Two reviewers inspected the new composition and selected decoded final frames. The independent
final pass covered **85 distinct frames across 11 sheets**: all 18 shot midpoints, both sides of
every cut, moving-subject samples, the dissolve and opening/ending. No blocking visual defects
were found in those samples. This is sampled frame review, not a full-speed human playback claim.

The final export corrects these defects found in the first encoded candidate:

| Time / frame | Earlier defect | Verified final behavior |
| --- | --- | --- |
| 4.733 s / 142; 19.433 s / 583; 32.633 s / 979 | One frame appeared at the unposed camera scale | First and next frames use the intended camera pose |
| 30.533–30.933 s / 916–928 | Morning flashed before the dissolve returned to the outgoing screen | Terms screen remains at the start, then blends progressively into morning |
| Throughout secondary UI | Some small supporting labels were difficult to read | Minimum authored secondary font size is 28 px; primary captions and headings remain larger |

Still scenes and captions now have one visibility owner: the frame-addressed composition.
HyperFrames retains timing for actual audio/video media. Regression tests cover exact boundaries,
small timestamp rounding errors and backward seeks. Browser checks found no runtime errors or
layout issues across 17 samples; all 23 sampled contrast checks passed. Three authoring warnings
and ten craft heuristics remain, principally short text holds and flat composition structure.
These warnings are not presented as zero-warning approval.

## Exported sound and words

The actual encoded soundtrack measured **−16.01 LUFS**, **−3.65 dBTP**, with no clipped or
nonfinite samples. Its measured lag against the pre-encode master is **0 ms**, correlation
**0.999882**. The master and narration hashes match their receipts.

All **14 of 14** independent ASR checks on encoded speech windows match the approved script.
The soft final line initially competed with the music. A speech-anchored 6 dB score reduction
raises its measured voice-to-bed ratio from 7.59 dB to **13.59 dB**, preserving the original
narration. The final recognizer reads “Before the next tap” correctly. These checks establish
timing, technical fidelity and transcript agreement; emotion and voice preference remain listening
judgments, and no ElevenLabs-equivalence claim is made.

## Baseline comparison and remaining limits

Using the same full-frame FFmpeg detector, the published paper pilot has zero large scene-change
events and this film has seven. At eight grayscale samples per second, the fraction of adjacent
samples changing by at most one 8-bit luma unit falls from **89.95% to 44.00%**. Captions, camera
movement, edits and subject movement all contribute. These are pixel measurements, not a creative
quality score, retention experiment or prediction of reach.

The two original Wan clips have 384 × 672 source resolution and are softer than the photographic
plates in the 1080p export. They show character action, without lip-synced speech. No subjective
full-mix listening approval or audience result is asserted. The five older unpublished pilots
remain held; this new film has not been posted to the social platforms.

Validation at delivery: **638 Python tests passed**, one Windows symlink-permission skip; Node
renderer suites and Ruff passed. The release includes exact prepared media, source fingerprints,
complete captions, attribution and a standalone rebuild guide. Detailed working review sheets
and measurements remain under ignored `output/cinematic-final-review/` and
`output/reports/hero-encoded-audio-v2/` on the production workstation.
