FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY api /workspace/api

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -e ./api[dev]

ENV PYTHONPATH=/workspace/api

CMD ["celery", "-A", "app.tasks:celery_app", "worker", "--loglevel=info", "--concurrency=2", "--prefetch-multiplier=1"]
