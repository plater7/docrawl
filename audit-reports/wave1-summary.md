# Wave 1 — Core Code Review Summary

**Date:** 2026-02-24
**Agents:** 5 (all sonnet model)
**Total Findings:** 174 raw (before deduplication)

## Findings by Agent

| # | Agent | Findings | Critical | Major | Minor | Suggestion |
|---|-------|----------|----------|-------|-------|------------|
| 1 | python-pro | 34 | 2 | 14 | 14 | 4 |
| 2 | backend-developer | 32 | 6 | 13 | 7 | 6 |
| 3 | frontend-developer | 37 | 2 | 17 | 18 | 0 |
| 4 | api-designer | 36 | 3 | 13 | 16 | 4 |
| 5 | fullstack-developer | 35 | 2 | 11 | 19 | 3 |

## Critical Findings (Cross-Agent Consensus)

### 1. Path Traversal via `output_path` (Agents: 2, 4, 5)
- **File:** `src/api/models.py:13`, `src/jobs/runner.py:285`
- No validation on `output_path` — arbitrary filesystem writes possible
- **Fix:** Pydantic `field_validator` enforcing `/data/` prefix + `.resolve()` check

### 2. No Authentication (Agents: 2, 4)
- **File:** All API endpoints
- Zero auth on any endpoint; relies entirely on Cloudflare Worker perimeter
- **Fix:** API key middleware (`X-API-Key` header)

### 3. No Rate Limiting / Job Concurrency Cap (Agents: 2, 4)
- **File:** `src/api/routes.py`, `src/jobs/manager.py`
- Unlimited job creation → Playwright browser exhaustion → DoS
- **Fix:** `slowapi` + `MAX_CONCURRENT_JOBS` in JobManager

### 4. Blocking Sync HTTP in Async Context (Agents: 1, 2, 4, 5)
- **File:** `src/llm/client.py:97-135` (`_get_openrouter_models`)
- Synchronous `httpx.get()` blocks entire event loop up to 10s
- **Fix:** Convert to `async def` with `httpx.AsyncClient`

### 5. XSS via `innerHTML` (Agent: 3)
- **File:** `src/ui/index.html:1273-1274, 1330-1334`
- SSE message data interpolated directly into `innerHTML` without sanitization
- **Fix:** Use `textContent` / `createElement` instead of string interpolation

### 6. In-Memory State with No Eviction (Agents: 1, 2, 4)
- **File:** `src/jobs/manager.py:83-89`
- Jobs accumulate forever → memory leak → eventual OOM
- **Fix:** TTL-based eviction for terminal jobs

### 7. `asyncio.create_task` Fire-and-Forget (Agent: 2)
- **File:** `src/jobs/manager.py:94`
- No `add_done_callback`, no shutdown cancellation, orphaned browsers on restart
- **Fix:** Done callback + lifespan shutdown handler

### 8. Browser/Playwright Resource Leaks (Agents: 1, 5)
- **File:** `src/scraper/page.py:109-113`, `src/crawler/discovery.py:237-296`
- Playwright instance not stored/stopped; browser leaked on timeout in nav_parse
- **Fix:** Store `self._playwright`, add `finally: await browser.close()`

## Major Findings (Deduplicated Top 10)

1. **`max_concurrent` never implemented** — sequential processing despite API accepting param (Agents: 4, 5)
2. **Sync file writes in async context** — `write_text()` blocks event loop per page (Agents: 1, 5)
3. **`_generate_index` produces broken links** — uses `_` separator vs actual `/` path structure (Agent: 5)
4. **Chunk overlap causes duplicate content** — 200-char overlap duplicated in output (Agent: 5)
5. **`num_ctx: 8192` too small for 16KB chunks** — LLM silently truncates output (Agent: 5)
6. **Health check returns 200 when not ready** — Docker healthcheck is non-functional (Agents: 2, 4)
7. **`__import__('os')` inline anti-pattern** — in `routes.py:62-63` (Agents: 1, 2, 4)
8. **No CORS configuration** — CORSMiddleware completely absent (Agents: 2, 4)
9. **No API versioning** — `/api/` without `/api/v1/` prefix (Agents: 2, 4)
10. **`print()` mixed with `logging`** — 30+ print statements in `discovery.py` (Agents: 1, 2)

## Files by Coverage

| File | Agents Covering | Finding Count |
|------|----------------|---------------|
| `src/jobs/runner.py` | 1, 2, 4, 5 | ~25 |
| `src/api/routes.py` | 1, 2, 4 | ~20 |
| `src/llm/client.py` | 1, 4, 5 | ~15 |
| `src/ui/index.html` | 3 | 37 |
| `src/crawler/discovery.py` | 1, 5 | ~12 |
| `src/api/models.py` | 2, 4, 5 | ~10 |
| `src/jobs/manager.py` | 1, 2, 4 | ~10 |
| `src/scraper/page.py` | 1, 5 | ~8 |
| `src/scraper/markdown.py` | 5 | ~4 |
| `src/exceptions.py` | 1 | 3 |

## Remaining Waves

- **Wave 2:** Infrastructure & DevOps (docker-expert, deployment-engineer, devops-engineer, security-engineer)
- **Wave 3:** AI/ML Engineering (ai-engineer, llm-architect, prompt-engineer)
- **Wave 4:** Quality & Security (code-reviewer, security-auditor, performance-engineer, qa-expert, test-automator)
- **Wave 5:** Documentation & DX (documentation-engineer, git-workflow-manager, refactoring-specialist)
- **Wave 6:** Architecture Review (architect-reviewer)
- **Wave 7:** Synthesis (agent-organizer, multi-agent-coordinator)
