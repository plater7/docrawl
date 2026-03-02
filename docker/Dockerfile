# Docrawl Dockerfile
#
# 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.

FROM python:3.12.9-slim-bookworm

WORKDIR /app

# Install system dependencies for Playwright (consolidated layer, no curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r docrawl && useradd -r -g docrawl -m -d /home/docrawl docrawl

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright system dependencies
RUN playwright install-deps chromium

# Copy application code
COPY src/ ./src/

# Create data directory and set permissions
RUN mkdir -p /data && chown -R docrawl:docrawl /data

# Switch to non-root user
USER docrawl

# Install Playwright browsers as docrawl user (installs to ~/.cache/ms-playwright)
RUN playwright install chromium

EXPOSE 8002

# Health check - verifies the API is responding (python urllib replaces curl dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/api/health/ready')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002", "--timeout-graceful-shutdown", "5"]
