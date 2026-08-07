# Fresh Windows laptop → unattended daily pipeline

This guide starts from a clean Windows 11 laptop and ends with a tested, scheduled pipeline. Do the credential and channel setup once; no manual editing is required after that, although you should review early runs and periodically audit facts, audience response, and policy compliance.

## 1. Hardware and disk

Recommended for the stated laptop:

| Item | Required | Recommended for this project |
|---|---:|---:|
| RAM | 16 GB | 16–32 GB |
| VRAM | 0 GB for cloud/local FFmpeg path | RTX 4070 Laptop 8 GB |
| Free disk | 20 GB | 60 GB for retained intermediates |
| GPU driver | recent NVIDIA Studio/Game Ready | 570+ or the newest stable driver |
| Python | 3.11 or 3.12 | 3.11 x64 |
| FFmpeg | 7+ with ffprobe | current Windows build with NVENC |

CUDA Toolkit is **not required** for the default pipeline. FFmpeg NVENC uses the NVIDIA driver. Install a CUDA-enabled PyTorch wheel only if you enable Kokoro/Whisper or another local ML provider. PyTorch's official selector currently supports Windows Python 3.9–3.12 and gives the correct wheel for the CUDA runtime it ships: [PyTorch Windows installation](https://docs.pytorch.org/get-started/locally/). Do not independently install a random CUDA Toolkit version and assume PyTorch will use it.

Local long-form text-to-video is intentionally excluded: an 8 GB GPU cannot reliably produce a daily 6–8 minute cinematic video at practical speed and quality. Local inference here means TTS, optional LLMs, image generation adapters, and FFmpeg encoding.

## 2. Install base software

Open **PowerShell as Administrator** for these package installs:

```powershell
winget install --id Python.Python.3.11 --exact
winget install --id Git.Git --exact
winget install --id Gyan.FFmpeg --exact
winget install --id GitHub.cli --exact
winget install --id Nvidia.GeForceExperience --exact
```

If the NVIDIA package is not appropriate for the laptop manufacturer, install the latest NVIDIA driver from the OEM or NVIDIA instead. Close and reopen PowerShell, then verify:

```powershell
python --version
git --version
ffmpeg -version
ffprobe -version
nvidia-smi
```

FFmpeg publishes source and links to trusted Windows builds from its [official download page](https://ffmpeg.org/download.html).

Git LFS is optional because models and generated media are ignored. Install it only if you intentionally create a private model/asset repository:

```powershell
winget install --id GitHub.GitLFS --exact
git lfs install
```

GitHub explains the pointer model and plan limits in its [Git LFS documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).

## 3. Clone and install

```powershell
git clone https://github.com/ReaperXD67/daily-video-factory.git
Set-Location daily-video-factory
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
Copy-Item .env.example .env
```

The script creates `.venv`, installs the production package plus Google/YouTube integrations, and creates local `output`, `models`, and `secrets` directories.

## 4. Choose text generation

The configured priority is Gemini → OpenRouter → local Ollama. Only one is required.

### Option A — Gemini API (recommended first attempt)

Why: low cost, structured JSON, and your existing Google ecosystem. Optional: yes. Free: a limited API free tier may apply to eligible models/regions; production and Veo use may require billing.

1. Open [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Create an API key in a Google Cloud project.
3. Check the project's billing and model availability. A Google AI/Google One subscription provides product-specific benefits and should not be assumed to be unrestricted Gemini Developer API credit. Google states that products have separate usage limits: [Google AI Pro benefits](https://support.google.com/googleone/answer/14534406).
4. Paste only the value into `.env`:

```dotenv
GOOGLE_API_KEY=your_key_here
```

Configured model: `gemini-3.1-flash-lite`. Change `script.gemini_model` in `config/default.yaml` if the model is not available to your account.

### Option B — OpenRouter (preserves your ~$5 balance)

Why: one OpenAI-compatible endpoint with provider fallback. Optional: yes. Free: some models are free; the configured model is usage-priced. Expected text cost is usually cents per video, but always check the selected model's live price.

1. Open [OpenRouter Keys](https://openrouter.ai/settings/keys).
2. Create a key and set an account spending limit.
3. Paste it into `.env`:

```dotenv
OPENROUTER_API_KEY=your_key_here
```

The system makes one structured script call per run. OpenRouter documents its normalized chat response and structured-output format in the [API reference](https://openrouter.ai/docs/api_reference/overview).

### Option C — Ollama local

Why: no per-call cost and no cloud script data. Optional: yes. Free: yes. Quality and speed are lower on 8 GB VRAM.

```powershell
winget install --id Ollama.Ollama --exact
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Keep Ollama running. The defaults expect:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

The 7B Q4 model needs roughly 5–6 GB VRAM plus context overhead. Close GPU-heavy applications during generation.

## 5. Choose narration

The configured fallback order is OpenAI → Gemini → Kokoro → Piper. At least one must be available.

### OpenAI TTS

Why: consistent, natural narration and controllable delivery. Optional: yes. Free: no. Expected cost: generally low for a 7-minute narration; confirm current usage in the OpenAI dashboard because pricing is token-based.

1. Create a key at [OpenAI API keys](https://platform.openai.com/api-keys).
2. Add billing and set a project budget.
3. Paste it into `.env`:

```dotenv
OPENAI_API_KEY=your_key_here
```

The default is `gpt-4o-mini-tts` with voice `coral`. OpenAI requires a clear disclosure that the listener hears an AI-generated voice; the generated description includes it. See the [official TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech).

### Gemini TTS

Why: excellent fallback using the same Google API key. Optional: yes. The default `gemini-2.5-flash-preview-tts` has a documented free tier in some regions and paid token pricing; preview availability can change. See [Gemini speech generation](https://ai.google.dev/gemini-api/docs/speech-generation) and [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

No new variable is needed beyond `GOOGLE_API_KEY`.

### Kokoro local

Why: free offline narration with better quality than many lightweight local voices. Optional: yes. Disk: allow 1–3 GB for Python packages, model cache, and PyTorch. VRAM: typically 2–4 GB; CPU works more slowly.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[local-tts]"
```

Kokoro downloads its model files on first use into the Hugging Face cache. If you require an offline deployment, pre-run a short test while online and preserve that cache. `KOKORO_MODEL_PATH` is reserved for custom adapters; the packaged Kokoro provider currently uses its own cache.

### Piper local

Why: smallest, fastest, fully offline fallback. Optional: yes. Free: yes. Disk: usually under 200 MB per voice.

1. Download the current Piper Windows release and an English `.onnx` voice plus its `.onnx.json` config from the maintained [OHF-Voice Piper project](https://github.com/OHF-Voice/piper1-gpl).
2. Put them under `models/piper/`.
3. Set absolute paths:

```dotenv
PIPER_EXECUTABLE=C:\full\path\to\piper.exe
PIPER_MODEL_PATH=C:\full\path\to\en_US-voice-medium.onnx
```

## 6. Images and video

### Pexels images (recommended)

Why: free editorial/stock visual source with explicit attribution records saved per scene. Optional: yes; the local card provider always works. Cost: free subject to Pexels API terms.

1. Request a key at [Pexels API](https://www.pexels.com/api/).
2. Add it:

```dotenv
PEXELS_API_KEY=your_key_here
```

Always audit whether a specific photo is suitable for commercial use, contains recognizable people, trademarks, or misleading product context.

### Veo hero clips (optional, off by default)

Why: a single high-value intro/product/hero shot can materially improve perceived quality. Free: no Developer API free tier for Veo. Current 720p Veo 3.1 Lite pricing is listed as $0.05/second, so one 8-second clip is about $0.40. See [official pricing](https://ai.google.dev/gemini-api/docs/pricing) and [Veo API guide](https://ai.google.dev/gemini-api/docs/veo).

To enable exactly one budgeted clip:

```yaml
video:
  enable_premium_scenes: true
  premium_max_scenes_per_video: 1
  premium_daily_budget_usd: 0.50
  premium_providers: [veo, minimax]
```

Your Google Cloud project must have paid Gemini API access. Google Flow/Google One AI credits are product-specific and are not passed to this API by the repository.

### MiniMax Hailuo (optional cloud fallback)

Why: an alternative premium hero-clip provider. Free: no dependable production free tier. Obtain a pay-as-you-go key at the [MiniMax platform](https://platform.minimax.io/), then set:

```dotenv
MINIMAX_API_KEY=your_key_here
```

There is intentionally no `MINIMAX_MODEL_PATH`: current official video generation is an asynchronous cloud API, documented at [MiniMax video generation](https://platform.minimax.io/docs/guides/video-generation). The original “MiniMax H3 local” assumption is not implemented because it is not a supported local video-provider path.

## 7. YouTube upload and scheduling

Publishing is optional and disabled until this is complete.

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable **YouTube Data API v3**.
4. Configure the OAuth consent screen. For personal testing, add your Google account as a test user.
5. Create an OAuth client of type **Desktop app**.
6. Download the JSON file.
7. Save it as `secrets/youtube_client_secret.json`.
8. Run:

```powershell
.\.venv\Scripts\dailyvideo.exe youtube-auth
```

9. Approve the `youtube.upload` scope in the browser. The refresh token is saved as `secrets/youtube_token.json` and is ignored by Git.

YouTube requires user OAuth for normal channel uploads; service accounts are not supported for ordinary YouTube channels. See [YouTube OAuth](https://developers.google.com/youtube/v3/guides/authentication).

Important: uploads from unverified API projects created after July 2020 are restricted to private visibility until the project completes YouTube's audit. See [`videos.insert`](https://developers.google.com/youtube/v3/docs/videos/insert). Keep `upload_privacy: private` while testing.

After a successful no-upload run, enable publishing:

```yaml
publishing:
  enabled: true
schedule:
  upload_privacy: private
  publish_hour: 18
```

The API body includes `status.containsSyntheticMedia: true`, supported by the current [video resource](https://developers.google.com/youtube/v3/docs/videos). Burned captions are always present; uploading a selectable SRT track is optional.

## 8. Configure the channel

Edit `config/default.yaml`:

- `channel.region`: trends region, such as `IN` or `US`.
- `channel.timezone`: use an IANA timezone such as `Asia/Kolkata`.
- `research.seed_topics`: your durable editorial pillars.
- `schedule.hour`/`minute`: production start time.
- `schedule.publish_hour`: target scheduled publication time.
- `script.*_model`: provider model IDs available to your account.
- `video.premium_daily_budget_usd`: hard cap for generated clips.

Do not put secrets in YAML. Every secret belongs in `.env` or `secrets/`.

## 9. First validation

```powershell
.\.venv\Scripts\dailyvideo.exe doctor
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\dailyvideo.exe run --topic "A realistic framework for evaluating side hustles" --no-upload
```

Inspect:

```text
output/<run>/final/video.mp4
output/<run>/thumbnails/thumbnail.jpg
output/<run>/metadata/quality_report.json
output/<run/manifest.json
```

The first production-quality 7-minute render may take 15–45 minutes depending on stock downloads, TTS, scene count, and encoder. A local Ollama or Kokoro run may take longer.

## 10. Dashboard and unattended schedule

Test the dashboard:

```powershell
.\.venv\Scripts\dailyvideo.exe dashboard
```

Open `http://127.0.0.1:8741`.

Register a Windows scheduled task from an Administrator PowerShell:

```powershell
.\scripts\register_task.ps1 -At "07:00"
```

The task uses the repository's virtual environment and runs with the current user's credentials. The SQLite lock prevents overlapping instances. Keep the laptop awake, connected, and plugged in at run time. In Windows Power Options, allow scheduled tasks to wake the computer if required.

## 11. Full environment-variable reference

| Variable | Required when | Where to obtain / meaning |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini text/TTS or Veo | Google AI Studio API keys |
| `OPENROUTER_API_KEY` | OpenRouter text | OpenRouter account keys |
| `OPENAI_API_KEY` | OpenAI TTS | OpenAI Platform project key |
| `MINIMAX_API_KEY` | MiniMax video | MiniMax API platform |
| `PEXELS_API_KEY` | Pexels images | Pexels developer API |
| `OLLAMA_BASE_URL` | local Ollama | normally `http://127.0.0.1:11434` |
| `PIPER_EXECUTABLE` | local Piper | absolute path to `piper.exe` |
| `PIPER_MODEL_PATH` | local Piper | absolute path to voice `.onnx` |
| `KOKORO_MODEL_PATH` | custom future adapter | not needed by packaged provider |
| `YOUTUBE_CLIENT_SECRETS_FILE` | YouTube upload | downloaded Desktop OAuth JSON |
| `YOUTUBE_TOKEN_FILE` | after OAuth | generated by `youtube-auth` |
| `OUTPUT_DIRECTORY` | optional | defaults to `output` |
| `CONFIG_FILE` | optional | defaults to `config/default.yaml` |
| `FFMPEG_PATH`/`FFPROBE_PATH` | FFmpeg not on PATH | absolute executable paths |
| `LOG_LEVEL` | optional | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TZ` | optional tooling | use `Asia/Kolkata` |

Never paste an API key into source, GitHub Actions logs, issue text, or screenshots. Rotate any credential that has been exposed.

## 12. Expected recurring cost

With premium scenes disabled and Gemini's eligible free tier, cost can approach zero beyond electricity. A practical quality configuration with paid TTS and one low-cost LLM call is commonly well under $1/video. Enabling one 8-second Veo Lite clip adds about $0.40 at the current documented rate; standard Veo is much more expensive. See [COSTS.md](COSTS.md) and always confirm live provider pricing before enabling billing.

