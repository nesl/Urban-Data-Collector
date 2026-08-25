FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ALERTCalifornia needs a real browser. The other collectors share this image so
# Compose only has to build and maintain one artifact.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY extractor_modules ./extractor_modules
COPY observation_contract ./observation_contract
COPY utilities ./utilities
RUN pip install --upgrade pip && pip install . -r requirements.txt

CMD ["python", "-m", "extractor_modules.container_scheduler", "--help"]
