# BRAG, applied to an actual film

The requested “barb” is interpreted as **BRAG**, the `latent-spaces/brag` repository linked in the brief. Version 0.5.0, commit `669ab9286aa28b6c3ee30e75f181ee74319d012a`, was inspected and installed into the local Codex skills directory. Its [MIT source](https://github.com/latent-spaces/brag/tree/669ab9286aa28b6c3ee30e75f181ee74319d012a) is pinned in [the skill lock](../config/skills/brag.lock.json); the reviewed instruction files have SHA256 hashes. Newly installed skills are discovered automatically on a subsequent Codex session. During this production pass the installed files were read directly.

BRAG supplies a useful discipline: inspect the actual source, answer nine concrete positioning questions, commit to a visual hook, storyboard causal moments, choose sound for visible action, check readable frames and deliver a usable poster and share caption. It is an authoring skill, **not** an image model or a magic video generator.

The concrete result is [The Yes Machine's plan](../videos/biznex-the-yes-machine/brag-plan.md) and [composition brief](../videos/biznex-the-yes-machine/composition-brief.md). The source of the hook is the story's physical YES button, not invented UI. Its continuous code-authored world uses a pinned local Three.js renderer with the existing HyperFrames/GSAP clock. The completed preceding film is not edited.

## Intentional adaptations

This commission is a narrated vertical fictional story rather than BRAG's default short website launch. The user's original voice identity, no-image-model constraint and complete emotional phrases take precedence over its Kokoro and 15–25 second defaults. The final duration follows measured speech. A strong real opening frame and an exported poster replace the suggested unrelated single-frame cover splice.

No BRAG music pack is added to the repository or silently assumed licensed. The film's score and mechanical Foley are original procedural synthesis. Third-party runtime files retain their own notices. The installation is optional: prepared projects render without an agent skill loader.

## Reuse without dependency collecting

- [Visual tools](NEXT_FILM_VISUAL_TOOLS.md): Three.js is adopted for geometry/materials; OGL, Theatre and a second animation framework are deferred for this project.
- [Voice performance](NEXT_VOICE_PASS.md): compare complete thoughts and native directions using the installed model; no new weights or paid service are needed for this pass.
- [Story pipeline](NEXT_STORY_PIPELINE.md): small declared local stages with hashed inputs and outputs, measured execution and fail-closed resume.

BRAG's marketing energy is useful. Claims still need evidence: a working rendered sample, a reproducible command, concrete measurements and clear limits. No tool choice proves viral reach, higher conversion or human-indistinguishable speech.
