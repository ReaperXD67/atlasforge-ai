# 有你，兄弟同心

A personal Mandarin music film for **Hock Siew / 拿督斯里谢惠福**. The folder retains an older working name; Benz is a separate, unstarted future commission.

**Current status: V4 is exported, technically verified and ready for user/boss review.** The user and boss rejected V3, so V4 is an image-only rebuild. It uses 18 original environment artworks, one transparent bronze foreground prop and the supplied real photographs. Hock’s photographed face, body and clothing are unchanged; literal crops exclude companions’ faces. There is no generated human likeness, AI video or reused V3 footage. Client creative acceptance remains pending.

The concept, **同心成桥 / The Bridge We Build**, follows a cinnabar strand through paper landscapes, shelter, rivers and a monumental bridge, then returns to an authentic photograph and Mandarin dedication. The original 196.760-second recording and all forty frozen lyric cues drive 54 shots. [BRIEF.md](BRIEF.md), [SPEC.md](SPEC.md) and [V4-STORYBOARD.md](V4-STORYBOARD.md) describe the scope and story; [edit-plan-v4.json](edit-plan-v4.json) is the executable edit.

## Watch V4

Local outputs (media stays outside Git):

- `renders/v4/Hock-Siew-Image-Film-V4.mp4` — **1920×1080, 24fps, 430.00MB**, H.264 with 320kbps AAC.
- `renders/v4/Hock-Siew-Image-Film-V4-720p.mp4` — **1280×720, 114.21MB**, with the same encoded AAC stream.
- [DELIVERY-V4.json](DELIVERY-V4.json) records exact SHA256 hashes, dimensions, timing, verification and acceptance status.

Both files fully decoded. The master contains 4,723 frames (196.791667s) covering the unchanged 196.760s song. Audio correlation is above 0.99959, with zero-sample measured lag in eight checks. All nine exact render-to-encode picture comparisons passed. The complete encoded review sampled all 54 shots and name anchors; no new P0/P1 framing defect was observed. This is technical and sampled visual evidence, with client creative approval still pending.

## V4 workflow

Private photos/audio, generated artwork, depth maps, local font/vendor copies and rendered media remain ignored local files. Git contains editable code, prompts, provenance and review records. A fresh clone needs those local inputs before rebuilding. Artwork is natively 1672×941 and composed for 1920×1080 delivery; 1080p output is not a claim of native 1080p artwork.

The isolated [renderer guide](v4-renderer/README.md) documents its plan contract and controls. It pins HyperFrames **0.9.72**, reuses reviewed Three.js 0.187.0/GSAP 3.14.2, and narrowly adapts gre’s MIT luma-wipe shader. [Upstream decisions](research/v4/upstream.md) explain licenses, maintenance and why additional rendering frameworks were not installed.

Run from the repository root, using the existing project environment and local media/model/font cache. [requirements-v4.txt](requirements-v4.txt) records the observed Python package versions; clean installation was not separately tested. [Skill/runtime update](research/v4/skills-update.md) records the reviewed refresh:

```powershell
.venv\Scripts\python.exe videos/dato-benz-brothers-united/generate_depth_v4.py
.venv\Scripts\python.exe videos/dato-benz-brothers-united/author_edit_v4.py
node videos/dato-benz-brothers-united/v4-renderer/build.mjs --plan videos/dato-benz-brothers-united/edit-plan-v4.json
.venv\Scripts\python.exe videos/dato-benz-brothers-united/verify_film_v4.py --preflight
Push-Location videos/dato-benz-brothers-united/v4-renderer
node smoke.mjs
npm run preview
powershell -NoProfile -ExecutionPolicy Bypass -File render.ps1 -Output ../renders/v4/Hock-Siew-Image-Film-V4-picture.mp4 -Quality delivery
Pop-Location
.venv\Scripts\python.exe videos/dato-benz-brothers-united/finalize_film_v4.py --share
.venv\Scripts\python.exe videos/dato-benz-brothers-united/verify_film_v4.py --file videos/dato-benz-brothers-united/renders/v4/Hock-Siew-Image-Film-V4.mp4 --contact-sheets
.venv\Scripts\python.exe videos/dato-benz-brothers-united/audit_delivery_v4.py
```

Source/build preflight, depth preparation, composition checks, 110 full-plan snapshots, 36 revised-shot snapshots, final title recheck, full export, finalization and encoded verification passed. The actual 0.9.72 hardware-GPU render took 6m49.8s. A 394-frame, 2fps encoded movement audit found no unintended freeze before the deliberate closing hold. The current official check retained one DOM-density warning and twenty DOM-only stillness warnings because camera motion draws inside WebGL; the encoded-pixel audit and sampled review cover that limitation. The finalizer preserves the rendered picture bitstream and encodes the canonical WAV directly to 320kbps AAC; the optional 720p copy shares that AAC stream.

## Evidence and limits

- [VISUAL-REVIEW-V4.md](VISUAL-REVIEW-V4.md): independent review of all 54 shots, five concrete framing/edit findings and targeted fixes. Sampled frames establish what was observed, not continuous playback quality or boss acceptance.
- [art-direction-v4.json](art-direction-v4.json), [artwork-v4.json](artwork-v4.json), [worker A](art-v4-worker-a.json) and [worker B](art-v4-worker-b.json): authored prompt set, exact worker prompts, realized artwork hashes and native dimensions. All 19 calls used built-in image generation; no Hock photograph was sent to it.
- [depth-provenance-v4.json](depth-provenance-v4.json): all 18 offline artwork-only maps, pinned Apache-2.0 Small-model weights, source hashes and 28.895 seconds of inference. Real photographs never enter the depth model.
- [YouTube references](research/v4/youtube-references.md): original creator sources and explicitly sampled frames, with observed ideas separated from documented methods. No creator media was reused.
- [Canonical audio analysis](research/v4/canonical-analyzer-generic.md): recovered with process-local generic CPU compilation; the exact song/cue clock stays unchanged and no unverified BPM is adopted.
- [CLIENT-STATUS.json](CLIENT-STATUS.json): current production and acceptance state.

V4 made **zero Runway generation calls, zero new private-photo uploads and no plan upgrade/top-up**. Built-in image generation uses the host app’s own allowance; it is not represented as a free external service. The last verified Runway balance belongs to V3’s archived ledger.

## Previous versions

V1–V3 and the model comparison remain archived. V3’s technical export passed but its creative result was rejected; technical passes are not likeness or audience approval. See [V3 direction](V3-DIRECTION.md), [V3 delivery](DELIVERY-V3.json), [V3 sampled review](VISUAL-REVIEW-V3.md), [pilot review](PILOT-REVIEW.md) and [realism research](REALISM-RESEARCH.md). Their local media stays under the existing versioned assets/renders directories. No previous master was overwritten.
