# Docrawl Dockerfile
#
# 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r docrawl && useradd -r -g docrawl docrawl

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY src/ ./src/

# Create data directory and set permissions
RUN mkdir -p /data && chown -R docrawl:docrawl /data

# Switch to non-root user
USER docrawl

EXPOSE 8002

# Health check - verifies the API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/api/health/ready || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002", "--timeout-graceful-shutdown", "5"]
