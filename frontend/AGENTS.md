# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Durable product direction

- Match the selected “Editorial Timeline Studio” reference: warm graphite surfaces, compact professional editing density, a chapter rail, cinematic preview, multitrack timeline, scene inspector, and restrained amber accent.
- This is a local-first production tool, not a generic SaaS dashboard. The primary action is “Generate film”; live provider and machine readiness must remain visible.
- Keep all Atomy content factual and compliance-safe. Avoid earnings promises, medical claims, fake endorsements, or hype copy.
- OpenRouter is the default script provider. Kokoro, Whisper, Pexels, FFmpeg, and NVENC are local/low-cost pipeline components whose states should reflect backend data rather than hard-coded success.
- Keep a distinct Remotion Lab for music-first faceless films. It should feel like a professional race-event director: uploaded master track, visible BPM/beat evidence, purposeful motorsport shot grammar, deterministic motion preview, and no implication that decorative preview graphics are the final footage.
