# godd.ai - Klap / Opus Clip Alternative Backend Worker
# Dockerfile for Render / Railway / Cloud Deployment

FROM node:24-bookworm-slim AS node_runtime

# Generate playback verification tokens on demand, then exit before encoding.
FROM node:24-bookworm-slim AS token_provider
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch 2.0.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil
WORKDIR /opt/bgutil/server
RUN npm ci --no-audit --no-fund && npx tsc && npm prune --omit=dev

FROM python:3.11-slim-bookworm
COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=token_provider /opt/bgutil/server /opt/bgutil/server
COPY --from=token_provider /opt/bgutil/LICENSE /opt/bgutil/LICENSE
ENV YOUTUBE_PO_PROVIDER_HOME=/opt/bgutil/server

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system FFmpeg with codecs, ca-certificates, and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    fonts-dejavu-core \
    fonts-noto-core \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libjpeg62-turbo libgif7 librsvg2-2 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV HF_HOME=/opt/huggingface
WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV AI_VIDEO_VOICE_DIR=/opt/godd-ai/voices
RUN python -m piper.download_voices --download-dir "$AI_VIDEO_VOICE_DIR" en_US-amy-medium en_US-lessac-medium
RUN base=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1 \
    && curl -fLsS --retry 3 "$base/kokoro-v1.0.onnx" -o "$AI_VIDEO_VOICE_DIR/timed-kokoro-v1.0.onnx" \
    && curl -fLsS --retry 3 "$base/voices-v1.0.bin" -o "$AI_VIDEO_VOICE_DIR/timed-voices-v1.0.bin"
# Cache the free-hosting model during build instead of each cold start.
ARG WHISPER_MODEL=base
RUN python -c "import os; from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-' + os.environ.get('WHISPER_MODEL', 'base'))"

# Copy all application code
COPY . .

# Render dynamically sets PORT (defaults to 8080 if not set)
ENV PORT=8080
EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/healthz || exit 1

# Start server
CMD ["python", "server.py"]
