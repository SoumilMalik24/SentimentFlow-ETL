# ============================================================
# SentimentFlow — Dockerfile (Pipeline Only)
# Uses requirements-pipeline.txt — no Streamlit/admin deps.
# Streamlit admin is run locally with full requirements.txt.
# ============================================================

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ONLY pipeline dependencies (no Streamlit, Cloudinary, etc.)
COPY requirements-pipeline.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-pipeline.txt

# Copy source
COPY . .

RUN mkdir -p logs

# Default: run the ETL pipeline
CMD ["python", "main.py"]
