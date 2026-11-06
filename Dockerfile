FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Create non-root application user
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application, database schema, and reference fonts
COPY fonts/ ./fonts/
COPY app/ ./app/
COPY static/ ./static/

# Secure ownership for persistent sqlite database creation
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Shell format to dynamically respect Render's $PORT environment variable
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
