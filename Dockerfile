# ---- Stage 1: builder ----
FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

# ---- Stage 2: runtime ----
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Non-root user
RUN useradd -m -u 1000 nutrimentor
COPY --from=builder /install /usr/local
COPY --chown=nutrimentor:nutrimentor src ./src
COPY --chown=nutrimentor:nutrimentor data ./data

USER nutrimentor

# Data & models are mounted as volumes
VOLUME ["/app/data/raw", "/app/vector_store", "/app/models/bge-large-zh"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/student/api/health')"

CMD ["python", "-m", "nutrimentor.servers.flask_app"]
