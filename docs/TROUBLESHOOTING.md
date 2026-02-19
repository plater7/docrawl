# Troubleshooting Guide

> 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.

Common issues and solutions for Docrawl.

## Table of Contents

- [Ollama Issues](#ollama-issues)
- [Docker Issues](#docker-issues)
- [Permission Issues](#permission-issues)
- [Network Issues](#network-issues)
- [Performance Issues](#performance-issues)

---

## Ollama Issues

### "No models available" or empty model list

**Symptoms**: The UI shows "No ollama models available" or the model dropdown is empty.

**Cause**: Ollama is not running or has no models pulled.

**Solution**:

```bash
# 1. Check if Ollama is running
ollama list

# If command not found, install Ollama:
# macOS/Linux:
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Start Ollama service (if not running)
ollama serve

# 3. Pull at least one model
ollama pull mistral:7b        # Good for crawl
ollama pull qwen2.5:14b       # Good for pipeline
ollama pull deepseek-r1:7b    # Good for reasoning

# 4. Verify models are available
ollama list
```

### "Connection refused" to Ollama

**Symptoms**: Error `Cannot connect to Ollama at http://host.docker.internal:11434`

**Cause**: Docker cannot reach the host's Ollama service.

**Solutions**:

1. **Check Ollama is running on host**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. **On Linux, add OLLAMA_HOST**:
   ```bash
   # In your .bashrc or .zshrc
   export OLLAMA_HOST=0.0.0.0
   
   # Restart Ollama
   pkill ollama
   ollama serve &
   ```

3. **Docker Desktop users** - `host.docker.internal` should work automatically.

4. **Linux users without Docker Desktop** - Ensure docker-compose has:
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```

### Model not found error

**Symptoms**: `Error: model "xyz" not found`

**Solution**:
```bash
# Pull the missing model
ollama pull <model-name>

# Example:
ollama pull mistral:7b
```

---

## Docker Issues

### Container exits immediately

**Symptoms**: `docker compose up` shows container starting then immediately exiting.

**Solution**:

```bash
# Check logs for the error
docker compose logs docrawl

# Common fixes:

# 1. Port 8002 already in use
lsof -i :8002
# Kill the process or change port in docker-compose.yml

# 2. Missing data directory
mkdir -p ./data

# 3. Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up
```

### "permission denied" creating files

**Symptoms**: Container logs show `PermissionError: [Errno 13] Permission denied`

**Solution**:

```bash
# Fix ownership of data directory
sudo chown -R $(id -u):$(id -g) ./data

# Or for Docker on Linux, add your user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

### Playwright browser fails to start

**Symptoms**: `browser.new_page: browser closed unexpectedly`

**Solution**:

```bash
# Ensure Docker has enough shared memory
# Add to docker-compose.yml under docrawl service:
shm_size: '2gb'

# Or run with:
docker compose run --shm-size=2gb docrawl
```

### Out of memory (OOM) errors

**Symptoms**: Container killed, slow performance, crashes during large crawls.

**Solution**:

```bash
# Increase Docker memory limit (Docker Desktop)
# Settings > Resources > Memory: at least 4GB

# For docker-compose, add resource limits:
# (Already included in docker-compose.yml)
```

---

## Permission Issues

### Cannot write to /data

**Symptoms**: `PermissionError: [Errno 13] Permission denied: '/data/output'`

**Solutions**:

```bash
# Option 1: Fix ownership
sudo chown -R $USER:$USER ./data

# Option 2: Fix permissions (less secure)
chmod -R 777 ./data

# Option 3: Run Docker with your user ID
docker compose run --user $(id -u):$(id -g) docrawl
```

### Cannot write to output path

**Symptoms**: Job fails with permission error on specific output path.

**Solution**:

```bash
# The output path must be under /data (the mounted volume)
# Correct: /data/output/example.com
# Wrong:   /home/user/output

# In the UI, ensure output path starts with /data/
```

---

## Network Issues

### "Connection refused" to target website

**Symptoms**: `Failed to connect to docs.example.com`

**Solutions**:

1. **Check your network**:
   ```bash
   curl -I https://docs.example.com
   ```

2. **DNS issues** - Try a different DNS or check `/etc/resolv.conf`

3. **Proxy required** - Set environment variables:
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   ```

### Timeout errors during crawl

**Symptoms**: `TimeoutError: page.goto: Timeout 30000ms exceeded`

**Solutions**:

1. **Increase request delay** - Set delay to 1000ms or more in UI
2. **Reduce concurrency** - Set max concurrent to 1 or 2
3. **Check target site status** - Site may be slow or blocking requests

### robots.txt blocking all URLs

**Symptoms**: All or most URLs filtered out by robots.txt

**Solution**:

Uncheck "Respect robots.txt" in the UI, or verify the site's policy:
```bash
curl https://docs.example.com/robots.txt
```

---

## Performance Issues

### Crawling is very slow

**Solutions**:

1. **Use a smaller crawl model** (3B-8B parameters):
   - `mistral:7b`, `qwen2.5:7b`, `phi3:mini`

2. **Reduce max depth** - Start with 3 instead of 5

3. **Increase delay is counterproductive** - If site allows, reduce delay to 200ms

4. **Check Ollama performance**:
   ```bash
   # Ensure GPU is being used (if available)
   nvidia-smi
   
   # Check Ollama is not CPU-bound
   htop
   ```

### High memory usage

**Solutions**:

1. **Use quantized models** (q4, q5, q8 suffix):
   ```bash
   ollama pull mistral:7b-q4
   ```

2. **Reduce concurrent pages** in UI to 1-2

3. **Limit crawl depth** to avoid queue overflow

### UI not responding during large crawl

**Symptoms**: UI freezes, logs stop updating.

**Cause**: Browser memory issues with too many log entries.

**Solution**: Refresh the page. Job continues running in background. Check status with:
```bash
curl http://localhost:8002/api/jobs
```

---

## Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Run with debug logs
LOG_LEVEL=DEBUG docker compose up

# Or in .env:
LOG_LEVEL=DEBUG
```

Check container health:
```bash
curl http://localhost:8002/api/health/ready
```

---

## Getting Help

1. Check this guide first
2. Search [GitHub Issues](https://github.com/plater7/docrawl/issues)
3. Open a new issue with:
   - `docker compose logs docrawl` output
   - Your docker-compose.yml
   - Steps to reproduce
   - `curl http://localhost:8002/api/health/ready` output
