# Patterns & Conventions

> What works well in DocRawl. Follow these when writing new code.

---

## Development Workflow

**Issue-driven development:** Every change starts with a GitHub issue. Feature branches (`feat/`, `fix/`, `chore/`) → PRs with conventional commits → merge to main → tag.

**PR structure:** Title is descriptive. Body has three sections: `## Problem`, `## Solution`, `## Testing`. Keep PRs atomic — reverting one shouldn't break others.

**Branch naming:** `feat/page-pool`, `fix/cleanup-performance`, `chore/docker-hardening`. PR references like `PR 1.2` map to the roadmap but branch names are human-readable.

**Conventional commits:** `feat:`, `fix:`, `chore:`, `perf:`, `refactor:`. Scope optional but useful: `feat(scraper): add http fast-path`.

---

## Code Patterns

**Graceful fallback chain:** Every new capability has a fallback to existing behavior. Pattern:
```python
result = await try_new_thing(url)
if result is None:
    result = await try_old_thing(url)  # always works
```
Used in: scraping (native MD → proxy → http-fast → Playwright), discovery (sitemap → nav → BFS).

**Opt-in with defaults:** New `JobRequest` fields always have a default value that preserves existing behavior:
```python
use_http_fast_path: bool = True   # safe — falls through to Playwright
use_cache: bool = False           # off by default — opt-in
output_format: Literal["markdown", "json"] = "markdown"
```

**Atomic file writes:** Always write to `.tmp` then `os.replace()`. Prevents corrupt files on crash:
```python
tmp_path = target_path.with_suffix(".tmp")
tmp_path.write_text(content, encoding="utf-8")
os.replace(tmp_path, target_path)
```
Used in: job state, cache, markdown output.

**asyncio.Semaphore for concurrency:** `max_concurrent` enforced via semaphore, not thread pool:
```python
sem = asyncio.Semaphore(request.max_concurrent)
async def _process_page(url):
    async with sem:
        # ... do work
```

**Counter protection with asyncio.Lock:** Shared mutable counters (`pages_ok`, `pages_failed`, etc.) are guarded by `_counter_lock`:
```python
async with _counter_lock:
    pages_ok += 1
    job.pages_completed += 1
```

**XML delimiter isolation for LLM prompts:** Scraped content is wrapped in `<document>...</document>` tags before sending to LLM. Prevents prompt injection from documentation that contains instructions:
```python
wrapped = f"<document>\n{markdown}\n</document>"
```

---

## SSE Event Patterns

**Phase-aware logging:** Every SSE event includes `phase` (init, discovery, filtering, scraping, cleanup) and optionally `active_model`. The frontend uses this for the phase banner:
```python
await _log(job, "phase_change", {
    "phase": "filtering",
    "active_model": request.crawl_model,
    "message": f"LLM filtering with {request.crawl_model}...",
})
```

**Terminal events:** `job_done`, `job_cancelled`, `job_error` are the only events that end the SSE stream. The frontend listens for these to stop the progress display.

**Keepalive:** Empty `keepalive` events every 20s (via `asyncio.wait_for` timeout in `event_stream`). Prevents proxies and browsers from closing idle connections.

---

## Testing Patterns

**Ascending difficulty test sites:** Always test against multiple sites in order:
1. httpx docs (easy — small, static MkDocs)
2. FastAPI docs (medium — 100+ pages, multi-language)
3. Stripe docs (hard — JS-rendered, 500+ URLs)
4. Cloudflare docs (extreme — supports `Accept: text/markdown`)

**Key metrics to capture per test:**
- Total job time (wall clock)
- Pages/second average
- Container memory peak (`docker stats`)
- Page replacement count (pool health)
- Error rate vs previous baseline

**Configuration matrix for PagePool testing:**
- `PAGE_POOL_SIZE=2, max_concurrent=3` (pool saturation)
- `PAGE_POOL_SIZE=5, max_concurrent=5` (balanced)
- `PAGE_POOL_SIZE=0` (legacy path, regression check)
- `PAGE_POOL_SIZE=1, max_concurrent=3` (forced serialization)

---

## Security Patterns

**SSRF validation before any network call:** `validate_url_not_ssrf()` called before Playwright navigation, httpx requests, and proxy calls. Checks against private IP ranges.

**Path traversal prevention:** `output_path` and `state_file_path` validated to resolve under `/data`. Pattern:
```python
resolved = Path("/data").joinpath(v.lstrip("/")).resolve()
if not str(resolved).startswith("/data"):
    raise ValueError("path must be under /data")
```

**API key auth (opt-in):** `API_KEY` env var. Empty = auth disabled. Non-empty = required in `X-Api-Key` header. Health and root endpoints exempt.

---

## Docker Patterns

**Non-root user:** Container runs as `docrawl` user, not root. Playwright browsers installed in user home.

**Healthcheck without curl:** Uses Python urllib instead of curl to avoid adding curl as a dependency:
```dockerfile
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/api/health/ready')" || exit 1
```

**Host access for Ollama:** `extra_hosts: ["host.docker.internal:host-gateway"]` + `OLLAMA_URL=http://host.docker.internal:11434`.

**shm_size:** `2gb` for Playwright — prevents crashes on large/complex pages.
