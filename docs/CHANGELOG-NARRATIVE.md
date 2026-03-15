# Project History — Narrative Changelog

> The story of DocRawl from idea to v0.9.10.
> Not a git log — this captures the *why* behind the evolution.

---

## The Beginning (~2026-02-10)

DocRawl started as "doc2md" — a simple idea: point it at a documentation site, get clean Markdown files back. The initial architecture was straightforward: FastAPI backend, Playwright for rendering, markdownify for HTML→MD, and Ollama for LLM cleanup. The first working prototype could crawl a site, convert pages, and produce output.

Early decisions that stuck: FastAPI + SSE for real-time progress, Docker for deployment, and the cascade approach to URL discovery (sitemap → nav parsing → recursive crawl).

**Key conversation:** First architecture discussion defined the pipeline stages and the principle that the LLM should handle planning/filtering while markdownify does the mechanical conversion.

---

## The Performance Crisis (~2026-02-14)

The first real stress test against OpenClaw docs (`docs.openclaw.ai`) exposed severe problems. A single page generated **57 chunks** because framework noise (Mintlify JS, CSS, navigation) wasn't being filtered before conversion. Each chunk took 50-370 seconds with the LLM, and many hit exactly 367 seconds — the signature of retry timeout multiplication (120s × 3 attempts + backoff delays).

One page took approximately 4 hours. A 9-page crawl would have taken over a day.

**The fix was transformative:** DOM pre-cleaning (removing noise elements before conversion) reduced chunks from 57 to ~10-15 per page. Dynamic timeouts replaced the fixed 120s. The `needs_llm_cleanup()` function learned to skip chunks that were already clean (mostly code, or short without noise), eliminating ~40-60% of unnecessary LLM calls.

This was the single biggest insight in the project: **clean the input before the LLM, not with the LLM.**

---

## Multi-Model Architecture (~2026-02-14)

Testing revealed that using one model for everything was wasteful. URL filtering is a simple classification task — mistral:7b handles it perfectly. Markdown cleanup needs better language understanding — qwen3:14b is appropriate. Using qwen3:14b for everything was like using a truck to deliver a letter.

The three-model-role system was introduced: `crawl_model`, `pipeline_model`, `reasoning_model`. The UI was updated with three selectors, each with hints about what model size fits. `reasoning_model` was reserved for future use (site structure analysis, complex content decisions).

---

## SSE Stability & Server Crashes (~2026-02-14)

During long crawls, the SSE connection would drop and the server would crash with ASGI protocol violations. The root cause was subtle: when an LLM call takes 120s+ and the browser disconnects, `sse-starlette` throws `GeneratorExit` into the async generator. But the generator was awaiting the event queue, and the exception propagated incorrectly.

The fix required understanding the ASGI lifecycle: explicit `GeneratorExit` handling, keepalive pings, and dead-task detection. Frontend auto-reconnect with exponential backoff completed the solution.

---

## Discovery Improvements (~2026-02-15)

Testing against multiple doc sites (Flask, Requests, Pydantic, NVIDIA) revealed that the discovery cascade wasn't robust enough. NVIDIA's sitemaps had invalid XML that crashed the parser. Nav parsing timeouts were too long (15s → 10s). Sites with 100+ sitemap URLs didn't need nav parsing but were doing it anyway.

Defensive improvements: per-sitemap try/catch, `defusedxml` for XXE-safe parsing, URL caps, smart strategy skipping, and parallel BFS with jitter for rate limiting.

---

## Multi-Provider LLM Support (~2026-02-18)

Ollama was the only backend initially. OpenRouter and OpenCode were added as cloud providers, enabling access to a wider range of models. The routing logic is simple: bare model names → Ollama, `namespace/model` → check prefix against provider registry.

Free-tier models on OpenRouter (`:free` suffix) made the tool accessible without local GPU hardware.

---

## Cloudflare Tunnel & Workers VPC (~2026-02-12)

Internet exposure via Cloudflare Tunnel was added for remote access. The initial implementation had a wrong architecture (Worker proxying to public tunnel URL instead of using VPC Service bindings). The correct pattern: tunnel with no public hostname, Worker uses `env.VPC_SERVICE.fetch()` to reach the service internally.

A Wrangler 3 vs 4 version issue caused silent binding failures — VPC Services require Wrangler 4.x.

---

## The Roadmap: v0.9.7 → v0.9.10 (~2026-03)

A comprehensive research session analyzed the tooling landscape and identified 15 improvement areas. These were organized into 3 milestones with 14 PRs:

**Milestone 1 (v0.9.8) — Quick Wins:** Docker hardening, PagePool, HTTP fast-path, parallel discovery, job TTL cleanup.

**Milestone 2 (v0.9.9) — Scraping & Pipeline:** Semantic chunking, heavy cleanup for tables/LaTeX, content dedup, disk cache, adaptive token estimation.

**Milestone 3 (v0.9.10) — Advanced Features:** Pause/resume, structured JSON output, producer/consumer pipeline, converter plugins.

All 14 PRs have been implemented and merged. The project is now at v0.9.10.

---

## Current State (v0.9.10, 2026-03-07)

DocRawl is a functional self-hosted documentation scraper with:
- 4 LLM providers (Ollama, LM Studio, OpenRouter, OpenCode)
- 4-stage scraping fallback (native MD → proxy → HTTP fast → Playwright)
- PagePool for browser page reuse
- Semantic chunking by headings
- Pause/resume with state checkpoints
- Structured JSON output option
- Converter plugin system
- Content dedup and blocked-response detection
- Per-job disk cache
- Docker deployment with Cloudflare tunnel support
- Synthwave-themed UI

**What's next:** See OPEN-QUESTIONS.md for unresolved items and potential future directions.
