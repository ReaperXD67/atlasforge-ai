# V4 image-film tool decisions

Observed 20 November 2026. This is a focused comparison for the Hock Siew image-only revision, not a claim that additional software improves audience response. No paid model generation or account action was performed by this research.

| Candidate | Exact evidence and dependency cost | Decision |
| --- | --- | --- |
| [Three.js](https://github.com/mrdoob/three.js) | Current dev head `8b92052852735b67cfa8393f78e707b3f07a0eec`, 20 November. MIT. Existing local r187 pin `7e89746a687bb88271253698fa108b1dd59825d0`; zero runtime dependencies; adopted module bytes total 2,133,699. | Reuse the exact reviewed local pin. Perspective textured layers, foreground occlusion and one deterministic camera are sufficient. |
| [GL Transitions](https://github.com/gl-transitions/gl-transitions/tree/deeebdee7581cdfe924ed9cf104ea2fd10e63155) | Head `deeebdee7581cdfe924ed9cf104ea2fd10e63155`, 18 November. Repository MIT; individual headers govern. Inspected `LumaWipe.glsl`: author gre, MIT. | Adapt only this small grayscale-mask blend. Preserve shader header and full repository license. No transition-package or adapter dependency. |
| [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2/tree/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf) | Head `a561b849ebae10a6f5ef49e26c83cbbcd36c71bf`, 24 March. Code and Small weights Apache-2.0; larger weights CC-BY-NC-4.0. Existing Small HF revision `5426e4f0f36572d16453bbda7a8389317b1bef99` and model SHA256 are already verified locally. | Optional offline depth preparation for invented landscapes only. The renderer accepts a local map and adds no ML dependency. Actual person photographs remain flat. |
| [GSAP](https://github.com/greensock/GSAP) | Head `5e6c35ff8eedea12d4f229129def635277d8b0f2`, 4 November. Existing vendor is 3.14.2. [Standard No Charge License](https://gsap.com/community/standard-license/) permits commercial use with specified visual-builder restrictions; this is not MIT. | Reuse the existing paused clock and retain its vendor notice. |
| [DepthFlow](https://github.com/BrokenSource/DepthFlow/tree/4d002b49f0ee2172d38fac93dcbc50c487e12301) | Head `4d002b49f0ee2172d38fac93dcbc50c487e12301`, 13 November. AGPL-3.0. Dependencies include ShaderFlow, Torch/TorchVision/Transformers and a separate CLI. | Defer. Automatic depth clips do not solve personal likeness or scene staging; existing Three can provide the useful layered camera behavior. |
| [PixiJS](https://github.com/pixijs/pixijs/tree/1e707686d00a2a8cd6432b047e56034fc7e7a909) | MIT; dev head `1e707686d00a2a8cd6432b047e56034fc7e7a909`, 11 November, repository pushed 19 November. | Defer a second GPU scene renderer. |

## Applied changes

The isolated `v4-renderer/` provides a plan compiler, locally frozen media, Three.js scene graphs, foreground PNG/geometry occlusion, camera waypoints, optional restrained depth for artwork, literal aspect-preserving photo crops, a reviewed luma-mask handoff and canonical cue display. The original photographs are copied byte-for-byte; no generated body, face restoration, depth deformation or generative video is used. No previous film source is modified.

The local motion-doctrine, cut-the-curve and seam-craft skills inform directional continuity, intentional arrivals and an opaque canvas. A long emotional music film does not need every scene to follow launch-video transition density. Camera keyframes can use linear or explicit eased travel, rather than an independent oscillation per scene. Selected meaningful masks and foreground occluders provide transitions appropriate to the paper/ink/bronze world.

`v4-renderer/UPSTREAM.json`, the original MIT shader and complete license retain provenance. `build-receipt.json` records exact input/vendor hashes after each build. Original art and private photographs remain ignored local media.

## Verification boundary

The smoke harness uses installed HyperFrames' Puppeteer dependency and local Chrome; it adds no package. It samples scene starts, moving interiors, mask seams and original photographs, captures 1080p PNGs, and verifies that seeking away/back produces identical screenshot bytes. The official pinned HyperFrames check and encoded short render are separate checks. Benchmarks distinguish render-call time from screenshot/encode cost. A short prototype does not establish full-song quality or the boss's acceptance; the full edit still requires decoded-frame and original-audio/cue verification.
