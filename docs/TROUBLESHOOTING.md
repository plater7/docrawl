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
   export OLLAMA_HOST=0.0.0.0
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
ollama pull <model-name>
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

3. **No model loaded**: LM Studio must have at least one model loaded before starting the server.

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

### Model prefix issues

**Symptoms**: Model runs on wrong provider or `model not found` errors.

**Solution**: Prefix model names with `lmstudio/` to ensure correct routing:
```json
{
  "crawl_model": "lmstudio/mistral-7b-instruct"
}
```

Bare model names (without prefix) default to Ollama.

---

## Docker Issues

### Container exits immediately

**Symptoms**: `docker compose up` shows container starting then immediately exiting.

**Solution**:

```bash
docker compose logs docrawl

# Common fixes:
# 1. Port 8002 already in use
lsof -i :8002

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
sudo chown -R $(id -u):$(id -g) ./data
```

### Playwright browser fails to start

**Symptoms**: `browserType.launch: Executable doesn't exist` or similar Playwright errors.

**Solution**:

```bash
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
mkdir -p ./data
chmod 755 ./data
docker compose down
sudo chown -R $(id -u):$(id -g) ./data
docker compose up
```

### API returns 403 Forbidden

**Symptoms**: API calls return `403 Forbidden` responses.

**Solutions**:

1. **Check robots.txt**: The target site may block crawlers
2. **Add delay between requests**: Use the `delay` parameter
3. **Use a custom User-Agent**: Some sites block default Python user agents

---

## Network Issues

### Timeout errors during crawling

**Symptoms**: `TimeoutError` or `Navigation timeout of 30000 ms exceeded`

**Solutions**:

1. **Increase timeout**: Set a higher timeout value (60s or 120s)
2. **Check network connectivity**:
   ```bash
   docker exec -it docrawl curl -I https://example.com
   ```
3. **Check if the site is blocking you**:
   ```bash
   curl -I -A "Mozilla/5.0" https://target-site.com
   ```

### DNS resolution failures

**Symptoms**: `Error: getaddrinfo ENOTFOUND`

**Solutions**:

1. **Check Docker DNS settings** in `/etc/docker/daemon.json`
2. **Restart Docker**: `sudo systemctl restart docker`

### SSL/TLS certificate errors

**Symptoms**: `SSL: CERTIFICATE_VERIFY_FAILED`

**Solution** (development only):
```bash
export PYTHONHTTPSVERIFY=0
```

> **Warning**: Disabling SSL verification is a security risk.

---

## Performance Issues

### Crawling is very slow

**Solutions**:

1. **Use a smaller/faster model** (`mistral:7b` over `qwen2.5:14b`)
2. **Reduce page limit**: Start with fewer pages
3. **Check system resources**: `docker stats docrawl`
4. **Use GPU acceleration**: `nvidia-smi` to verify
5. **Enable pipeline mode** for large sites:
   ```env
   use_pipeline_mode=true
   ```
   Pipeline mode uses producer/consumer pattern with `asyncio.Queue`.

### Out of memory errors

**Symptoms**: Container killed or `OOMKilled` in Docker.

**Solutions**:

1. **Increase Docker memory limit** (4G minimum)
2. **Use a smaller model**: 7B models use ~4GB RAM
3. **Reduce concurrent pages**

### High disk usage

```bash
du -sh ./data
rm -rf ./data/old-crawl-*
docker system prune -f
```

---

## Page Cache Issues

> Added in v0.9.5 (PR #130)

### Stale content being served

**Symptoms**: Crawl results don't reflect recent changes on the target site.

**Cause**: Page cache (24h TTL) is returning cached content.

**Solutions**:

1. **Disable cache for this job**: `use_cache=false`
2. **Clear the cache**: `rm -rf ./data/.page_cache/`
3. **Wait for TTL expiry**: Cache entries expire after 24 hours.

### Cache HIT/MISS in logs

**Info**: When cache is enabled, logs show `[CACHE HIT]` or `[CACHE MISS]` per page. This is normal. High HIT ratio = site unchanged; high MISS ratio = fresh content being fetched.

---

## Pause / Resume Issues

> Added in v0.9.6 (PR #132)

### Pause returns 409 Conflict

**Symptoms**: `POST /api/jobs/{id}/pause` returns `409 Conflict`.

**Cause**: Job is not in a pausable state. Only `running` jobs can be paused.

**Solution**: Check job status first:
```bash
curl http://localhost:8002/api/jobs/{id}/status
```

### Resume fails or restarts from beginning

**Symptoms**: Resumed job re-scrapes already-completed pages.

**Cause**: Checkpoint file `.job_state.json` is missing or corrupted.

**Solutions**:

1. **Check checkpoint exists**: `ls -la ./data/{job_id}/.job_state.json`
2. **Verify checkpoint content**: Should contain `completed_urls`, `current_phase`, `progress`
3. **If checkpoint is lost**: Enable `use_cache=true` to skip re-scraping cached pages.

### Job state not persisted after crash

**Cause**: Automatic resume on server restart is not yet implemented (Roadmap v1.0.0).

**Workaround**: After restarting, manually call:
```bash
POST /api/jobs/{job_id}/resume
```

---

## Still Having Issues?

1. **Check the logs**: `docker compose logs -f docrawl`
2. **Open an issue**: [GitHub Issues](https://github.com/plater7/docrawl/issues)
3. **Check existing issues**: Your problem may already have a solution

> **Tip**: When reporting issues, include your OS, Docker version, error message, and steps to reproduce.
