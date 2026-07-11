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
RUN python -c "import tomllib; project = tomllib.load(open('pyproject.toml', 'rb'))['project']; print('\n'.join(project.get('dependencies', [])))" > /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt && \
    python -c "from alembic.config import main as alembic_main; import uvicorn; print('verified runtime dependencies:', alembic_main.__name__, uvicorn.__version__)"

COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY books/ ./books/
COPY docs/books/audio/ ./docs/books/audio/
COPY scripts/ ./scripts/
COPY src/ ./src/

# Install only the local project package after source code is copied.
RUN python -m pip install --no-cache-dir --no-deps . && \
    python -c "from alembic.config import main as alembic_main; print('verified alembic cli entrypoint:', alembic_main.__name__)"

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
