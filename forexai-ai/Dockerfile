FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PREWARM_QUANT=true

# requirements.txt is copied on its own and installed before any other build
# step so this (slow) layer stays cached while the source changes.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Only the application and the trained model artifacts are copied into the
# image. ``.dockerignore`` keeps secrets (.env), data and tests out.
COPY app ./app
COPY models ./models

# The artifact fetcher is the one build-time script the image needs; every
# other script (dev checks, the local MT5 bridge) stays out of the context.
COPY scripts/fetch_model_artifacts.py ./scripts/fetch_model_artifacts.py

# The ensemble binaries are git-ignored, so a hosted build (which clones the
# repository) sees an empty models/ directory and would ship a signal
# generator with no quant module. Fetch the exact artifacts listed in
# models/ARTIFACTS.sha256, verifying each checksum. On a local build they are
# already present and this is a no-op.
ARG MODEL_ARTIFACTS_BASE_URL=https://github.com/MBKNgcobo/ForexAI_signal_generator/releases/download/models-v1
ENV MODEL_ARTIFACTS_BASE_URL=${MODEL_ARTIFACTS_BASE_URL}

RUN python scripts/fetch_model_artifacts.py

# Run as an unprivileged user; the base image's root account is not needed
# at runtime.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0 if r.status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]