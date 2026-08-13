# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS base

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

RUN python -m venv /opt/venv \
    && pip install --upgrade pip setuptools wheel

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install "."

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

FROM base AS local-ai
USER root
RUN pip install ".[local-tts,transcription]"
USER atlasforge
