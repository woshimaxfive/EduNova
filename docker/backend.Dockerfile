FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends fonts-noto-cjk \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
  && python -m pip install --no-cache-dir -r /app/backend/requirements.txt

COPY alembic.ini /app/alembic.ini
COPY backend /app/backend

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python -m backend.app.cli sync-builtin-courses && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
