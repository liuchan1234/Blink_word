FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system deps (for asyncpg + poster image rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    fonts-dejavu-core \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

RUN chmod +x /app/entrypoint.sh

# Default listen port (runtime may override via PORT, e.g. Railway/Fly)
EXPOSE 8000

# Health check follows $PORT at runtime (same as uvicorn)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health')"

CMD ["/app/entrypoint.sh"]
