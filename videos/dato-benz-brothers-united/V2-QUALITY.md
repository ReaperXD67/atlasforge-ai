# Hock Siew V2 picture-quality evaluation

The native24 cadence, neutral treatment and restrained detail filters below were adopted in V2, together with lossless FFV1 staging and one final H.264 picture encode. Measured delivery and review are recorded in `DELIVERY-V2.json` and `REVIEW-V2.md`; short benchmark results below are scoped to their tested excerpts.

Observed 19 November 2026. No paid generations, model downloads, installed packages or production-source edits were made. Benchmarks and derived image comparisons remain under `output/hock-v2-quality/`.

## Recommended small changes

1. Deliver the V2 film at **native 24fps**. Current native Runway footage is 1280×720 at 24fps. V1's `fps=30` produces repeated frames with an uneven conversion cadence. In an unretimed three-second native test, 30fps produced 18 near-duplicate adjacent pairs out of 89; 24fps produced 0 out of 71. This is a cadence measurement, not a claim about the whole film or artistic quality. For 196.760 seconds, 24fps requires `ceil(196.76*24) = 4,723` frames, picture duration 196.791667 seconds, with the full unchanged soundtrack. All hard-coded 30s and verifier clocks must change consistently; keep audio timestamps unchanged.
2. Use restrained luma-only sharpening after the 1.5× upscale: `unsharp=3:3:0.18:3:3:0`. The comparison image shows slightly clearer fabric and edge definition without obvious new halos in this sampled face/shoulder frame. Do not describe this as recovered native detail.
3. Remove the extra amber colour-balance pass on already-warm Runway shots. Tested candidate: `eq=contrast=1.012:saturation=.98`, omitting V1's `colorbalance=rs=.008:bs=-.006` and slight negative brightness. Skin and shadow detail look a little more neutral in the same-instant sample. Adapt individual new hero shots after inspection rather than force one warm cast across everything.
4. Keep output at 1080p with high-quality H.264. Source720→output1080 is upscaling; exporting 4K alone would not prove better source detail. Prioritize identity-led content, visible source motion and editorial clarity over a resolution label.

Candidate native filter sequence (assumes no retiming):

```
fps=24,scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,
crop=1920:1080,setsar=1,unsharp=3:3:0.18:3:3:0,
eq=contrast=1.012:saturation=.98,format=yuv420p
```

The tested three-second samples use the same native source instant, the installed FFmpeg7.1 binary, NVENC p6/vbr/cq17/14M. V1 conversion encoded in 2.84s; native24 gentle candidate in 1.24s. Motion-interpolated30fps took20.37s. Single-short-run timings include initialization and are not throughput guarantees.

## Upstream choices and licence review

| Primary source | Inspected version / maintenance | License / decision |
| --- | --- | --- |
| [FFmpeg](https://github.com/FFmpeg/FFmpeg), [filter manual](https://ffmpeg.org/ffmpeg-filters.html#minterpolate) | Installed imageio-ffmpeg0.6.0 resolves FFmpeg7.1. Upstream head `01ca75d35067cff8c2d0c3e7ed75e3f537ee10c4`, dated2026-11-19, was inspected for current maintenance. | Core LGPL2.1+, with optional GPL parts; installed static build enables GPL/version3. **Adapt existing filters only.** No copied upstream code or binaries distributed. |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | Head `a4abfb2979a7bbff3f69f58f58ae324608821e27`, dated2024-04-02. No local model weights found. | BSD-3-Clause. **Defer installation**: requires new model/runtime handling and per-frame restoration would need temporal/identity review. An untested model is not automatically a quality improvement. |
| [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan) | Head `a7532fc3f9f8f008cd6eecd6f2ffe2a9698e0cf7`, dated2022-10-23. No local models found. | MIT. **Defer**: native24 delivery already removes conversion cadence without synthesized face/hand frames or a new Vulkan executable. Do not bypass Windows application-control restrictions. |

FFmpeg `minterpolate` is available in the installed binary and tested successfully. It uses bidirectional motion compensation and generates distinct intermediate frames, but its 20.37s time for3s (versus1.24s native24) and need for denser occlusion review offer no compelling gain for a cinematic24fps delivery. The official manual notes scene detection replaces interpolated frames with duplicates at a detected cut. Interpolate only individual shots if a future specific slow-motion need warrants the extra review; never interpolate a whole edit across cuts or burnt-in captions.

Runway's available `upscale_video` connector can upscale clips under40seconds and requires local videoFile or an uploaded/public source. Its metadata does not quote a cost before submission. No call was made because root owns the finite326-credit budget and is prioritising identity-preserving new shots.

## Evidence

- `benchmark.json`: exact filters, timings, encoded sizes, hashes and adjacent-frame cadence counts.
- `comparison.jpg`: V1 versus native24 gentle treatment, same source instant, plus100% crop.
- `v1-30fps.mp4`, `v2-24fps-gentle.mp4`, `v2-minterpolate30.mp4`: three-second sample encodes.

No objective super-resolution accuracy is claimed: there is no higher-resolution ground truth. The major demonstrated improvement is removal of avoidable24→30 cadence; the detail/colour treatment is a subtle sampled visual preference.
