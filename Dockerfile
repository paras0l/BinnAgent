FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        ghostscript \
        libpq-dev \
        ocrmypdf \
        qpdf \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Install third-party Python dependencies before copying application code so
# source-only changes can reuse the expensive dependency layer.
COPY pyproject.toml ./
RUN python - <<'PY' > /tmp/requirements.txt
import tomllib

with open("pyproject.toml", "rb") as fh:
    project = tomllib.load(fh)["project"]

for dependency in project.get("dependencies", []):
    print(dependency)
PY
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY books/ ./books/
COPY scripts/ ./scripts/
COPY src/ ./src/

# Install only the local project package after source code is copied.
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
