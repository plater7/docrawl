# Open Questions & Unresolved Items

> Things deferred, undecided, or identified but not yet implemented.
> Check here before planning new work — it might already be on the radar.

---

## Unimplemented Ideas (Identified in Research)

### Two-Phase Scraping with Quality Gate
**Source:** Research session (2026-03-02)  
**Idea:** HTTP fast-path already exists, but a more sophisticated approach: first fetch via HTTP, score the content quality (text density, heading structure, code block count), and only fall through to Playwright if the score is below a threshold.  
**Why deferred:** Current binary approach (≥500 chars → accept) works well enough. Quality scoring adds complexity.  
**Priority:** Low — revisit if users report pages where HTTP fast-path produces bad output.

### Improved Table Handling
**Source:** Research session, PR 2.2 analysis  
**Idea:** Microsoft's Table Transformer Detection model for detecting table structure in complex HTML. Also, custom markdownify overrides for nested tables, colspan/rowspan.  
**Why deferred:** Table Transformer is overkill for HTML tables (they already have DOM structure). The real problem is tables that markdownify renders poorly — a custom converter plugin (ADR-011) is the better fix.  
**Priority:** Medium — table-heavy docs (API references) still produce messy output.

### Auto-Prompt Optimization
**Source:** Research session (auto-prompt tooling)  
**Idea:** Use auto-prompt or similar tools to optimize the hardcoded prompts in `cleanup.py` and `filter.py`. Currently the prompts were hand-tuned.  
**Priority:** Low — prompts work well enough. Would be a good optimization pass once the core pipeline is stable.

### Groq / Gemini as LLM Providers
**Source:** Performance discussion (2026-02-14)  
**Idea:** Groq for extremely fast inference (cleanup at cloud speed), Gemini for large context windows.  
**Why deferred:** Adding more providers is easy (same OpenAI-compatible API) but each needs testing and error handling. Ollama + OpenRouter covers most use cases.  
**Priority:** Low — revisit when there's user demand.

### Producer/Consumer Pipeline Mode
**Source:** PR 3.3
**Status:** ✅ Implemented. `use_pipeline_mode: true` activates the producer/consumer pipeline in `runner.py`. Scraping and cleanup are decoupled with backpressure control.
**Priority:** N/A — implemented.

---

## Known Gaps

### reasoning_model is Reserved
**Impact:** Low
`reasoning_model` is carried through the pipeline but intentionally unused in the current version. It is reserved for future pipeline stages (site structure analysis, quality assessment). See ADR-012 in `docs/DECISIONS.md`. Must be set to a valid model identifier when provided, but has no effect on current crawl behavior.

### No Metrics/Observability Beyond Logs
**Impact:** Medium  
JSON structured logging exists (PR #109) but there's no metrics collection (Prometheus, StatsD, etc.). For a self-hosted tool this is fine, but as usage grows, understanding job distribution, failure rates, and model performance would be valuable.

### Cloudflare Workers VPC Not Fully Verified
**Impact:** Low (optional feature)  
The tunnel + Workers VPC architecture was designed and partially implemented, but the last test had `ProxyError: connection_refused` that wasn't fully resolved. Need to verify the complete flow end-to-end.

### Cache Invalidation
**Impact:** Low  
The page cache (PR 2.4) has a 24h TTL but no way to invalidate specific entries. If a doc site updates a page, the cache serves stale content until TTL expires. For a documentation scraper this is usually fine (you're doing a one-time crawl), but repeat crawls of the same site within 24h get stale data.

---

## Questions to Resolve

- **Should the UI support dark/light mode toggle?** Currently hardcoded synthwave theme.
- **Should there be a CLI interface** in addition to the web UI? For scripting and CI/CD integration.
- **How should multi-language docs be handled?** Current filter works on URL patterns (`/en/`, `/es/`). Some sites use query params or cookies for language.
- **Should completed job output be browsable from the UI?** Currently you need to look at the filesystem directly.
