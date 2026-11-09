# Run the next authored story

The new story runner executes an explicit local production recipe. It connects prepared voice, measured scene planning, mixing, a project-specific builder, rendering, encoded-speech verification, decoded review sheets and packaging. It preserves the completed *Second Question* film and its source contracts. It adds no image model, workflow service or orchestration dependency.

```powershell
# Inspect the declared recipe without executing commands.
.venv/Scripts/python.exe scripts/run_story_pipeline.py videos/biznex-the-yes-machine

# Run every declared stage, then verify the delivered bytes and QA evidence.
.venv/Scripts/python.exe scripts/run_story_pipeline.py videos/biznex-the-yes-machine --execute

# Reuse only stages with matching inputs, implementation and output hashes.
.venv/Scripts/python.exe scripts/run_story_pipeline.py videos/biznex-the-yes-machine --execute --resume
```

The [concrete ten-stage recipe](../videos/biznex-the-yes-machine/PIPELINE.json) is delivered with the new film. A missing recipe, script or dependency fails; these commands do not invent a story or silently substitute assets. Voice generation needs the existing pinned local runtime and cached weights. A prepared voice stage may verify its earlier generation receipt instead of loading the model again; its synthesis runtime and the runner's verification runtime remain distinct evidence.

The verified 26.3-second, 789-frame production run took **365.424 seconds** on this Windows machine with one software-rendering browser worker. Rendering/check/decode accounted for 326.019 seconds; the new prepared narration was hash-verified in 0.656 seconds rather than regenerated. Its earlier measured model session took 78.759 seconds, excluding preflight/imports and CPU ASR. All ten stages passed, including actual encoded-audio transcription and portable packaging. See the [per-stage measurements](../videos/biznex-the-yes-machine/PRODUCTION_METRICS.json) and [delivered project](../videos/biznex-the-yes-machine/README.md).

## Recipe and stage contract

The [Borrowed Countdown recipe](../videos/biznex-the-borrowed-countdown/PIPELINE.json)
adds a separate kinetic-desk scene family and speech-anchored original sound. On
9 November it completed nine stages through encoded-audio and decoded-frame QA in
393.526 seconds, using prepared narration: 23.9 seconds, 717 frames, thirteen shots.
All five encoded thoughts passed ASR; 78 unique decoded frames were sampled and
inspected. Packaging follows editorial review as a separate command:

```powershell
.venv/Scripts/python.exe scripts/package_story_delivery.py videos/biznex-the-borrowed-countdown
```

This is an authored recipe, not a general daily scene generator. Automatic BizNex
operation was paused by the owner on 9 November; run production only on request.

`PIPELINE.json` lives inside `videos/<project-id>/`. Its `project_id` must match that directory. `brief` defaults to `BRIEF.md` and remains immutable throughout the run. The following is a structural example, not a complete delivery recipe:

```json
{
  "schema_version": 1,
  "project_id": "example-story",
  "brief": "BRIEF.md",
  "stages": [{
    "id": "compile",
    "executor": "python",
    "entrypoint": "scripts/compile_edit_plan.py",
    "args": ["{project}/EDIT_PLAN.json"],
    "inputs": ["EDIT_PLAN.json", "timing.json"],
    "repo_inputs": [],
    "outputs": ["EDIT_PLAN.compiled.json", "EDIT_PLAN.compiled.js", "EDIT_PLAN.audit.json"]
  }]
}
```

Stages run in listed order. Each uses the current Python environment or local Node and a reviewed `scripts/*.py` or `scripts/*.mjs` entrypoint. Arguments are passed as an argv array, with `{project}` expanded to the selected directory; no shell parses them. Inputs and outputs are project-relative files. `repo_inputs` names additional repository-relative configuration or dependency files. Optional `output_trees`, such as `["qa/frames"]`, hash every regular file beneath a contained directory and reject symlinks. Adding, editing or deleting a review image therefore invalidates that stage's cache. Output producers and trees must have distinct stage ownership, later-produced inputs cannot be used early, and a stage cannot overwrite its own declared input. A stage can set a bounded `timeout_seconds`.

The runner is for trusted, reviewed project code, not an OS sandbox for untrusted scripts. It rejects private absolute paths, credential-like arguments, network URLs and escaping file references. Runtime credentials and environment dumps are never included in portable receipts. Subprocess logs stay under ignored `output/story-pipeline/<project-id>/<run-id>/`; errors shown by the runner remain generic. No stage in the supplied workflow publishes, schedules or opens accounts.

## Cache, failure and timing evidence

Before a stage runs, its recipe, authored brief, declared input bytes, explicit repository inputs and local implementation files receive SHA256 fingerprints. The toolchain fingerprint includes Python and relevant package versions, Node/FFmpeg/ffprobe versions and executable hashes, and installed Windows Chrome executable/engine hashes. It is rechecked after the run. Local Python, JavaScript, templates and PowerShell files under `src/` and `scripts/` are included to cover transitive code changes. Freeze implementation code for the production run. This deliberately invalidates a cache when shared code or runtime changes, even if a particular stage might not use that change.

An existing target alone is never a cache hit. `--resume` requires a matching prior successful signature **and** current output hashes. Missing or edited outputs rerun the stage. Inputs are checked after execution, and every earlier input/output is checked after the complete sequence, so a later stage cannot silently rewrite an upstream artifact. A failed command, missing declared output, changed input or interruption writes a failed run receipt; an older MP4 cannot turn that invocation into success. Rendering itself uses a new temporary MP4 and the existing serial browser check/full media decode contract.

Every stage prints starting/completed/reused status and elapsed wall time. The unique report and `latest.json` distinguish actual work from reuse. `state.json` is an internal successful-stage cache. Generic recipes end as `stages_verified`; recipes that produce `STORY_PACKAGE.json` additionally recheck current render sources, captions, audio/frame QA, final MP4 and archive hashes before receiving `verified_technical_delivery`. This still does not certify creative quality or audience response.

## Delivery tools and review boundary

The reusable commands accept a prepared project directory:

- `render_story_project.py`: runs the existing 17-sample browser gate, fresh render, decoded-frame count, H.264/AAC format checks and complete video/audio decode. It writes `renders/final.mp4` and its matching report.
- `verify_story_audio.py`: decodes that MP4, verifies mix/master/narration identity and alignment, measures loudness/peak/clipping, and transcribes every measured speech window with cached CPU `small.en`. Speech windows must cover the complete approved transcript. Any mismatch returns nonzero; it does not silently rewrite captions or claim emotional fidelity.
- `review_story_frames.py`: decodes all shot midpoints, both sides of every cut, transition handles, action samples and bookends. It writes image hashes and contact sheets under `qa/frames/`. The receipt confirms sample extraction and coverage, not visual approval. Inspect these sheets and play the actual film before accepting it.
- `package_story_delivery.py`: requires current source/media/caption checks plus passed encoded-audio and frame-coverage evidence. It writes `renders/delivery.zip` and `STORY_PACKAGE.json`. The default archive includes the MP4, exact SRT, upload copy, credits, provenance, review sheets and prepared source tree. `--consumer-only` omits source files. No model weights, environment, credential files or source downloads are bundled. Exact runtime sources containing private paths are rejected; private paths in non-runtime metadata are redacted only in the exported copy.

The prepared source bundle contains local code, runtime assets and pinned small rebuild dependencies. Its `sources/REBUILD.md` starts with a source-only check and can render the prepared composition without regenerating voice. Check all `SHA256SUMS.txt` entries after download. A source-only check is not a fresh render or a clean-machine installation test.

## What remains authored

Story choice, hook, causality, factual sources, licensed asset choices, voice direction and each shot's meaning remain explicit reviewed inputs. Scripts can turn those inputs into measured artifacts and fail closed on technical mistakes. They cannot prove that a hook is compelling, a synthetic performance is natural, or a film will retain viewers. The next story's actual exported film and audience observations supply that evidence.

## Focused upstream decisions

Primary documentation, repository licenses/commits and package metadata were inspected on 2026-11-06. No upstream code or runtime was installed for the orchestrator.

| Candidate | Inspected maintenance/license | Decision |
| --- | --- | --- |
| [DVC running pipelines](https://doc.dvc.org/user-guide/pipelines/running-pipelines) | [commit b59add99](https://github.com/treeverse/dvc/commit/b59add99ee667f2b352cc1be337619f965fe3fea), dated 6 November; [Apache-2.0](https://github.com/treeverse/dvc/blob/b59add99ee667f2b352cc1be337619f965fe3fea/LICENSE). [3.67.1 package metadata](https://pypi.org/pypi/dvc/3.67.1/json) lists 42 base requirements. | Adapt explicit inputs/outputs and content-based reuse; defer the package because remote artifact management and a larger dependency graph do not solve this local sequence. |
| [doit dependency checks](https://pydoit.org/dependencies.html) | [commit 0d8135a2](https://github.com/pydoit/doit/commit/0d8135a20e754db5472c8852d95f0f7cb720a948), dated 21 September; [MIT](https://github.com/pydoit/doit/blob/0d8135a20e754db5472c8852d95f0f7cb720a948/LICENSE). [0.37.0 metadata](https://pypi.org/pypi/doit/0.37.0/json) has no mandatory dependencies for current Python. | Adapt missing-target and changed-configuration invalidation. Defer the runtime: the repository already has its media gates, Pydantic and a process lock, and needs portable media evidence beyond task completion. |

The expected benefit is less repeated manual orchestration and no unnecessary rerender when exact inputs remain unchanged. Runtime improvements are reported from actual cold/reuse runs, not inferred from upstream popularity.
