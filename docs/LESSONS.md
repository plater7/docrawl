# Lessons Learned

> Hard-won knowledge from debugging sessions and production issues.
> Read this before implementing anything performance-sensitive or touching the LLM pipeline.
> Newest first.

---

## The 367-Second Timeout Mystery
**When:** 2026-02-14 — **Source:** OpenClaw docs crawl session  
**Symptom:** Many chunks finished in exactly 367.0 seconds. Looked like a weird fixed timeout but didn't match any configured value.

**Root cause:** `cleanup_markdown()` had 3 retries with exponential backoff. Each attempt hit the 120s timeout: `120 + 2 + 120 + 5 + 120 = 367s`. Every chunk that failed was burning ~6 minutes in retries that would never succeed.

**Fix:** Reduced retries from 3 to 2 (MAX_RETRIES). Added dynamic timeout based on chunk size instead of fixed 120s. Cap at 90s. The insight: if a chunk can't be cleaned in 90s, a retry won't help either — the problem is the chunk, not the network.

**Lesson:** When you see suspiciously consistent timing in logs, check for retry × timeout multiplication. Log the retry count alongside duration.

---

## 57 Chunks Per Page — The Pre-Cleaning Gap
**When:** 2026-02-14 — **Source:** OpenClaw docs crawl  
**Symptom:** A single page generated 57-87 chunks. Each chunk took 50-370 seconds. One page took ~4 hours.

**Root cause:** `html_to_markdown()` was converting the *entire* page HTML including Mintlify framework JS, CSS inline styles, Next.js hydration code, and navigation chrome. This noise inflated the markdown 5-10x, generating dozens of junk chunks that the LLM couldn't meaningfully clean.

**Fix:** DOM pre-cleaning in two phases:
1. Playwright JS removes noise elements before extraction (`NOISE_SELECTORS` list)
2. Content extraction tries `main`, `article`, `[role='main']` before falling back to `body`
3. Post-conversion regex removes line-level noise (On this page, Edit this page, etc.)

**Result:** Same pages now produce 8-15 chunks. Total crawl time dropped from hours to minutes.

**Lesson:** HTML pre-cleaning is the highest-leverage optimization in the entire pipeline. Always clean before converting, not after. The LLM should never see framework noise.

---

## Oversized Models for Mechanical Tasks
**When:** 2026-02-14 — **Source:** Performance analysis  
**Symptom:** Using qwen3:14b for URL filtering (a simple classification task) was slow and wasteful.

**Root cause:** URL filtering just needs to decide "is this URL a documentation page?" — it's a mechanical task that mistral:7b handles perfectly. qwen3:14b has unnecessary overhead for this (larger context loading, slower inference per token).

**Fix:** Three model roles (ADR-007). Match model size to task complexity.

**Lesson:** Don't use a reasoning model for mechanical tasks. The cost isn't just tokens — it's seconds per inference call multiplied by hundreds of URLs.

---

## SSE Crashes on Client Disconnect
**When:** 2026-02-14 — **Source:** Job monitoring during long crawls  
**Symptom:** "Connection lost" in the frontend, followed by server crash with "ASGI callable returned without completing response." Uvicorn restarts, losing all in-memory job state.

**Root cause:** When an LLM call takes 120s+ and the browser tab disconnects, `sse-starlette` closes the async generator via `GeneratorExit`. But the generator was inside a `wait_for` on the event queue, and the `GeneratorExit` wasn't being caught properly. This left the ASGI response in an incomplete state, which Uvicorn treated as fatal.

**Fix:**
1. Explicit `except GeneratorExit` in `event_stream()` — log and exit cleanly
2. Keepalive pings every 15s (prevents proxy/browser timeout disconnects)
3. Dead task detection: if the runner task dies without emitting a terminal event, `event_stream()` detects via `_task.done()` and emits `job_done` with error
4. Frontend auto-reconnect with exponential backoff

**Lesson:** SSE with long-running backend operations is fragile. Always handle `GeneratorExit`, always ping, and always detect dead tasks. The client *will* disconnect during long operations.

---

## Docker Networking: localhost vs Service Names
**When:** 2026-02-12 — **Source:** Cloudflare tunnel setup  
**Symptom:** Cloudflared container couldn't reach docrawl with `localhost:8002`.

**Root cause:** Inside Docker Compose, each container has its own network namespace. `localhost` inside the cloudflared container refers to cloudflared itself, not the docrawl container. Must use the Docker service name `docrawl:8002`.

**Fix:** VPC Service configuration points to `docrawl:8002`, not `localhost:8002`.

**Lesson:** In docker-compose, sibling services are always reached by service name, never localhost. This applies to Ollama too (`host.docker.internal:11434` to reach the host).

---

## Ollama Silent Truncation (num_ctx)
**When:** 2026-02-14 — **Source:** Cleanup quality analysis  
**Symptom:** LLM cleanup was producing garbage or truncated output for larger chunks, but worked fine for small ones.

**Root cause:** Ollama's default context window (2048-4096 depending on model) is smaller than many chunks. When input exceeds `num_ctx`, Ollama silently truncates — no error, no warning, just bad output.

**Fix:** Dynamic `num_ctx` in cleanup options, sized to the actual chunk content plus overhead. Formula: `max(2048, estimated_input_tokens + 1024)`.

**Lesson:** Always pass explicit `num_ctx` to Ollama. Never trust the model default. If output quality suddenly degrades for larger inputs, suspect context window truncation first.

---

## NVIDIA Sitemap: Invalid XML Doesn't Mean No URLs
**When:** 2026-02-15 — **Source:** NVIDIA docs testing  
**Symptom:** Discovery failed for NVIDIA docs. Logs showed "Invalid XML in sitemap" for several sitemap files.

**Root cause:** NVIDIA's sitemap index contains multiple sitemap URLs. Some are valid, some have malformed XML. The parser was failing on the first bad sitemap and aborting entirely.

**Fix:** Per-sitemap try/catch. Log warning for bad sitemaps, continue with the rest. Also handle gzipped sitemaps (`.xml.gz`) and 404s gracefully.

**Lesson:** Never let one bad sitemap kill the entire discovery. Parse defensively, log failures, continue with what works. Use `defusedxml` for XXE-safe parsing.

---

## Wrangler 3 vs 4: VPC Service Bindings
**When:** 2026-02-12 — **Source:** Cloudflare Workers deployment  
**Symptom:** `wrangler deploy` showed "Unexpected fields" warning and "No bindings found" for VPC Services.

**Root cause:** VPC Service bindings (`vpc_services` in wrangler config) require Wrangler 4.x. Wrangler 3.x silently ignores the field.

**Fix:** Pin `wrangler: "^4.0.0"` in package.json.

**Lesson:** When a Cloudflare feature doesn't work, check the Wrangler version first. New binding types often require the latest major version.

---

## Markdown Wrapped in Code Fences
**When:** 2026-02-14 — **Source:** OpenClaw docs output evaluation  
**Symptom:** 21 of 27 scraped files had their content wrapped in ` ```markdown ... ``` ` fences. The markdown wasn't being rendered — it was treated as literal text.

**Root cause:** The LLM cleanup was told to "return only cleaned markdown" but some model responses wrapped the output in code fences (a common LLM behavior when returning code-like content).

**Lesson:** Post-process LLM output to strip code fences if present. Check for `response.startswith("```")` and strip the wrapper. This happens with multiple models, not just one.
