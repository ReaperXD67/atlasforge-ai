# AI Cinema V3 review

The active film retains the seven original AI worlds and adds ten matching scenes. Seventeen artworks form 52 phrase-led shots, with inferred depth, continuous camera travel, selective material motion and short optical handoffs. The original 185-second song and all 71 cue intervals remain intact. All nine encoded brand lines read **Bosston**; the source logo correctly reads uppercase BOSSTON.

## Admission and motion

All 17 color/depth pairs pass SHA-256, dimensions, grayscale range, model revision and Apache-2.0 license checks. CPU depth preparation took 22.585 seconds. Missing/stale depth and incorrect brand spelling fail preparation or verification.

HyperFrames lint, runtime, layout and sampled contrast checks pass. Five nonblocking structure warnings concern intentional logo reuse, dense shot/caption lanes and root bookend grouping. The local Noto font is served rather than inlined because it is 23.4 MB. The editable preview was opened before export.

The native Chrome gate passed 35 selected seeks, 17 actual depth maps with no fallback, no sampled shader/context error or effectively blank picture, and three exact repeated-time canvas hashes. The 32.24-second silk handoff and additional silk/light seams were inspected for opaque coverage. The outgoing linear camera continues through the overlap; the wipe crosses the complete feather before the transition ends. Three dark top-edge flags belong to the drum artwork, not missing picture coverage.

A 14-second actual-composition proof has 420 frames at 1080p30 and passes full decoding. Its source/proof audio correlations are 0.999722 / 0.999757 at zero offset. Its 229.836-second capture includes PNG screenshot/pipe encoding and is not the final render benchmark. Sampled direct-seek timings exclude screenshot/readback.

## Encoded delivery

The master is **185.000 seconds / 5,550 decoded frames / 1920 × 1080 / 30 fps**, H.264/yuv420p with 48 kHz stereo AAC, **788,619,064 bytes (752.1 MiB)**. Both complete soundtrack channels match the original at zero offset: **0.99683083 / 0.99686263**. The 720p copy is **62,201,607 bytes (59.3 MiB)**, fully decodes and retains the encoded AAC payload byte for byte.

The master rendered in **398.5 seconds**, including **391.2 seconds** of screenshot capture. This excludes artwork generation, depth preparation and review. The actual export's SHA-256 is `8b12f8f5ccaa17e3372215bdf723be2a71e49d32dd13816fa1a1ff46a8858100`.

All **52 encoded shot midpoints** were inspected across four contact sheets. No blank/missing world, clipped lyric block, incorrect logo or major anatomy/framing distraction was found. Some sampled lyrics are inside their short entrance/exit fades. All **nine native-resolution Bosston crops** were separately inspected; spelling and surrounding lyric text match, and every exact decoded sample timestamp lies inside its cue. These are actual MP4 frames, not source-only checks.

## Picture correspondence diagnostic

Eleven exact-clock native picture bands match the expected browser composition with RGB mean absolute error **2.669–3.335 / 255** and BT.709-luma SSIM **0.988110–0.990652**. No frame-offset search, resize, crop fitting or color fitting is used. The older stock export is a negative control and is rejected at all three sampled positions.

The initial strict **raw-RGB SSIM ≥0.97** diagnostic remains recorded as **failed**, with actual scores **0.928824–0.968632**. It is not relabeled as a pass. A lossless required 4:2:0 roundtrip of an expected frame itself scores only **0.951285 RGB SSIM**, while luma remains **0.997407**: fine saturated chroma edges make that raw-RGB threshold unsuitable for this format. Luma correspondence and color-error measurements are reported separately; thresholds were not lowered. See `output/bosston-ai-v3/ai-binding.json` and `encoding-diagnostic/encoding-diagnostic.json` for the distinct results.

## Limits

This is 2.5D animation of generated artwork, not native generated-video footage. Relative depth cannot reconstruct hidden surfaces or create fully articulated creature performances. Thin dark/jagged outlines can appear on a few luminous whisker/ribbon edges at native scale. Vocal timing remains model-derived and was not independently human-auditioned. Sampled stills and technical checks do not establish complete real-time visual quality or audience response. Stock and low-detail 3D experiments are inactive.
