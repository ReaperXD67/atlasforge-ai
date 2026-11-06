# Package the cinematic delivery

`scripts/package_cinematic_delivery.py` exports the prepared **Second Question** project after
its final render is verified. It does not render, generate voices, enqueue, upload or publish.
The old six-pilot packager is separate and unchanged.

From the repository root:

The packaging command requires a full repository checkout. The minimal source ZIP supplies the prepared renderer and its own `sources/REBUILD.md`; it does not include this packager or the development tests.

```powershell
# Readiness only; a missing or stale final returns not_ready and a nonzero exit.
.venv/Scripts/python.exe scripts/package_cinematic_delivery.py --check --project-source

# Export the film and its portable prepared source project together.
.venv/Scripts/python.exe scripts/package_cinematic_delivery.py --project-source
```

Omit `--project-source` for only the viewing/publication package. Choose the option before
exporting: the helper refuses to overwrite an existing directory or ZIP. Preserve or move an
earlier export before creating another.

Output is `output/deliveries/biznex-second-question/`, the matching `.zip`, and a `.zip.sha256`
sidecar. Media and exports remain ignored by Git. Successful export is reported only after
the files are installed; documentation and source code do not assert that a ZIP already exists.

## Checks and contents

The helper reads `renders/final.report.json`, requires its successful render/check/media stages,
revalidates the current edit/mix/build sources, and compares the full source snapshot. It then
checks the MP4 hash, probes and completely decodes its video/audio through the cinematic runner.
A later source-only invocation may replace `CINEMATIC_RUN.json`; the matching final sidecar is
the authoritative delivery record.

Canonical `timing.json` must select the expressive voice. The complete `narration.srt` must
contain the approved script's words and match the selected timing's caption boundaries. The
canonical narration WAV's hash must match the voice actually used in `AUDIO_MIX.json`. A
development SRT is never substituted just because it exists.

The consumer package contains:

- `final.mp4`, decoded-frame `thumbnail.jpg`, complete `captions.srt`, transcript and `UPLOAD_COPY.md`.
- Music/foley/visual/motion/voice provenance and the final render report.
- The available neutral-versus-directed voice audition, its order JSON and evidence. This is
  an audition, not an alternate soundtrack for the film.
- A README with the Scott Buckley CC BY credit, fictional/AI disclosure, `DELIVERY_MANIFEST.json`
  and `SHA256SUMS.txt` for every other exported file.

`--project-source` adds `sources/`: the exact runtime project and prepared assets, original
plates, motion clips, canonical narration/master, authorized synthetic voice-reference WAV,
licenses, authoring files and minimal compiler/mixer/builder/render support. It excludes the
duplicate music download, baseline narration, caches, snapshots, account files, virtual
environments and model weights. The archive's `sources/REBUILD.md` supplies dependency and
Windows rebuild commands. Rendering uses the prepared assets; voice regeneration remains a
separate model/runtime setup. Encoder differences can produce different MP4 bytes on another
machine, even with the same authored inputs.

The source bundle includes the project's decoded poster and the edit-plan schema/example, so its project README and core rebuild-guide links work locally. Optional full-repository generation references link to the online repository rather than pulling unrelated projects into the archive.

The packager shares the runner lock and rechecks copied-input hashes before installing an
export. It refuses escaping paths, credential-like content and private absolute paths in
fingerprinted runtime files. Private machine paths in non-runtime provenance copies are
redacted, with source and exported hashes recorded; originals stay untouched. Technical
verification is distinct from full-film listening, aesthetic review and emotional fidelity.
