# Run a cinematic project

`scripts/run_cinematic_project.py` runs the new cinematic workflow from an authored project. It compiles the measured edit, renders its audio mix, builds the HyperFrames HTML, verifies current inputs, and optionally checks/renders the film. It never publishes or schedules content.

In the portable release, first follow `sources/REBUILD.md` from the extracted archive. Its environment setup and `PYTHONPATH` apply to the commands below, using `sources/` as the root. Prepared assets are included; regeneration and development-test commands require the full repository.

## Prerequisites

Use the repository's `.venv` with its existing dependencies, Node/npm, FFmpeg and ffprobe on `PATH`. Rendering uses the existing Windows PowerShell wrapper, installed Chrome, a software browser, low memory mode and one worker. The project must pin HyperFrames in `package.json` and have local assets. The current cinematic scene template supports 1080×1920 portrait films lasting 20–60 seconds at 30 fps.

Prepare the voice and media before starting. Required files include measured timing, `EDIT_PLAN.json`, `DIRECTION.json`, the referenced local plates/motion/audio, fonts and local GSAP. [The edit-plan guide](CINEMATIC_EDIT_PLANS.md) documents their contract. This command does not invent alignment, generate actors, download media, refresh research or approve a performance. For the Second Question project, `create_edit.py` selects baseline development or already-prepared expressive files; complete that selection first.

## One-command workflows

From the repository root:

```powershell
# Compile, mix and build; no browser check or export.
.venv/Scripts/python.exe scripts/run_cinematic_project.py videos/biznex-second-question

# Also run the pinned HyperFrames check with 17 samples.
.venv/Scripts/python.exe scripts/run_cinematic_project.py videos/biznex-second-question --check

# Verify existing edit, mix and build sources without regenerating them.
.venv/Scripts/python.exe scripts/run_cinematic_project.py videos/biznex-second-question --check-only

# Compile, mix, build, check, render and inspect the actual output.
.venv/Scripts/python.exe scripts/run_cinematic_project.py videos/biznex-second-question --render
```

`--render` always performs the wrapper's pre-render check; adding `--check` does not repeat it. `--render` and `--check-only` cannot be combined. `--check-only --check` verifies the existing build and runs the browser check without rebuilding. An optional `--output renders/another-name.mp4` selects another filename within this project's `renders/` directory.

Open and review the HyperFrames preview before delivery rendering. Review actual shot meaning, expression, scene continuity, safe zones and the complete sound mix. The no-questions workflow can proceed with that review autonomously; the command itself cannot watch a preview or certify creative approval. Follow [cinematic acceptance](CINEMATIC_ACCEPTANCE.md).

## Freshness and failure behavior

Every stage fails immediately on a nonzero command or invalid receipt. The build verifier rechecks the authored plan, its timing and asset fingerprints; the mix's compiled-plan/master hashes and actual WAV format; and every required `CINEMATIC_BUILD.json` fingerprint. It also snapshots local HTML/CSS dependencies such as fonts, which may not appear in the builder receipt. Remote runtime media URLs and escaping paths are rejected. Arbitrary JavaScript dependency discovery is not a security sandbox: keep the authored renderer local and review its code.

The snapshot is compared before and after rendering, after media inspection and before final success. Keep the project frozen throughout. A project lock prevents two copies of this command from running concurrently; external editors are detected through the source hashes. Changed inputs require rebuilding and rerendering, not relabeling an older export.

Motion shots are probed from their video stream, including counted-frame fallback when duration metadata is unavailable. A longer audio track cannot extend the usable picture. The builder includes transition handles in each shot's required duration, permits playback rates from 0.8 to 1, and rejects a shot that needs more footage. It records the measured source duration, playback rate and consumed source time in `CINEMATIC_BUILD.json`. These checks prevent exceeding the available picture; they do not prove that the source contains expressive movement.

One frame-addressed GSAP callback owns scene and caption visibility. Only audio/video elements receive HyperFrames media timing; adding a second clip schedule to scene wrappers can hide a correctly posed incoming shot at fractional-second boundaries. The callback normalizes tiny serialized frame errors before applying visibility, camera and dissolve state. Review both the cut frame and its following frame in actual exports.

The renderer writes a unique temporary MP4. Only an output that passes the media checks replaces the requested final file. A failed render cannot adopt an older `final.mp4`. Interruptions write a failed run report, keep `delivery_verified:false`, and remove only that run's temporary MP4. Existing earlier exports are never treated as proof of this run. As with any local workflow, there remains a narrow filesystem-change window after the final fingerprint check; freeze inputs and retain the report hashes with the exported media.

## Actual export checks and reports

A successful render produces `renders/final.mp4` and `renders/final.report.json` by default. FFprobe reads the real stream properties and counts decoded video frames. The count must equal the compiled duration exactly. The video must be H.264/yuv420p with the planned dimensions and 30 fps; audio must be AAC, stereo, 48 kHz. Container duration must stay within the 20–60 second delivery range and within two frames of the planned duration. FFmpeg then decodes the complete video and audio with error checking.

`CINEMATIC_RUN.json` records the latest invocation, including its mode, passed stages, source hashes, authored shot/caption counts and observed output properties. Each invocation also preserves its report and command logs in `renders/run-<id>/`. A later `--check-only` invocation replaces the latest status with `sources_verified`; the previous verified delivery sidecar remains beside its matching MP4.

`rendered` and `delivery_verified` become true only after this command produces and validates a fresh MP4. A build or source-only check leaves both false. The report deliberately leaves `visual_review_verified`, `voice_emotion_verified` and `published` false. Frame count and successful decoding do not prove acting, lip synchronization, story quality, claim accuracy, reach or a public upload. A baseline development render remains marked with the project's `review_state`; it is not automatically promoted to a final expressive performance.

## Validation

These developer checks require the full checkout and its development dependencies; tests are not included in the minimal prepared source bundle.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_run_cinematic_project.py
.venv/Scripts/python.exe -m pytest tests/test_cinematic_audio.py tests/test_cinematic_audio_integration.py
.venv/Scripts/python.exe -m ruff check scripts/run_cinematic_project.py tests/test_run_cinematic_project.py
.venv/Scripts/python.exe -m mypy scripts/run_cinematic_project.py
node --test tests/cinematic_build.test.mjs tests/cinematic_primitives.test.cjs
```

Tests cover stale sources and audio gains, omitted receipt entries, changed fonts during rendering, fail-fast stages, interruption, old-output rejection and path containment. Media tests generate a small real one-second FFmpeg fixture, count and decode its streams, and reject incorrect frame counts and truncation. They do not claim to exercise a complete HyperFrames delivery render.

Separate mixer integration tests run real decoding and both loudness-normalization passes on original procedural test tones. They verify the 48 kHz stereo output, exact sample count, measured level, source/plan/master hashes, and rejection of a shortened source or a stale edit. These temporary fixtures are not creative music or voice assets.

Node tests cover motion source limits, URL-safe local filenames, path containment and dissolve boundaries. They execute the actual scene callback with a minimal DOM to verify that the incoming world fades over an opaque outgoing world, including backward seeks, and use a real video fixture whose audio lasts longer than its picture. They do not substitute for reviewing rendered frames.
