FROM python:3.11-slim AS collector-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements/base.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt
COPY extractor_modules/common ./extractor_modules/common
COPY extractor_modules/operations/__init__.py ./extractor_modules/operations/__init__.py
COPY extractor_modules/operations/scheduler.py ./extractor_modules/operations/scheduler.py

FROM collector-base AS gdelt
COPY requirements/gdelt.txt /tmp/requirements-service.txt
RUN pip install -r /tmp/requirements-service.txt
COPY extractor_modules/gdelt ./extractor_modules/gdelt

FROM collector-base AS pems
COPY requirements/pems.txt /tmp/requirements-service.txt
RUN pip install -r /tmp/requirements-service.txt
COPY extractor_modules/pems ./extractor_modules/pems

FROM collector-base AS cctv
COPY requirements/cctv.txt /tmp/requirements-service.txt
RUN pip install -r /tmp/requirements-service.txt
COPY extractor_modules/cctv ./extractor_modules/cctv

FROM collector-base AS alertcalifornia
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/alertcalifornia.txt /tmp/requirements-service.txt
RUN pip install -r /tmp/requirements-service.txt
COPY extractor_modules/alertcalifornia ./extractor_modules/alertcalifornia

FROM collector-base AS weather
COPY requirements/weather.txt /tmp/requirements-service.txt
RUN pip install -r /tmp/requirements-service.txt
COPY extractor_modules/weather ./extractor_modules/weather

FROM collector-base AS air
COPY requirements/air.txt /tmp/requirements-service.txt
RUN pip install -r /tmp/requirements-service.txt
COPY extractor_modules/air ./extractor_modules/air

FROM collector-base AS email
COPY requirements/email.txt /tmp/requirements-service.txt
RUN pip install -r /tmp/requirements-service.txt
COPY extractor_modules/email ./extractor_modules/email

FROM collector-base AS operations
COPY extractor_modules/operations/archive.py ./extractor_modules/operations/archive.py
COPY extractor_modules/operations/missing_data_alert.py ./extractor_modules/operations/missing_data_alert.py

CMD ["python", "-m", "extractor_modules.operations.scheduler", "--help"]

FROM python:3.11-slim AS processing

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements/processing.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt
COPY processing ./processing
COPY urban_observation_model ./urban_observation_model

CMD ["python", "-m", "processing.enrichment.service", "--help"]
