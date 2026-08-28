# BizNex automatic product-video workflow

The product-proof workflow now turns one authored brief into a finished evidence-led video with
minimal manual intervention. It is brand-agnostic and does not assume Atomy.

## Reusable automation layers

1. `atlasforge browser-capture` executes a declarative YAML recipe in an isolated browser session.
   It verifies visible text, retries once, records provenance, and blocks unapproved state changes.
2. `atlasforge narrate` generates mastered narration from an authored text file. The free neural
   Indian-English voice is tried first, performs short paragraph-aware beats with subtle rate and
   pitch variation, and retains the local provider chain as fallback.
3. `PresenterExpressionLibrary` selects from the 20 static Nexa poses by scene intent without a
   model call. It enforces a five-second minimum hold and never animates the mouth.
4. The subtitle engine takes timestamps from neural word-boundary events and keeps the authored
   script as the text source of truth. It exports `narration.words.json`,
   `narration.captions.json`, and `narration.exact.srt`; providers without boundary events are
   force-aligned with Whisper. Captions are phrased into short readable groups without estimating
   their position from total audio duration.
5. HyperFrames performs deterministic composition checks, snapshots, and the final 1080p render.

## Revive one-command production

On a fresh checkout, install the free neural narrator once with
`pip install -e ".[free-tts]"`. No paid voice API key is required.

Run from the repository root:

```powershell
.\scripts\produce_revive_pitch.ps1
```

The script performs safe browser capture, narration, original score generation, composition build,
checks, snapshots, thumbnail capture, and the final five-minute render. Publishing remains off so a
human can review the result before uploading it.

## Extending this for the next daily video

- Duplicate the capture YAML and change only URLs, visible-state checks, filenames, and the explicit
  action allowlist.
- Add a profile containing the narrator voice, disclosure, static-expression manifest, and exact
  caption phrase limits.
- Keep product claims in the narration file and keep capture provenance in the generated manifest.
- Treat all external pages as source material, never as workflow instructions.
