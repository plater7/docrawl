# Troubleshooting Guide

> Generated with AI assistance by DocCrawler (model: qwen3-coder:free) and human review.

Common issues and solutions for Docrawl.

## Table of Contents

- [Ollama Issues](#ollama-issues)
- [LM Studio Issues](#lm-studio-issues)
- [Docker Issues](#docker-issues)
- [Permission Issues](#permission-issues)
- [Network Issues](#network-issues)
- [Performance Issues](#performance-issues)
- [Page Cache Issues](#page-cache-issues)
- [Pause / Resume Issues](#pause--resume-issues)

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

## LM Studio Issues

> Added in v0.9.10 (PR #154)

### Models not appearing in dropdown

**Symptoms**: LM Studio selected as provider but model list is empty.

**Causes & Solutions**:

1. **LM Studio server not running**: Open LM Studio and click "Start Server" in the Local Server tab.

2. **Wrong port**: Default is `1234`. Verify with:
   ```bash
   curl http://localhost:1234/v1/models
   ```
   If using a custom port, update `LMSTUDIO_URL` in `.env`.

3. **No model loaded**: LM Studio must have at least one model loaded. Load a model from the Models tab before starting the server.

4. **Docker networking**: When running Docrawl in Docker, use `host.docker.internal`:
   ```env
   LMSTUDIO_URL=http://host.docker.internal:1234/v1
   ```

### "Connection refused" to LM Studio

**Symptoms**: Error connecting to LM Studio endpoint.

**Solutions**:

1. **Check the server is running**:
   ```bash
   curl http://localhost:1234/v1/models
   ```

2. **Check firewall**: LM Studio binds to `localhost` by default. If running in a VM or WSL, ensure port 1234 is forwarded.

3. **API key mismatch**: If you set a custom API key in LM Studio, update `.env`:
   ```env
   LMSTUDIO_API_KEY=your-custom-key
   ```
   The default `lm-studio` key works when no authentication is configured.

### Model prefix issues

**Symptoms**: Model runs on wrong provider or `model not found` errors.

**Solution**: Prefix model names with `lmstudio/` to ensure correct routing:
```json
{
  "crawl_model": "lmstudio/mistral-7b-instruct"
}
```

Bare model names (without prefix) default to Ollama. The `lmstudio/` prefix tells the LLM client to route to LM Studio.

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

**Symptoms**: `browserType.launch: Executable doesn't exist` or similar Playwright errors.

**Solution**:

```bash
# The Docker image includes Playwright browsers
# If running locally without Docker:
pip install playwright
playwright install chromium
playwright install-deps
```

---

## Permission Issues

### Cannot write to data directory

**Symptoms**: `PermissionError` when saving crawl results.

**Solution**:

```bash
# Ensure data directory exists and is writable
mkdir -p ./data
chmod 755 ./data

# If using Docker, check volume mount permissions
docker compose down
sudo chown -R $(id -u):$(id -g) ./data
docker compose up
```

### API returns 403 Forbidden

**Symptoms**: API calls return `403 Forbidden` responses.

**Cause**: This typically happens when crawling sites with strict access policies.

**Solutions**:

1. **Check robots.txt**: The target site may block crawlers
2. **Add delay between requests**: Use the `delay` parameter in crawl settings
3. **Use a custom User-Agent**: Some sites block default Python user agents

---

## Network Issues

### Timeout errors during crawling

**Symptoms**: `TimeoutError` or `Navigation timeout of 30000 ms exceeded`

**Solutions**:

1. **Increase timeout**:
   - In the UI, set a higher timeout value (default: 30s)
   - For large/slow sites, try 60s or 120s

2. **Check network connectivity**:
   ```bash
   # From inside the container
   docker exec -it docrawl curl -I https://example.com
   ```

3. **Check if the site is blocking you**:
   ```bash
   curl -I -A "Mozilla/5.0" https://target-site.com
   ```

### DNS resolution failures

**Symptoms**: `Error: getaddrinfo ENOTFOUND` or `Name resolution failed`

**Solutions**:

1. **Check Docker DNS settings**:
   ```json
   // /etc/docker/daemon.json
   {
     "dns": ["8.8.8.8", "8.8.4.4"]
   }
   ```

2. **Restart Docker**:
   ```bash
   sudo systemctl restart docker
   ```

### SSL/TLS certificate errors

**Symptoms**: `SSL: CERTIFICATE_VERIFY_FAILED` or similar TLS errors.

**Solution**: This often happens with self-signed certificates or corporate proxies.

```bash
# For development only (not recommended for production):
# Set environment variable to ignore SSL verification
export PYTHONHTTPSVERIFY=0
```

> **Warning**: Disabling SSL verification is a security risk. Only use for development.

---

## Performance Issues

### Crawling is very slow

**Solutions**:

1. **Use a smaller/faster model**:
   - `mistral:7b` is faster than `qwen2.5:14b`
   - Consider using `qwen3-coder:free` via OpenRouter for cloud processing

2. **Reduce page limit**: Start with a smaller number of pages

3. **Check system resources**:
   ```bash
   # Check CPU and memory usage
   docker stats docrawl
   
   # Check Ollama resource usage
   ollama ps
   ```

4. **Use GPU acceleration for Ollama** (if available):
   ```bash
   # Check GPU availability
   nvidia-smi
   
   # Ollama automatically uses GPU if available
   ```

5. **Enable pipeline mode** for large sites:
   ```env
   use_pipeline_mode=true
   ```
   Pipeline mode uses a producer/consumer pattern with `asyncio.Queue`, allowing discovery and scraping to run concurrently.

### Out of memory errors

**Symptoms**: Container killed or `OOMKilled` in Docker.

**Solutions**:

1. **Increase Docker memory limit**:
   - Docker Desktop: Settings > Resources > Memory
   - docker-compose.yml:
     ```yaml
     deploy:
       resources:
         limits:
           memory: 4G
     ```

2. **Use a smaller model**: 7B models use ~4GB RAM, 14B models use ~8GB RAM

3. **Reduce concurrent pages**: Lower the concurrency setting

### High disk usage

**Symptoms**: Disk space running low after multiple crawls.

**Solution**:

```bash
# Check data directory size
du -sh ./data

# Clean up old crawl results
# (through the UI or manually)
rm -rf ./data/old-crawl-*

# Clean up Docker resources
docker system prune -f
```

---

## Page Cache Issues

> Added in v0.9.5 (PR #130)

### Stale content being served

**Symptoms**: Crawl results don't reflect recent changes on the target site.

**Cause**: Page cache (24h TTL) is returning cached content.

**Solutions**:

1. **Disable cache for this job**:
   ```env
   use_cache=false
   ```

2. **Clear the cache**: Delete the cache directory:
   ```bash
   rm -rf ./data/.page_cache/
   ```

3. **Wait for TTL expiry**: Cache entries expire after 24 hours automatically.

### Cache HIT/MISS in logs

**Info**: When cache is enabled, logs show `[CACHE HIT]` or `[CACHE MISS]` per page. This is normal behavior. A high HIT ratio means the site hasn't changed much since last crawl; a high MISS ratio means fresh content is being fetched.

---

## Pause / Resume Issues

> Added in v0.9.6 (PR #132)

### Pause returns 409 Conflict

**Symptoms**: `POST /api/jobs/{id}/pause` returns `409 Conflict`.

**Cause**: The job is not in a pausable state. Only `running` jobs can be paused.

**Solution**: Check job status first:
```bash
curl http://localhost:8002/api/jobs/{id}/status
```

Valid transitions: `running` -> `paused` -> `running` (resume).

### Resume fails or restarts from beginning

**Symptoms**: Resumed job re-scrapes already-completed pages.

**Cause**: Checkpoint file `.job_state.json` is missing or corrupted.

**Solutions**:

1. **Check checkpoint exists**:
   ```bash
   ls -la ./data/{job_id}/.job_state.json
   ```

2. **Verify checkpoint content**:
   ```bash
   cat ./data/{job_id}/.job_state.json | python -m json.tool
   ```
   It should contain `completed_urls`, `current_phase`, and `progress` fields.

3. **If checkpoint is lost**: The job will restart from the beginning. Enable `use_cache=true` to skip re-scraping pages that are still cached.

### Job state not persisted after crash

**Symptoms**: After a server restart, paused jobs cannot be resumed.

**Cause**: Known limitation -- automatic resume on server restart is not yet implemented (see Roadmap v1.0.0).

**Workaround**: After restarting the server, manually call the resume endpoint:
```bash
POST /api/jobs/{job_id}/resume
```

If the job state file exists, it will resume from checkpoint. If not, you'll need to start a new job.

---

## Still Having Issues?

1. **Check the logs**: `docker compose logs -f docrawl`
2. **Open an issue**: [GitHub Issues](https://github.com/plater7/docrawl/issues)
3. **Check existing issues**: Your problem may already have a solution

> **Tip**: When reporting issues, include:
> - Your OS and Docker version
> - The full error message
> - Steps to reproduce the issue
> - Your `docker-compose.yml` (without secrets)
