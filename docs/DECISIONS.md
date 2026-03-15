# Architecture Decisions

> Key design choices and their rationale. Newest first.
> Format: What was decided, why, what was the alternative, what's the trade-off.

---

## ADR-011: Converter Plugin System via Protocol
**Date:** 2026-03 (PR 3.4) — **Status:** Implemented

**Decision:** HTML→Markdown conversion extracted behind a `MarkdownConverter` Protocol with a static registry (`get_converter`, `register_converter`). Default: markdownify.

**Why:** Different doc sites have wildly different HTML patterns. Stripe API reference vs Cloudflare tutorials need different conversion logic. Protocol is lightweight, no runtime cost, and the registry makes it testable.

**Alternative considered:** Subclassing a base class. Rejected because Protocol + `@runtime_checkable` is more Pythonic and doesn't require inheritance.

---

## ADR-010: Pause/Resume via State File Checkpoint
**Date:** 2026-03 (PR 3.1) — **Status:** Implemented

**Decision:** Jobs checkpoint to `.job_state.json` on pause. Resume creates a *new* job with only the pending URLs — does not reattach to the old job object.

**Why:** Long crawls (500+ URLs) take hours. Users need to pause without losing progress. New-job-on-resume is simpler than rehydrating an in-memory `Job` dataclass, and handles server restarts between pause and resume.

**Trade-off:** Sites may change between pause and resume. Some URLs may 404 on resume — those get logged as `failed_urls`, which is acceptable. Atomic write (`.tmp` → `os.replace`) prevents corrupt state files on crash.

---

## ADR-009: HTTP Fast-Path Before Playwright
**Date:** 2026-03 (PR 1.3) — **Status:** Implemented

**Decision:** Plain HTTP GET via httpx (8s timeout) tried after native markdown and proxy, but before Playwright. If response has ≥500 chars of markdown after conversion, Playwright is skipped entirely.

**Why:** Most documentation sites (MkDocs, Docusaurus, Hugo, Sphinx) are server-rendered. Skipping Playwright saves ~2-5s per page and significant memory. 500-char threshold is conservative — JS-rendered shells return <200 chars of meaningful content and correctly fall through.

**Alternative considered:** Always try Playwright. Rejected because for 200+ URL crawls the overhead adds up to minutes.

---

## ADR-008: PagePool with asyncio.Queue
**Date:** 2026-03 (PR 1.2 / PR #137) — **Status:** Implemented

**Decision:** Pre-create N Playwright pages at startup, manage via `asyncio.Queue`. Pages reset (about:blank + clear cookies) between uses. `PAGE_POOL_SIZE=0` disables pool entirely (legacy fallback). Broken pages auto-replace.

**Why:** Creating a new Playwright page per URL adds ~200-500ms overhead. With 200+ URLs, that's minutes of waste. Pool size is independent of `max_concurrent` — can have more or fewer pages than workers.

**Key learning from PR #137 testing:** Pool saturation (`pool_size < max_concurrent`) works correctly — extra workers just wait on the queue without deadlock.

---

## ADR-007: Three Model Roles
**Date:** 2026-02 — **Status:** Implemented

**Decision:** `crawl_model` (URL filtering), `pipeline_model` (markdown cleanup), `reasoning_model` (reserved). Each role uses a different model optimized for its task.

**Why:** URL filtering is lightweight classification — mistral:7b handles it fine at high speed. Markdown cleanup needs better language understanding — qwen3:14b is appropriate. Using qwen3:14b for URL filtering wastes inference time. Using mistral:7b for cleanup produces lower quality.

**The disaster that motivated this:** First version used a single model (qwen3:14b) for everything. Cleanup of 57 chunks per page with 367-second timeouts. See LESSONS.md "The 367-second timeout mystery."

**Recommended defaults:** crawl → mistral:7b, pipeline → qwen3:14b, reasoning → deepseek-r1:32b (unused today).

---

## ADR-006: URL Discovery Cascade (Sitemap → Nav → BFS)
**Date:** 2026-02 — **Status:** Implemented

**Decision:** Three strategies tried in order. Stops at first success. Sitemap (fast, authoritative) → Nav parsing via Playwright (JS-rendered menus) → Recursive BFS crawl (last resort).

**Why:** Sitemap is ideal when available. Nav parsing catches single-page apps where links are rendered by JS. BFS is the universal fallback but slow and noisy.

**Key behaviors:** Nav parsing has 10s timeout and 100-URL cap. BFS has 1000-URL safety cap. Parallel BFS (PR 1.4) uses `asyncio.Semaphore` for concurrency with jitter to mitigate rate limiting. Smart skip: if sitemap finds 100+ URLs, nav parsing is skipped.

---

## ADR-005: SSE for Job Progress (not WebSocket)
**Date:** 2026-02 — **Status:** Implemented

**Decision:** Server-Sent Events via `sse-starlette` with `asyncio.Queue` per job. Ping every 15s. Frontend auto-reconnects.

**Why:** SSE is simpler than WebSocket for unidirectional server→client events. No need for client→server messages during a job. `sse-starlette` handles the ASGI lifecycle.

**Critical caveat:** Long LLM operations (120s+ timeouts) can cause `GeneratorExit` mishandling when clients disconnect during a chunk, leading to ASGI protocol violations and server crashes. Fixed with proper error boundaries and keepalive pings. See LESSONS.md "SSE crashes on client disconnect."

---

## ADR-004: Dynamic Timeouts for LLM Calls
**Date:** 2026-02 — **Status:** Implemented

**Decision:** `BASE_TIMEOUT=45s + TIMEOUT_PER_KB=10s`, capped at `MAX_TIMEOUT=90s`. Token estimation uses code-density-adjusted ratios (3.0 for code, 3.5 mixed, 4.0 prose) instead of flat `len(text)//4`.

**Why:** Fixed 120s timeout caused two problems: small chunks waited too long on failure, large chunks timed out prematurely. Dynamic timeout scales with actual content.

---

## ADR-003: DOM Pre-Cleaning Before Conversion
**Date:** 2026-02 — **Status:** Implemented

**Decision:** Remove noise elements (nav, footer, sidebar, script, style, cookie banners, framework chrome) from the DOM *before* running markdownify. Two-phase: Playwright JS removes elements, then regex post-clean removes line-level noise.

**Why:** Without pre-cleaning, a single page could generate 57-87 chunks because framework noise (Mintlify JS, Next.js hydration, CSS) inflated the HTML. After pre-cleaning, same pages produce 8-15 chunks. This was the single biggest performance improvement in the project's history.

---

## ADR-002: Opt-in Features with Sensible Defaults
**Date:** 2026-02 — **Status:** Principle

**Decision:** Every new feature is opt-in with a default that preserves existing behavior. New `JobRequest` fields always have defaults. If a new feature fails, fall back to the previous behavior silently.

**Why:** Users shouldn't need to reconfigure after an upgrade. Breaking changes destroy trust. "Simplicity wins" — the project philosophy.

**Examples:** `use_http_fast_path=True` (safe default, falls through to Playwright), `use_cache=False` (off by default), `PAGE_POOL_SIZE=5` (on by default but `=0` disables), `output_format="markdown"` (JSON is opt-in).

---

## ADR-001: Self-Hosted, Local-First
**Date:** 2026-02 — **Status:** Principle

**Decision:** DocRawl runs entirely on the user's machine. LLM inference via Ollama (local). Cloud providers (OpenRouter, OpenCode) are optional add-ons. No data leaves the machine unless the user explicitly configures a cloud provider or Cloudflare tunnel.

**Why:** Documentation scraping may involve proprietary/internal docs. Users must trust that their content isn't sent to third parties by default.
