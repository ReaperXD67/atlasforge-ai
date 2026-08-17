# syntax=docker/dockerfile:1.7
FROM node:22-bookworm-slim AS web-builder

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --prefer-offline --no-audit --no-fund
COPY frontend ./
RUN npm run build

FROM python:3.12-slim-bookworm AS python-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        espeak-ng \
        ffmpeg \
        fontconfig \
        fonts-dejavu-core \
        libsndfile1 \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip python -m venv /opt/venv \
    && pip install --upgrade pip setuptools wheel

WORKDIR /app

FROM python-runtime AS local-ai-runtime
RUN --mount=type=cache,target=/root/.cache/pip pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.13.0+cpu" \
    && pip install "kokoro>=0.9,<1" "soundfile>=0.12,<1" "faster-whisper>=1.1,<2" "transformers>=4.46,<6" \
    && python -m spacy download en_core_web_sm

FROM python-runtime AS base
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY --from=web-builder /web/dist/client ./src/daily_video_factory/web
RUN --mount=type=cache,target=/root/.cache/pip pip install "."

COPY config ./config
RUN useradd --create-home --uid 1000 atlasforge \
    && mkdir -p /app/output /app/models /app/secrets \
    && chown -R atlasforge:atlasforge /app

USER atlasforge
ENV CONFIG_FILE=/app/config/default.yaml \
    OUTPUT_DIRECTORY=/app/output \
    MODEL_DIRECTORY=/app/models \
    HF_HOME=/app/models/huggingface \
    XDG_CACHE_HOME=/app/models/cache

ENTRYPOINT ["tini", "--", "atlasforge"]
CMD ["doctor", "--config", "/app/config/default.yaml"]

FROM local-ai-runtime AS local-ai
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY --from=web-builder /web/dist/client ./src/daily_video_factory/web
RUN --mount=type=cache,target=/root/.cache/pip pip install "."

COPY config ./config
RUN useradd --create-home --uid 1000 atlasforge \
    && mkdir -p /app/output /app/models /app/secrets \
    && chown -R atlasforge:atlasforge /app

USER atlasforge
ENV CONFIG_FILE=/app/config/default.yaml \
    OUTPUT_DIRECTORY=/app/output \
    MODEL_DIRECTORY=/app/models \
    HF_HOME=/app/models/huggingface \
    XDG_CACHE_HOME=/app/models/cache

ENTRYPOINT ["tini", "--", "atlasforge"]
CMD ["doctor", "--config", "/app/config/default.yaml"]
