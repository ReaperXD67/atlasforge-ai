# AtlasForge AI architecture

## Design goals

- Exactly one resumable production run per editorial date.
- Intermediate artifacts survive provider or machine failures.
- External providers are replaceable behind narrow interfaces.
- A useful local result exists without cloud video generation.
- Expensive generation is selected by scene value and bounded by a daily cap.
- Policy failures stop upload.
- Secrets never enter manifests or logs.

## Layers

| Layer | Modules | Responsibility |
|---|---|---|
| Domain | `models.py`, `quality.py` | validated scripts, scenes, metadata, policy gates |
| Orchestration | `pipeline.py`, `scheduler.py`, `state.py` | checkpoints, locking, retries/fallback, one-run lifecycle |
| Providers | `providers/` | text, TTS, images, premium cloud video |
| Media | `media/` | deterministic music/SFX, subtitles, FFmpeg render/mix |
| Delivery | `publishing/youtube.py` | minimal-scope OAuth upload, thumbnail, optional captions |
| Operations | `doctor.py`, `dashboard.py`, CLI | preflight, visibility, human controls |

## State and idempotency

`output/runs.sqlite3` is the operational ledger. A run has a stable ID, publication date, manifest JSON, and per-stage status. `output/pipeline.lock` prevents concurrent pipelines on one machine. A partial run for the date is resumed by default. A published run is protected by a partial unique SQLite index.

Artifacts are written before the corresponding stage is marked complete. Model-shaped checkpoints are revalidated through Pydantic on resume. Media checkpoints are accepted only when the stage is complete and the expected file exists.

## Fallback semantics

Providers fail closed at their own boundary and fail over only within the same capability:

```text
script:    Gemini → OpenRouter → Ollama
narration: OpenAI → Gemini → Kokoro → Piper
images:    Pexels → locally generated editorial card
video:     local FFmpeg motion always; optional Veo → MiniMax for selected scenes
```

The system does not silently replace factual research with model memory. Trend, autocomplete, and Reddit results are explicitly treated as topic/audience signals, not evidence.

## Premium scene scheduling

Storyboard scenes receive a `premium_score` from hook position, product relevance, emotional weight, and motion complexity. The scheduler sorts by score, then enforces both:

- `premium_max_scenes_per_video`
- `premium_daily_budget_usd`

A failed or over-budget premium scene falls back to local motion from a licensed/source-recorded still. Cost entries are persisted in `manifest.json`.

## Extension examples

To add a text provider, implement `TextProvider.available()` and `generate_json()`, register it in `ScriptGenerator`, and add its name to `script.text_providers`.

To add a visual provider, implement `ImageProvider.generate(scene, output)`. The output must include or accompany a license/provenance record.

To add a video provider, implement `PremiumVideoProvider.generate(scene, output)` and expose a conservative `estimated_cost_usd`. Do not bypass the scheduler.

## Known constraints

- Fully automatic fact verification is not equivalent to human editorial review. The writer is instructed to minimize claims; `facts_to_verify` is retained for audit.
- YouTube monetization depends on originality and channel-level patterns, not only technical compliance. A high-volume templated slideshow can still be ineligible.
- Preview model IDs and prices change. They are configuration, not hard-coded invariants.
- Pexels images may include people or marks that make a particular use inappropriate even when API access is allowed.
- Consumer Google AI credits and Developer API billing are separate product contexts unless Google explicitly connects them for your account.
