# Architecture

> DocRawl v0.9.10 — Documentation Crawler with LLM-powered cleanup

## Overview

DocRawl is a FastAPI service that crawls documentation websites and produces clean Markdown (or structured JSON) output. It combines multi-strategy URL discovery, a 5-level scraping fallback chain, and LLM-based content cleanup to handle the full spectrum of documentation sites — from static HTML to JS-rendered SPAs.

The system runs as a Docker container exposing a REST API + SSE event stream, with a synthwave-themed web UI for interactive use.

## Pipeline

```
                         ┌─────────────────────────────────────────────┐
                         │              FastAPI Application            │
                         │  src/main.py — lifespan, middleware, auth   │
                         └──────────────────┬──────────────────────────┘
                                            │
                                    POST /api/jobs
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │              Job Manager (src/jobs/manager.py)│
                    │  Creates Job, tracks state, cleanup loop      │
                    └──────────────────┬────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        Job Runner (src/jobs/runner.py)                    │
│                        ═══════════════════════════════                    │
│                                                                          │
│  ┌─── Phase 1: INIT ───────────────────────────────────────────────┐     │
│  │  • Validate models (crawl, pipeline, reasoning)                 │     │
│  │  • Start Playwright browser                                     │     │
│  │  • Load robots.txt + crawl-delay                                │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                           │
│                              ▼                                           │
│  ┌─── Phase 2: DISCOVERY ──────────────────────────────────────────┐     │
│  │  src/crawler/discovery.py — 3 strategies (parallel fallback):   │     │
│  │                                                                 │     │
│  │  1. Sitemap parsing (/sitemap.xml, sitemap index, robots.txt    │     │
│  │     Sitemap: directive) — with gzip, nested sitemap, caching    │     │
│  │  2. Nav parsing (Playwright) — JS-rendered nav/aside/sidebar    │     │
│  │  3. Recursive BFS crawl — parallel per-depth, 1000 URL cap     │     │
│  │                                                                 │     │
│  │  All strategies: URL normalization, same-domain filter,         │     │
│  │  dedup, SSRF validation                                        │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                           │
│                              ▼                                           │
│  ┌─── Phase 3: FILTERING ─────────────────────────────────────────┐     │
│  │  a) Deterministic (src/crawler/filter.py):                      │     │
│  │     • Extension blocklist (.pdf, .zip, .png, etc.)              │     │
│  │     • Pattern blocklist (/blog/, /changelog/, /releases/)       │     │
│  │     • Language filtering (en/es/fr/de/ja/zh/pt/ru/ko)          │     │
│  │     • Same-domain + subpath enforcement                         │     │
│  │                                                                 │     │
│  │  b) robots.txt filtering (src/crawler/robots.py)                │     │
│  │                                                                 │     │
│  │  c) LLM filtering (src/llm/filter.py):                         │     │
│  │     • Batch URL classification with crawl_model                 │     │
│  │     • Removes non-documentation URLs the heuristics miss        │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                           │
│                              ▼                                           │
│  ┌─── Phase 4: SCRAPING ──────────────────────────────────────────┐     │
│  │  5-level fallback chain (src/scraper/page.py):                  │     │
│  │                                                                 │     │
│  │  1. Cache         — PageCache disk lookup (24h TTL, opt-in)     │     │
│  │  2. Native MD     — Accept: text/markdown content negotiation   │     │
│  │  3. Proxy MD      — markdown.new / r.jina.ai proxy service     │     │
│  │  4. HTTP fast-path — plain httpx GET + markdownify (>=500ch)    │     │
│  │  5. Playwright    — full browser render + DOM noise removal     │     │
│  │                     via PagePool (asyncio.Queue, reusable pages) │     │
│  │                                                                 │     │
│  │  Post-scrape checks:                                            │     │
│  │  • Bot-detection (is_blocked_response) — skip blocked pages     │     │
│  │  • Content dedup (content_hash) — skip near-identical pages     │     │
│  │  • Converter plugin (src/scraper/converters/) — HTML→MD         │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                           │
│                              ▼                                           │
│  ┌─── Phase 5: CLEANUP ───────────────────────────────────────────┐     │
│  │  src/llm/cleanup.py — 3-tier classification:                    │     │
│  │                                                                 │     │
│  │  • "skip"   — code-heavy (>60% density) or short clean text     │     │
│  │  • "cleanup" — standard LLM cleanup (nav residue, footers)     │     │
│  │  • "heavy"  — cleanup + table repair + LaTeX fix                │     │
│  │                                                                 │     │
│  │  Features:                                                      │     │
│  │  • Dynamic timeout (BASE_TIMEOUT + tokens/250 * 10, max 90s)   │     │
│  │  • Adaptive context window (num_ctx sized to actual content)    │     │
│  │  • Code-density-adjusted token estimation (3.0/3.5/4.0 ratio)  │     │
│  │  • Exponential backoff retry (1s, 2s, 4s — 3 attempts)         │     │
│  │  • XML-wrapped input to isolate scraped data from prompt        │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                           │
│                              ▼                                           │
│  ┌─── Phase 6: OUTPUT ────────────────────────────────────────────┐     │
│  │  Two formats (per JobRequest.output_format):                    │     │
│  │                                                                 │     │
│  │  • "markdown" — chunked .md files (src/scraper/markdown.py)    │     │
│  │  • "json"     — structured JSON with content blocks             │     │
│  │                 (src/scraper/structured.py — StructuredPage)    │     │
│  │                                                                 │     │
│  │  Checkpoint: save_job_state() after each page for pause/resume  │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Module Map

### `src/api/` — REST API Layer
| File | Responsibility |
|------|---------------|
| `models.py` | Pydantic request/response models. `JobRequest` (20+ fields), `ResumeFromStateRequest`, `JobStatus`, `OllamaModel`. Input validation includes path traversal prevention and SSRF checks. |
| `routes.py` | FastAPI router: CRUD for jobs, SSE event stream, model/provider listing, converter listing, health check, pause/resume endpoints. Rate-limited via slowapi. |

### `src/crawler/` — URL Discovery and Filtering
| File | Responsibility |
|------|---------------|
| `discovery.py` | 3-strategy URL discovery: `try_sitemap()` (XML parsing, gzip, sitemap index, caching), `try_nav_parse()` (Playwright nav/sidebar extraction), `recursive_crawl()` (parallel BFS, depth-limited). Orchestrated by `discover_urls()`. |
| `filter.py` | Deterministic URL filtering: extension blocklist, pattern blocklist, language filtering (9 languages), same-domain enforcement. |
| `robots.py` | Simple robots.txt parser: Disallow rules + crawl-delay. Note: does not support `Allow:` directive yet (known limitation). |

### `src/jobs/` — Job Lifecycle
| File | Responsibility |
|------|---------------|
| `manager.py` | `JobManager` — creates, tracks, cancels jobs. Manages `PagePool` lifecycle. Background cleanup loop removes expired completed jobs. Concurrency limit via `MAX_CONCURRENT_JOBS`. |
| `runner.py` | `run_job()` — the 1102-line heart of the pipeline. Orchestrates all phases sequentially, manages concurrent page processing via `asyncio.Semaphore`, emits SSE events, handles pause/resume. |
| `state.py` | Checkpoint persistence: atomic write (`.tmp` -> `os.replace`) of `JobState` (completed/failed/pending URL lists). Enables pause/resume across process restarts. |

### `src/llm/` — LLM Integration
| File | Responsibility |
|------|---------------|
| `client.py` | Multi-provider LLM client: Ollama (local), OpenRouter (cloud), OpenCode (cloud), LM Studio (local). Model caching (60s TTL), provider auto-detection from model name prefix. Core `generate()` function used by cleanup and filter. |
| `cleanup.py` | 3-tier markdown cleanup (skip/cleanup/heavy). Smart heuristics: code density, noise indicators, broken table detection, LaTeX detection. Dynamic timeouts and context windows. |
| `filter.py` | LLM-based URL filtering: batch classification of URLs as documentation vs non-documentation using the crawl model. |

### `src/scraper/` — Content Extraction
| File | Responsibility |
|------|---------------|
| `page.py` | `PageScraper` (Playwright-based HTML extraction with DOM noise removal), `PagePool` (reusable page pool via `asyncio.Queue`), `fetch_markdown_native()`, `fetch_markdown_proxy()`, `fetch_html_fast()` — the first 4 levels of the fallback chain. |
| `markdown.py` | `chunk_markdown()` — splits large markdown into chunks for LLM processing, respecting heading boundaries. |
| `cache.py` | `PageCache` — disk-based HTML cache with 24h TTL. Opt-in via `use_cache=True`. Non-gzipped content only. |
| `detection.py` | `is_blocked_response()` — detects bot-check/captcha pages. `content_hash()` — SHA-256 based dedup. |
| `structured.py` | `StructuredPage` / `ContentBlock` — structured JSON output format. `html_to_structured()` preserves document hierarchy. |
| `converters/` | Plugin system: `MarkdownConverter` Protocol + registry. Default: `MarkdownifyConverter`. Extensible via `register_converter()`. |

### `src/utils/`
| File | Responsibility |
|------|---------------|
| `security.py` | `validate_url_not_ssrf()` — blocks URLs resolving to private/reserved networks (127.0.0.0/8, 10.0.0.0/8, 169.254.0.0/16, etc.). Used before every HTTP request and Playwright navigation. |

### `src/main.py` — Application Entry Point
FastAPI app with:
- **Lifespan**: PagePool initialization, background cleanup task, graceful shutdown
- **Middleware stack**: CORS (env-configured), security headers (CSP, X-Frame-Options, etc.), API key auth (optional, via `X-Api-Key` header)
- **Structured logging**: JSON formatter for all log output
- **Global error handler**: sanitized 500 responses (never leaks internals)

## Key Design Decisions

> Formal ADRs for these decisions are in [`docs/adr/`](docs/adr/).

### 5-Level Scraping Fallback Chain
**Why 5 levels?** Documentation sites range from static HTML (where httpx suffices) to heavy JS SPAs (requiring full Playwright). Each level is cheaper/faster than the next. The chain tries the lightest approach first and escalates only on failure, optimizing for the common case while handling edge cases.

### PagePool with asyncio.Queue
**Why?** Creating/closing a Playwright page per URL is expensive (~200ms overhead). The pool pre-warms N pages and reuses them via `asyncio.Queue`, with automatic replacement of broken pages. This cut scraping time by ~40% in benchmarks.

### 3-Tier LLM Cleanup Classification
**Why not just send everything to the LLM?** Code-heavy chunks and short clean text don't benefit from LLM cleanup — they're already clean. The 3-tier classifier (skip/cleanup/heavy) avoids wasting LLM tokens on content that doesn't need it, reducing costs and latency by ~30%.

### Multi-Provider LLM Support
**Why?** Flexibility. Local models (Ollama, LM Studio) for development/privacy, cloud models (OpenRouter, OpenCode) for production quality. Provider auto-detected from model name prefix (e.g., `opencode/claude-sonnet-4-5` routes to OpenCode).

### Checkpoint-Based Pause/Resume
**Why atomic writes?** A crawl job can process hundreds of URLs over minutes/hours. Crashes shouldn't lose progress. The state file uses `.tmp` -> `os.replace()` for crash safety. Resume creates a new job with only pending URLs.

### Converter Plugin System
**Why a Protocol instead of ABC?** Structural subtyping via `@runtime_checkable` Protocol means any class with `convert()`, `supports_tables()`, and `supports_code_blocks()` methods works — no inheritance required. Simplifies third-party converter integration.

## Infrastructure

### Docker
- Multi-stage build: Python deps + Playwright browser install
- `PAGE_POOL_SIZE` env var controls browser page pool (default: 5, 0 = disabled)
- `/data` volume for output files and cache

### CI/CD (11 GitHub Actions workflows)
- **Quality**: lint (ruff), test (pytest + coverage), security (pip-audit + Snyk), CodeQL
- **Build**: Docker build + publish to GHCR
- **Release**: auto-tag on version bump, changelog generation, SNAPSHOT regeneration
- **Maintenance**: stale issue cleanup, docs update on merge

### Security Layers
- SSRF validation on all URLs (before httpx and Playwright)
- Input validation via Pydantic (path traversal, URL scheme enforcement)
- Rate limiting (slowapi — 10 jobs/min)
- API key authentication (optional)
- Security headers middleware (CSP, X-Frame-Options, Referrer-Policy)
- XML input wrapping for LLM prompts (prompt injection mitigation)
- defusedxml for sitemap parsing (XXE prevention)
- Sanitized error responses (never expose stack traces)

---

*This document describes DocRawl v0.9.10. For the full code snapshot, see `SNAPSHOT.md`.*
