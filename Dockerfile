# godd.ai - Klap / Opus Clip Alternative Backend Worker
# Dockerfile for Render / Railway / Cloud Deployment

FROM node:24-bookworm-slim AS node_runtime

FROM python:3.11-slim-bookworm
COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system FFmpeg with codecs, ca-certificates, and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-noto-core \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV HF_HOME=/opt/huggingface
WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
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
