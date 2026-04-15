# Dockerfile — Hugging Face Spaces (Docker SDK) deployment
#
# The app listens on port 7860 as required by HF Spaces.
# This file is read automatically when the Space is linked to this repository.

FROM python:3.11-slim

# Keep image small and avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /app

# Install OS dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cache friendly)
COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

# Copy application code
COPY backtest_dashboard.py .

# HF Spaces runs as a non-root user — create one
RUN useradd -m appuser
USER appuser

EXPOSE 7860

CMD ["gunicorn", "backtest_dashboard:server", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "1", \
     "--timeout", "120", \
     "--log-level", "info"]
