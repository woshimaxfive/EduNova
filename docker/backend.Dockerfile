# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG DEBIAN_MIRROR=http://deb.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1

WORKDIR /app

RUN sed -i \
      -e "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
      -e "s|http://deb.debian.org/debian|${DEBIAN_MIRROR}|g" \
      /etc/apt/sources.list.d/debian.sources \
  && apt-get update \
  && apt-get install -y --no-install-recommends fonts-noto-cjk \
  && groupadd --gid 10001 edunova \
  && useradd --uid 10001 --gid edunova --no-create-home --shell /usr/sbin/nologin edunova \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN --mount=type=cache,id=edunova-pip,target=/root/.cache/pip \
    python -m pip install --index-url "$PIP_INDEX_URL" --upgrade pip \
  && python -m pip install --index-url "$PIP_INDEX_URL" -r /app/backend/requirements.txt

FROM base AS ai-worker

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG HF_ENDPOINT=https://huggingface.co
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_VERSION=2.13.0+cpu
ARG TORCHVISION_VERSION=0.28.0+cpu

COPY backend/requirements-ai.txt /app/backend/requirements-ai.txt
RUN --mount=type=cache,id=edunova-pip,target=/root/.cache/pip \
    python -m pip install --index-url "$TORCH_INDEX_URL" \
      "torch==$TORCH_VERSION" "torchvision==$TORCHVISION_VERSION" \
  && python -m pip install --index-url "$PIP_INDEX_URL" -r /app/backend/requirements-ai.txt
RUN --mount=type=cache,id=edunova-huggingface,target=/root/.cache/huggingface \
    set -eu; \
    attempt=1; \
    while true; do \
      if HF_ENDPOINT="$HF_ENDPOINT" HF_HUB_DOWNLOAD_TIMEOUT=120 \
        docling-tools models download --output-dir /opt/docling/models layout tableformer; then \
        break; \
      fi; \
      if [ "$attempt" -ge 3 ]; then \
        echo "Docling 模型下载连续失败 ${attempt} 次。" >&2; \
        exit 1; \
      fi; \
      rm -rf /opt/docling/models; \
      attempt=$((attempt + 1)); \
      sleep $((attempt * 5)); \
    done

COPY backend /app/backend

RUN mkdir -p /app/storage/exports /app/var/uploads/materials /app/var/uploads/chat-attachments \
  && chown -R edunova:edunova /app/storage /app/var

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
ENV DOCLING_ARTIFACTS_PATH=/opt/docling/models

USER edunova

FROM base AS runtime

COPY alembic.ini /app/alembic.ini
COPY backend /app/backend

RUN mkdir -p /app/storage/exports /app/var/uploads/materials /app/var/uploads/chat-attachments \
  && chown -R edunova:edunova /app/storage /app/var

USER edunova

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python -m backend.app.cli sync-builtin-courses && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]

FROM runtime AS local-backend
USER root
RUN --mount=type=cache,id=edunova-pip,target=/root/.cache/pip \
    python -m pip install -r /app/backend/requirements-local-embedding.txt && python -m pip check
USER edunova

FROM ai-worker AS local-ai-worker
USER root
RUN --mount=type=cache,id=edunova-pip,target=/root/.cache/pip \
    python -m pip install -r /app/backend/requirements-local-embedding.txt && python -m pip check
USER edunova

FROM runtime AS local-speech
USER root
RUN --mount=type=cache,id=edunova-pip,target=/root/.cache/pip \
    python -m pip install -r /app/backend/requirements-local-speech.txt && python -m pip check
USER edunova
CMD ["python", "-m", "uvicorn", "backend.app.speech_server:app", "--host", "0.0.0.0", "--port", "8091", "--no-access-log"]

FROM runtime AS backend
