FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 memoria && mkdir -p /data && chown memoria:memoria /data

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY scripts ./scripts

RUN python -m pip install --upgrade pip && \
    python -m pip install ".[product]"

USER memoria

EXPOSE 8080
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "memoria_resolutiva.product_server:app", "--host", "0.0.0.0", "--port", "8080"]
