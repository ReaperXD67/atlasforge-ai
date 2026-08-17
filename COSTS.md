# AtlasForge AI cost model

Provider prices and free tiers change. The values below are planning assumptions as of 7 August 2026; confirm the linked live pages before enabling paid features.

| Stage | Default path | Expected marginal cost |
|---|---|---:|
| Topic signals | Trends RSS, YouTube suggestions, Reddit | $0 |
| Script | Gemini eligible free tier, then OpenRouter | $0 to a few cents |
| Storyboard/metadata | deterministic local code | $0 |
| Narration | OpenAI or Gemini; local fallback | typically low; provider/token dependent |
| Images | Pexels or local card | $0 |
| Music/SFX | project-generated waveforms | $0 |
| Captions/edit/render | FFmpeg/NVENC | electricity only |
| Song analysis / Remotion preview | Librosa + Remotion Player | $0 |
| ElevenLabs narration | disabled optional premium voice | about $0.10/minute for Multilingual v2/v3 at current API pricing |
| Veo 3.1 Lite, 720p | disabled; max one 8s clip | about $0.40 at $0.05/s |
| MiniMax Hailuo | disabled cloud fallback | package/model dependent |
| YouTube upload | Data API OAuth | $0; quota applies |

Current Gemini pricing lists Veo 3.1 Standard at $0.40/second, Fast at $0.10/second for 720p, and Lite at $0.05/second for 720p: [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing). This is why the repository defaults to Lite, one clip, and a $0.50 hard cap.

The MiniMax package system uses model-dependent units and package pricing, so the configured `$0.30` estimate is deliberately conservative rather than an invoice promise. Review [MiniMax video pricing](https://platform.minimax.io/docs/guides/pricing-video) and update `minimax_estimated_usd_per_clip` for the plan actually purchased.

## Recommended modes

### Minimum recurring cost

- Gemini free-tier text, if available.
- Gemini free-tier TTS or local Kokoro/Piper.
- Pexels/local images.
- Premium scenes off.

### Best cost/quality for daily use

- Gemini or a low-cost OpenRouter model for script.
- One high-quality cloud TTS narration.
- Pexels plus local motion.
- Premium scenes off for normal days; manually configure one Veo Lite hero scene for important topics.

### Premium day

- Same pipeline, `premium_max_scenes_per_video: 1`.
- Never enable provider billing without a provider-side monthly budget and alert.

## Your stated resources

- The roughly $5 OpenRouter balance should be reserved for scripts, not video. One structured call per day stretches it far longer than multi-agent/script/storyboard/SEO calls.
- A Google AI subscription can include AI Studio and product credits, but Google says each product has its own usage limits. Confirm Developer API billing and Veo entitlement inside the exact Cloud project instead of assuming consumer credits pay API invoices.
- The RTX 4070 Laptop GPU is best used for NVENC, optional 7B quantized Ollama, local TTS, and perhaps image generation—not long-form local text-to-video.
