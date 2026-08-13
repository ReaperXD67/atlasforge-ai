# Local and Docker operation

AtlasForge has three container modes. All keep artifacts, source records, model caches, and
credentials on the local machine. Publishing and premium video generation remain disabled unless
explicitly enabled in configuration.

## 1. Lightweight CPU-safe runtime

This mode works without GPU passthrough and falls back to `libx264` when NVENC cannot encode a real
test frame. It expects a configured cloud narration provider; use mode 3 for the fully local path.

```powershell
docker compose build atlasforge
docker compose run --rm atlasforge doctor
docker compose run --rm atlasforge run --no-upload
```

## 2. Use the GPU for rendering

Docker Desktop must expose the NVIDIA GPU. The preflight reports the encoder selected after a real
one-frame encode, rather than only checking FFmpeg's encoder list. Caption timing falls back to
deterministic pacing unless faster-whisper is installed; mode 3 includes it.

```powershell
docker compose --profile gpu run --rm atlasforge-gpu doctor
docker compose --profile gpu run --rm atlasforge-gpu run --no-upload
```

## 3. Fully local scripting plus local media

The local profile runs the official Ollama image with NVIDIA passthrough. Download the configured
7B quantized writer once, then run the app against that service. The model is unloaded after each
request so the 8 GB GPU can be reused by caption alignment and rendering.

```powershell
docker compose --profile local-ai up -d ollama
docker compose --profile local-ai run --rm ollama-pull
docker compose --profile local-ai run --rm atlasforge-local doctor
docker compose --profile local-ai run --rm atlasforge-local run --no-upload
```

The `atlasforge-local` image is intentionally separate because the Kokoro/Whisper Torch layer is
several gigabytes; normal CPU/GPU image builds do not pay that cost. Its first run also downloads
local Kokoro and Whisper model assets into `models/`. Later runs reuse them. If RAM or VRAM is
constrained, set `subtitles.alignment: estimated` or use the CPU-safe service.

## Useful checks

```powershell
docker version
docker compose version
docker run --rm --gpus all nvidia/cuda:12.9.1-base-ubuntu24.04 nvidia-smi
docker compose --profile local-ai logs ollama
```

The `output`, `models`, and `secrets` directories are bind-mounted. API keys are injected from the
ignored `.env` file and are never copied into the image.
