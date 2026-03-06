# ============================================================
# SentimentFlow — Dockerfile
# Python 3.11 slim image with all project dependencies
# ============================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required by psycopg2 and pyahocorasick
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the full project source
COPY . .

# Create logs directory
RUN mkdir -p logs

# Default command — runs the ETL pipeline
CMD ["python", "main.py"]
