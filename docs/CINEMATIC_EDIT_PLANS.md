# Voice-anchored cinematic edit plans

An opted-in project can compile an authored shot list against measured narration before its HyperFrames builder runs. This adds an editorial contract to the existing renderer: exact shot coverage, explicit visual changes, sound layers, transition handles and measured captions. It does not modify the six released pilot projects or their production fingerprints.

For the complete compile → mix → build → check/render → real-media verification command, use [the cinematic project workflow](CINEMATIC_PROJECT_WORKFLOW.md). The lower-level compiler commands below remain useful while authoring.

## Compile and verify

From the repository root, with the project environment installed:

For a prepared release bundle, use its `sources/REBUILD.md` environment setup and run compiler commands from `sources/`. The schema and authoring example are included; the pytest/Node developer tests below require a full repository checkout.

```powershell
.venv/Scripts/python.exe scripts/compile_edit_plan.py videos/<project>/EDIT_PLAN.json
.venv/Scripts/python.exe scripts/compile_edit_plan.py videos/<project>/EDIT_PLAN.json --check
.venv/Scripts/python.exe scripts/compile_edit_plan.py --schema config/editing/edit-plan.schema.json
.venv/Scripts/python.exe -m pytest tests/test_edit_plan.py
node --test tests/cinematic_primitives.test.cjs
```

The first command writes `EDIT_PLAN.compiled.json`, `EDIT_PLAN.compiled.js` and `EDIT_PLAN.audit.json` beside the authored plan. The JavaScript file exposes `window.ATLASFORGE_EDIT_PLAN`. The check command recomputes the plan and rejects changed inputs, missing assets, changed audio, edited payloads or a failing quality contract. Run it immediately before building/rendering an opted-in project. These commands do not render, upload or schedule anything.

Use [the JSON schema](../config/editing/edit-plan.schema.json) and [the authoring example](../config/editing/second-question.example.json). The example demonstrates the structure; its phrases and paths must be replaced with the actual approved narration and media before compilation. It is not a delivered video or a synthetic timing file.

The Python entry points are in `daily_video_factory.edit_plan`:

- `compile_edit_plan(EditPlan, timing_dict)` produces an in-memory frame plan.
- `audit_edit_plan(EditPlan, CompiledEditPlan)` checks that plan's authored contract.
- `compile_project_edit_plan(Path)` resolves local files, records SHA256 fingerprints, checks quality and writes artifacts.
- `validate_edit_plan_bundle(Path)` verifies the current inputs and all three saved artifacts without writing.

A failing quality check writes its audit but does not replace runnable payloads. An older payload may therefore still exist; it is unusable through `--check`. Files are replaced atomically one at a time; the bundle verifier also detects interrupted multi-file writes. Keep project inputs frozen during the final build/render. This verifier is not a filesystem lock or a signature from an independent reviewer.

## Authoring contract

The plan uses project-relative POSIX paths; absolute paths, parent traversal, network URLs and symlinks escaping the project are rejected. Every referenced shot asset and audio file must exist and is hashed. File hashing verifies identity, not media validity, sample rate, duration or content rights; those remain media-delivery checks.

`timing.json` needs `duration_seconds` and ordered `words` containing `text`, `start`, `end` in seconds. Other existing timing fields are accepted. Every word is one token, positive in duration, nonoverlapping and inside the audio clock. These are measured alignments supplied by the voice workflow, not inferred by this compiler.

The opening shot starts at `{"boundary":"start"}`. Later cuts normally use `{"phrase":"Fresh start doing what"}`. Matching ignores punctuation and case; an ambiguous phrase requires a one-based `occurrence`. `edge:"end"`, `offset_frames` and a zero-based `word_index` are available for deliberate breath/action offsets. Missing phrases fail instead of falling back to guessed timing. Each shot ends at the next shot start; the final shot ends at the measured voice duration rounded up to a frame. Sub-nanoframe timestamp noise is normalized before rounding.

Each shot declares its asset, visual kind, subject, location, layout, framing, camera, concrete action, expression and cut reason. `subject_motion` is `still`, `performance` or `action`; a photograph must stay `still` even when its camera moves. Calling an image “performance” does not make it animated. A scene builder must actually implement its declared camera and transition.

Primary frame ranges are half-open: `[start_frame,end_frame)`. They cover the film once without gaps or overlap. `display_start_frame`/`display_end_frame` add transition handles around a cut without shortening the approved voice. `cut` and `match_cut` use zero transition frames; `dissolve`, `whip` and `wipe` require positive frames. The renderer chooses the treatment; the compiler supplies ranges, not pixels.

Captions preserve every measured word. Groups stop at the word/character cap, sentence punctuation or a speech gap. Their per-word timing remains global to the film. A short hold never overlaps the following group. A word too long for the configured limit fails rather than being truncated. Renderers must still check actual font geometry, line wrapping and safe zones.

Audio uses one full-duration `voice` cue plus authored `music`, `ambience`, `foley` or `accent` cues. Each cue has a start anchor and either an end anchor or `duration_frames`. `source_start_frame` selects an offset in a non-voice source. Narration cannot be trimmed, faded, ducked or given gain keyframes. Gain envelopes use global frame numbers and **linear interpolation in decibels**; convert to amplitude with `10 ** (gain_db / 20)`. Voice ducking is optional per bed, with attack/release frames. Short speech gaps stay ducked to avoid pumping. The compiler does not mix sound or assume HyperFrames applies these envelopes automatically: the project's mixer must consume them or explicitly render an approved pre-mix.

Non-voice cues may add `gain_keyframes` for a deliberate change in the bed under a quiet line. Each `at` uses the same measured `VoiceAnchor` as shots. `offset_db` (−60 to +12 dB) is added to the cue's static `gain_db`, fade and duck values; it does not replace them. The following cue field lowers its existing mix level by another 6 dB over the six frames before a unique spoken phrase:

```json
"gain_keyframes": [
  {"at": {"boundary": "start"}, "offset_db": 0},
  {"at": {"phrase": "Before the next tap", "offset_frames": -6}, "offset_db": 0},
  {"at": {"phrase": "Before the next tap"}, "offset_db": -6},
  {"at": {"boundary": "end"}, "offset_db": -6}
]
```

This is a field inside an audio cue, not a complete JSON document. At 30 fps the ramp lasts 0.2 seconds. Resolved points must be strictly increasing and lie inside their cue, including its exact start/end; reversed points, quantized collisions, missing or ambiguous phrases fail compilation. Up to 200 points are allowed. A single point applies a constant offset, and the first/last offsets hold outside their authored interval. Omission or an empty list preserves the existing cue output. The compiler emits resolved points, their speech evidence and every fade/duck/ride breakpoint into the fingerprinted payload. Automated curves also include fractional-frame intersections with the −96 dB silence floor so interpolation preserves the authored ramp. These are sample-level envelope points, not fractional video cuts. Changing a point requires recompiling, remixing and rendering again; it never changes the narration source.

## Quality gates and limits

Defaults require 12 shots, four asset paths, three visual kinds, five layouts, three subjects, four framings, three non-locked camera modes, music and a motivated environmental/action layer. Primary shots must last 0.45–5.5 seconds; a declared still subject with a locked camera cannot exceed 4.5 seconds. The same layout cannot occupy more than 40% of the film or run for more than seven consecutive seconds. Typography is limited to 18%. Later cuts need nearby measured speech anchors. These defaults are editable policy, not a proven optimum for retention.

The audit rejects the old single-layout pattern even if its author splits it into many nominal shots. It checks declared metadata and asset identities; distinct filenames can still contain the same image, and a false label can still misdescribe a scene. Every audit explicitly keeps visual quality, semantic accuracy, rendered motion and audience-performance prediction **false**. Review the actual decoded film for story, acting, artifact continuity, caption geometry, sound and source accuracy using [cinematic acceptance](CINEMATIC_ACCEPTANCE.md). No audit score promises reach or virality.

## Reusable renderer primitives

`scripts/lib/cinematic_primitives.js` is a small local script with no DOM, network, timer or rendering dependency. Copy it into a new project's `assets/vendor/`, preserve its header and the accompanying [Apache-2.0 license](licenses/HYPERFRAMES-APACHE-2.0.txt), then load it before scene code. It exposes `window.AtlasForgeCinematic`; Node tests can also `require()` it.

```javascript
const pose = AtlasForgeCinematic.focusCameraAt(frame, {
  startFrame: shot.start_frame,
  endFrame: shot.end_frame - 1,
  anchorX: 68, anchorY: 36,
  startZoom: 1.02, endZoom: 1.18,
  driftX: 0.12, driftY: 0.08,
});
// The inner world must fill the viewport and use transform-origin: 50% 50%.
world.style.transform = `translate(${pose.xPercent}%, ${pose.yPercent}%) scale(${pose.scale})`;
```

The camera clamps pan to preserve viewport coverage, and finite drift returns to zero at its endpoints. `matchCutAt(frame,{cutFrame,halfDurationFrames:12,axis:"x",distancePercent:8})` returns a shared transform and two complementary opacities. It swaps the visible subject at the speed peak; the author must align the two subjects spatially. Apply opacity to inner children, never a HyperFrames `.clip`. `captionAtFrame(compiled,frame)` returns a group and its active global word index; silence gaps deliberately have no active word. All functions reproduce a state regardless of seek order. They do not register or play a timeline; the host's paused GSAP timeline supplies its frame.

## Research and adoption record

Primary sources inspected on **2026-11-06**. No replacement video framework was installed. These choices reuse the project's Python/Pydantic and pinned HyperFrames renderer rather than adding a second rendering stack.

| Upstream / inspected revision | Exact license and maintenance evidence | Decision and concrete adaptation |
| --- | --- | --- |
| [Remotion](https://github.com/remotion-dev/remotion), `cfe138e68d6621e70fca110f6f363e0516e55e7a` | [Remotion License](https://github.com/remotion-dev/remotion/blob/cfe138e68d6621e70fca110f6f363e0516e55e7a/LICENSE.md), a custom license with eligibility and company-license conditions; inspected commit dated 2026-11-06. | **Adapt concepts, defer runtime.** Explicit frame ranges and [transition timing](https://www.remotion.dev/docs/transitions/transitionseries) informed separate primary/display ranges. No Remotion code copied and no React/runtime dependency added. |
| [Motion Canvas](https://github.com/motion-canvas/motion-canvas), `7b91435c301d530351dcf5ebb91dd139c002e405` | [MIT](https://github.com/motion-canvas/motion-canvas/blob/7b91435c301d530351dcf5ebb91dd139c002e405/LICENSE); inspected current commit dated 2026-07-02. This is weaker recent maintenance evidence than the daily-active alternatives. | **Adapt named cues.** [Time events](https://motion-canvas.io/docs/time-events/) motivate literal speech anchors instead of manually copied delays. No generator/canvas runtime added. |
| [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO), `80c5ff30938e4adffe9c94f419b1055856cee9f5` | [Apache-2.0](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/80c5ff30938e4adffe9c94f419b1055856cee9f5/LICENSE.txt); inspected commit dated 2026-10-30. | **Adapt timing model, defer package/export.** [Architecture](https://opentimelineio.readthedocs.io/en/latest/tutorials/architecture.html) informs rational frame clocks, layered media and exclusive end ranges. Native bindings/export adapters are unnecessary for this renderer. The JSON is not claimed to be an OTIO document. |
| [Auto-Editor](https://github.com/WyattBlue/auto-editor), `ddf5812dde4133d32a4e4a4b91b1b5a76d1960f8` | [Unlicense](https://github.com/WyattBlue/auto-editor/blob/ddf5812dde4133d32a4e4a4b91b1b5a76d1960f8/LICENSE); inspected commit dated 2026-11-06. Binary dependencies may carry other licenses. Current source is principally Nim. | **Adapt handles, defer automatic cutting.** Source margins and transition handles are useful; deleting low-volume pauses from expressive, approved narration would change the performance. No binary or dependency installed. |
| [BRAG](https://github.com/latent-spaces/brag), `669ab9286aa28b6c3ee30e75f181ee74319d012a` / 0.5.0 | [MIT](https://github.com/latent-spaces/brag/blob/669ab9286aa28b6c3ee30e75f181ee74319d012a/LICENSE); release commit dated 2026-10-23. Bundled music has separate CC BY 4.0 terms. | **Adapt authored handoff.** [Skill source](https://github.com/latent-spaces/brag/blob/669ab9286aa28b6c3ee30e75f181ee74319d012a/skills/brag/SKILL.md) reinforces concrete beats and sound choices. Site-launch templates do not supply character acting. No bundled media or executable instructions imported. |
| [HyperFrames](https://github.com/heygen-com/hyperframes), CLI 0.9.19; registry source `de2d21a8abd786ef3d63a6818eda3cad844ea46f` | [Apache-2.0](https://github.com/heygen-com/hyperframes/blob/de2d21a8abd786ef3d63a6818eda3cad844ea46f/LICENSE), copyright 2026 HeyGen, Inc.; inspected current commit dated 2026-11-06. No root NOTICE file present at that revision. | **Adapt actual code.** [ui-focus-zoom](https://github.com/heygen-com/hyperframes/blob/de2d21a8abd786ef3d63a6818eda3cad844ea46f/registry/components/ui-focus-zoom/ui-focus-zoom.html) supplied the camera-clamp pattern; [text-match-cut](https://github.com/heygen-com/hyperframes/blob/de2d21a8abd786ef3d63a6818eda3cad844ea46f/registry/components/text-match-cut/text-match-cut.html) supplied shared-curve timing. The new primitive removes skeleton UI, callbacks and CDN loads, adds strict inputs and measured-caption lookup, and preserves attribution/license. |

The measurable benefits verified by tests are deterministic frame coverage, full narration preservation, explicit rejection of ambiguous/invalid timing, old-pattern rejection, asset-change detection, bounded camera coverage and seek-order independence. Better storytelling, more expressive acting and audience response must be assessed on rendered films and real observations; upstream popularity does not establish those outcomes.
