# Bosston / Pragon: AI-scene motion and skill upgrades

Reviewed 18 November 2026 for the user's request to retain the original generated
red-and-gold worlds, improve their editing/motion, and publish the project to GitHub.
Stock footage was a wrong creative substitution for that request. This revision's
motion work should preserve the photographic AI artwork rather than replace it with
unrelated live footage or low-detail procedural hero models.

## Concrete decision

Use the existing local HyperFrames/GSAP/WebGL clock with AI-estimated depth and
original image-space animation. Give shots a composed entrance, sustained camera
path and a motivated handoff. Compare rendered frames across the handoff; a new
skill installation or a moving camera value is not by itself evidence that the
film has stopped looking like a slideshow. Depth parallax is an animated-image
technique, not native generated video or recovered true scene geometry.

## Primary-source review

| Source and inspected revision | License / maintenance evidence | Decision |
| --- | --- | --- |
| [HyperFrames v0.9.65](https://github.com/heygen-com/hyperframes/tree/32ff8b332323cfcff29be3ede278fc7810b6f5a5), published 18 November 2026; main inspected at [`c6e3f30`](https://github.com/heygen-com/hyperframes/commit/c6e3f30bea553e3a32edd8ae939be69c57346a75) the same day | [Apache-2.0](https://github.com/heygen-com/hyperframes/blob/32ff8b332323cfcff29be3ede278fc7810b6f5a5/LICENSE). Current repo and releases are active. Current top-level skills include hyperframes, media-use, registry/CLI, figma, reverse, slideshow and style sampling. Older separate keyframe/animation domain paths no longer exist at current main. | **Retain the tested renderer and existing domain references.** Do not blindly install stale listing paths or replace the runtime while authoring. The local keyframe and animation skills already explain deterministic timeline/GLSL timing; no second framework is needed. |
| [Cut the Curve](https://github.com/ThaddeusHackz/THE-AI-VIDEO-EDITOR/tree/d2a6541566554a3323098f8b4a1c1cdf13d0eb44/skills/cut-the-curve), [Seam Craft](https://github.com/ThaddeusHackz/THE-AI-VIDEO-EDITOR/tree/d2a6541566554a3323098f8b4a1c1cdf13d0eb44/skills/seam-craft), and [Motion Doctrine](https://github.com/ThaddeusHackz/THE-AI-VIDEO-EDITOR/tree/d2a6541566554a3323098f8b4a1c1cdf13d0eb44/skills/motion-doctrine) at `d2a6541566554a3323098f8b4a1c1cdf13d0eb44` | [Apache-2.0](https://github.com/ThaddeusHackz/THE-AI-VIDEO-EDITOR/blob/d2a6541566554a3323098f8b4a1c1cdf13d0eb44/LICENSE), copyright notice retained. Repository not archived; latest inspected push 18 October 2026. Small instruction/example library; no model, service or extra rendering dependency. | **Install project-local and adapt relevant mechanics.** Match camera direction/velocity and zoom sign across cuts; use an opaque scene ground and short optical handoffs. Do not mechanically apply its motion-graphics defaults to every cinematic shot. |
| [Depth Anything V2 Small HF](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf/tree/5426e4f0f36572d16453bbda7a8389317b1bef99) and [canonical source](https://github.com/DepthAnything/Depth-Anything-V2/tree/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf) | Model card declares Apache-2.0 for **Small**. The canonical README distinguishes Small's Apache-2.0 weights from larger models under CC-BY-NC. Inspected source revision is dated 24 March 2026. Small is about 24.8M parameters / 99.2 MB. | **Suitable isolated trial.** Existing CPU PyTorch/Transformers can produce local depth without downloading a second video-generation runtime. Keep exact model revision, depth inputs/outputs and observed runtime. Base/Large weights are not silently substituted for this branded film. |
| [DepthFlow `4d002b4`](https://github.com/BrokenSource/DepthFlow/tree/4d002b49f0ee2172d38fac93dcbc50c487e12301), commit 13 November 2026; [package manifest](https://github.com/BrokenSource/DepthFlow/blob/4d002b49f0ee2172d38fac93dcbc50c487e12301/pyproject.toml) | Package declares AGPL-3.0 and version 1.0.1. Maintained image-to-depth-parallax project; adds ShaderFlow, PyTorch, TorchVision, Transformers and supporting packages. | **Defer dependency and code copying.** It confirms the route's practicality, but its separate renderer/dependency burden and copyleft integration require a deliberate choice. This project can write an original deterministic WebGL depth/displacement implementation over its current stack. No DepthFlow code was installed or copied. |
| HyperFrames [style-sampling](https://github.com/heygen-com/hyperframes/blob/32ff8b332323cfcff29be3ede278fc7810b6f5a5/skills/style-sampling/SKILL.md) and [reverse-any-video](https://github.com/heygen-com/hyperframes/blob/32ff8b332323cfcff29be3ede278fc7810b6f5a5/skills/reverse-any-video/SKILL.md) | Current maintained upstream guidance, Apache-2.0 repo. These routes involve account/Pro features or reconstructing another supplied video. | **Defer for this task.** Neither adds the required local AI-scene depth motion; pulling paid style kits or rebuilding unrelated reference footage does not resolve this brief. |

## Installed project skills

The official Codex `skill-installer/scripts/install-skill-from-github.py` installed
these three directories with `--ref d2a6541566554a3323098f8b4a1c1cdf13d0eb44` and
`--dest <repository>/.agents/skills`:

- [cut-the-curve](../../.agents/skills/cut-the-curve/SKILL.md): velocity-matched zoom,
  sideways handoffs, rack-focus swaps, and example GSAP mechanics.
- [seam-craft](../../.agents/skills/seam-craft/SKILL.md): opaque stage grounds and
  compositing correctness around seams.
- [motion-doctrine](../../.agents/skills/motion-doctrine/SKILL.md): motion-vector
  planning and concrete carriers between adjacent scenes.

All **seven upstream skill files** match their downloaded source SHA-256 values.
They were not modified. Each folder adds an unmodified publisher `LICENSE` and a
local `UPSTREAM.md`; no upstream root NOTICE existed at this revision. Installation
provenance and source hashes are frozen in the local
`output/bosston-ai-v3/skills/installed-skills.json`. The skills are automatically
available on the next turn; their files can be consulted directly now.

Both included `.mjs` scripts pass `node --check`. This is syntax validation only.
The optional upstream live seam gate starts a POSIX `sh` preview command and uses
platform-specific browser discovery, so it is **not claimed as a working Windows
live gate**. It also measures DOM carriers; shader/depth camera continuity needs
rendered-frame inspection. Do not run the upstream stamping command against the
current project without adapting its selectors and master composition identity.
User/project instructions remain higher priority than upstream gateway language.

## What to adapt in this film

1. Carry the outgoing camera direction into the next view. A growing push should
   continue growing after the swap, rather than immediately reversing into a pull.
2. Put scene changes inside motion, then let the new composition settle enough
   for its lyric to read. Use only a few motivated transition families across the
   film; every cut need not advertise a new effect.
3. Keep lyric glyphs sharp and stable while camera/atmosphere move. The prior cue
   clock and corrected **Bosston** spelling remain the source of truth.
4. Budget overscan for both the camera and depth displacement. The upstream
   230 px motion-graphics example does not fit a 1.13-scale full-bleed image: that
   scale provides only about 125 px of horizontal edge margin. Reduce travel or
   increase available image coverage, then inspect the first/last frames for holes.
5. Derive all depth, atmosphere, optical and camera state from absolute song time.
   Freeze all assets locally before export. Review cut-adjacent strips, a motion
   preview and decoded final frames; report measured results rather than assuming
   these new references guarantee cinematic quality.

No paid provider was called, no external account or security setting was changed,
and no Git operations were performed by this research/installation subtask. The
parent task owns implementation, main/project README updates, final render checks
and the requested GitHub commits/push.

## Measured implementation

The adopted Small model produced all **17** source-size depth maps in **22.585 seconds** on eight CPU threads; the 8-bit runtime maps total **1,922,944 bytes**. Every source/map pair passes SHA-256, dimension, orientation and nonconstant-range checks. The working helper uses the installed Depth Anything/DINOv2 image classes and strict checkpoint loading; it does not load unrelated optional text-model dependencies or change any security policy.

The original WebGL renderer uses absolute song time, a shared X/Z camera direction, overscan, restrained depth displacement and selected material-motion fields. An outgoing linear camera continues through the short wipe rather than freezing at its final pose. The film has **52 shots / 17 artworks / 71 unchanged vocal cue intervals**. Cuts, silk wipes and light leaks are the only transition families; the high-travel whip was excluded because it exceeded the available image margin.

The custom native-Chrome gate passed **35 selected seeks**, **17 loaded depth maps with no fallback**, no sampled shader/context error or effectively blank picture, and **three exact repeated-time canvas hashes**. A **14-second / 420-frame / 1080p30** actual-composition proof fully decodes. These checks supplement HyperFrames lint/runtime/layout/contrast checks and visual seam inspection; they do not validate every frame or imply native generated-video motion. The earlier upstream POSIX DOM gate was not used as evidence for the shader.
