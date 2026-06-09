FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=/app/env/compose.config.yaml

WORKDIR /app

RUN python -m pip install --no-cache-dir "PyYAML>=6.0"

COPY app ./app
COPY config ./config
COPY core ./core
COPY modules ./modules
COPY tools ./tools
COPY transport ./transport
COPY pyproject.toml README.md ./

RUN mkdir -p /data/artifacts /app/env

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=3)); raise SystemExit(0 if data.get('ok') else 1)"

CMD ["python", "-m", "app.main"]
