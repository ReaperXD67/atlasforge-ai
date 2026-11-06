# Fast authored visuals for the next film

Research observed on 6 November 2026. The completed **The Second Question** film and its fingerprinted renderer remain unchanged. This investigation addresses the next film: no image models, no downloaded character model, and no sequence of static cards. Root creative direction and measured narration still determine the final scene design.

## Decision

Keep HyperFrames and the existing GSAP clock. Add **Three.js 0.187.0**, locally pinned, for original geometry and lighting. Use native SVG/DOM for sharp labels, invented interface inserts and kinetic typography. One scene function computes every object, camera and overlay state from a requested frame. No physics engine, React runtime, second editor or new animation framework is needed.

| Candidate / inspected version | License, maintenance and actual cost | Decision |
| --- | --- | --- |
| [Three.js r187](https://github.com/mrdoob/three.js/commit/7e89746a687bb88271253698fa108b1dd59825d0), released 30 October 2026 | [MIT](https://github.com/mrdoob/three.js/blob/r187/LICENSE), copyright 2010–2026 three.js authors; retain notice. Package has zero runtime dependencies. The two adopted WebGL module files total 2,133,699 bytes raw / 419,412 bytes gzip, measured from the integrity-verified npm archive. | **Adopt.** Materials, cameras, bevelled extrusion and reusable geometry make authored object scenes faster to implement than raw shaders. Use the [WebGL2 renderer](https://threejs.org/docs/pages/WebGLRenderer.html), not the more complex WebGPU/post-processing path. |
| [OGL 1.0.11](https://github.com/oframe/ogl/commit/385ce65c352c70734a36dc98c787fdd1d30ddb3b), public head 13 April 2025 | Package declares Unlicense and the [maintainer README](https://github.com/oframe/ogl/blob/385ce65c352c70734a36dc98c787fdd1d30ddb3b/README.md) contains the public-domain dedication. Zero runtime dependencies; npm package 423,239 bytes unpacked. README claims 29 KB minzipped across core/math/extras; that is not our benchmark. No GitHub releases; public development is substantially less recent than Three.js. | **Defer.** Good for a custom shader effect, but this film needs physical-looking objects and lights. Its lower-level API moves material/lighting work into our code. |
| [Theatre.js public head](https://github.com/theatre-js/theatre/commit/6ea82b938ea49609489f6377ded693ccc6ee8f5b), 11 April 2024; npm 0.7.2 | [Core Apache-2.0 / studio AGPL-3.0-only](https://github.com/theatre-js/theatre#license). Public head announces private development; an upcoming 1.0 is not evidence of a shipped public release. Core depends on dataverse and is 903,189 bytes unpacked; studio 22,283,657 bytes. These package sizes are not browser bundle sizes. | **Defer.** Another authoring editor, dataflow layer and clock add cost without helping this frame-driven pipeline. No studio source or dependency is copied. |
| [Motion 14.10.1](https://github.com/motiondivision/motion/commit/78f3ff51b5508f7e8c1c283d8e80bcd26fec37d7), 6 November 2026 | [MIT](https://github.com/motiondivision/motion/blob/78f3ff51b5508f7e8c1c283d8e80bcd26fec37d7/LICENSE.md). Active release; full package depends on framer-motion/tslib; React peers are optional. Maintainer [animate documentation](https://motion.dev/docs/animate) lists 3.2 KB mini / 22 KB hybrid; these are maintainer figures, not measured here. | **Defer.** A sound HTML/SVG animation option for a new website, but duplicates the existing tested GSAP timing path. Native SVG needs no additional library. |

The focused comparison stops here: neither popularity nor another framework would improve this particular production path. Remotion was already evaluated in [the cinematic research record](CINEMATIC_EDIT_PLANS.md); changing renderers would not create better objects or storytelling by itself.

## Skills and concrete reuse

Applied the local repository-research skill and HyperFrames 3D/runtime/registry guidance. Registry search returned relevant `filmed-screen`, `text-match-cut`, `rack-focus` and procedural 3D entries. The existing attributed match-cut primitive remains available. The new proof's geometry and choreography are original; no unreviewed registry block or skill bundle was executed. BRAG research/creative direction is handled separately by the root workflow.

The useful pattern is explicit frame-addressed drawing through `hf-seek` and a paused timeline. Simulations must be analytical or precomputed. Lights/materials and geometry are allocated once; frames only change transforms. No wall-clock loop, timers, network media or live physics is introduced.

## Measured isolated proof

`output/next-lab/` contains an eight-second **silent rendering study**, not the next delivered film. An original YES button triggers a curved domino chain, clock hand and reversal. All objects are built from geometry, including the drawn text texture. No image or video model was used.

The local npm archive's SHA512 integrity was checked before selecting two module files and the MIT notice. `THREE_PROVENANCE.json` records their SHA256 hashes. `BENCHMARK.json` records actual Chrome results at 1080×1920 with confirmed **SwiftShader software rendering**:

- 30 sampled draws: median 0.8 ms, 95th percentile 1.6 ms; each sample calls `gl.finish()`. These are render-call timings, excluding screenshots, video encoding and pipeline startup.
- Browser/page startup 1.72 seconds; sampled visible scene 5,476 triangles and 27 draw calls.
- No external requests and no browser errors.
- Frame 60 produced identical screenshot bytes after seeking 0 → 60 → 120 → 180 → 239 → 60.
- Actual PNGs were inspected. This proves frame addressability and rendering cost, not final art direction. The prototype has intentionally close crops and temporary copy; it has not been exported as a complete video.

## Next film integration

**The Yes Machine** now implements a 26.3-second, 13-shot film in one original mechanical world: press, domino chain, money, time, unused goods, brake, three question gates and a deliberate two-button choice. Camera scale and composition change with the discovery. Typography supports the consequence; it is not the only moving subject. Its [authored project](../videos/biznex-the-yes-machine/README.md) and [production recipe](NEXT_STORY_PIPELINE.md) explain the full workflow.

The isolated [builder](../scripts/build_procedural_short.mjs) consumes the measured edit, `DIRECTION.json`, original `assets/world.json` and verified audio mix. It writes existing verifier-compatible composition and build receipt names, and hashes every local JS module, font, world input and vendor. Its [pure state function](../scripts/lib/procedural_story_state.mjs) is covered by six tests for full-frame camera validity, backward seeking, rounded frame boundaries, spoken domino onset, pause freezing, a settled ending and invalid input rejection. A shared procedural world honestly uses one asset specification; asset counts are not inflated by copying filenames. Declared action and camera diversity still require review of the actual decoded film.

The [sound recipe](../scripts/synthesize_yes_machine_sound.py) creates original stereo score and mechanical transients from measured spoken anchors, with a complete hush at the pause and reduced final music. It does not download copyrighted recordings or alter the canonical voice. Local Three.js provenance records the exact MIT-licensed module bytes; Montserrat and existing GSAP notices remain with their assets.

Twenty-five actual HyperFrames snapshots were reviewed after framing corrections. The revised goods accumulate visibly, the dominoes fall progressively, the brake stops the machine, and both final choices remain readable from 23.2 seconds onward. HyperFrames check passed with zero errors, 14 of 14 measured text-contrast checks and 211 craft samples. Four short, speech-timed caption reading advisories and software WebGL readback performance warnings remain recorded. These preview checks establish neither a final export nor listening approval; the production recipe records actual encoded-media verification separately.

Keep generation, editing and rendering receipts separate. Report time spent per stage, preserve prepared voice/media, resume only unchanged inputs, and recheck first/next frames at every cut. Any next-film export still needs real video/audio decoding, readable caption checks, listening review, provenance and clear fictional/AI disclosure. No tool choice establishes audience reach.
