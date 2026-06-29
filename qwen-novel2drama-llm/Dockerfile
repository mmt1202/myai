FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/api-server.txt requirements/api-server.txt
COPY requirements/provider-adapter.txt requirements/provider-adapter.txt
COPY requirements/postgres-run-store.txt requirements/postgres-run-store.txt
COPY requirements/postgres-quota.txt requirements/postgres-quota.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements/api-server.txt \
    && python -m pip install -r requirements/provider-adapter.txt \
    && python -m pip install -r requirements/postgres-run-store.txt \
    && python -m pip install -r requirements/postgres-quota.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/v1/ready', timeout=3) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    raise SystemExit(0 if data.get('status') in {'ok', 'degraded'} else 1)
PY

CMD ["python", "inference/api_server.py", "--host", "0.0.0.0", "--port", "8000", "--skip-model-load"]
