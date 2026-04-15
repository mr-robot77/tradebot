# Dockerfile — Hugging Face Spaces (Docker SDK) deployment
#
# HF Spaces requires:
#   - The app to listen on port 7860
#   - No root filesystem writes beyond /tmp (app is read-only after build)
#
# Deploy instructions (≈ 5 minutes):
#   1. Create a free account at https://huggingface.co
#   2. Go to https://huggingface.co/spaces → New Space
#   3. Choose SDK: Docker  |  Space name: tradebot-backtest
#   4. Connect the mr-robot77/tradebot GitHub repository (or push manually)
#   5. HF builds this Dockerfile automatically
#   6. Your dashboard is live at:
#        https://huggingface.co/spaces/<your-username>/tradebot-backtest

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
