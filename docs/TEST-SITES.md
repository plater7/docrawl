# Test Sites Reference

> Documentation sites used for testing, with known behaviors and gotchas.
> Difficulty: Easy → Medium → Hard → Extreme.

---

## 1. httpx docs (Easy)
**URL:** `https://www.python-httpx.org/`  
**Generator:** MkDocs  
**Pages:** ~20-30  
**Sitemap:** Clean, authoritative  

**Why it's easy:** Static HTML, simple structure, few pages, no JS rendering needed. Ideal baseline for validating the pipeline works at all.

**Good for testing:** Pool saturation (`PAGE_POOL_SIZE=2, max_concurrent=3`), basic fallback chain, chunk counts.

---

## 2. FastAPI docs (Medium)
**URL:** `https://fastapi.tiangolo.com/`  
**Generator:** MkDocs  
**Pages:** 100+  
**Sitemap:** Available, multi-language  

**Why it's medium:** Large enough to exercise concurrency and memory. Has multiple languages (good test for language filter). Interactive code examples with tabs.

**Known behaviors:**
- Language filter must be set to `en` or you get every translation
- Some pages have dynamic tabs that Playwright captures but HTTP fast-path doesn't

**Good for testing:** Pool size == max_concurrent, SSE stability over long runs, language filtering, memory stability.

---

## 3. Stripe docs (Hard)
**URL:** `https://docs.stripe.com/`  
**Generator:** Custom (React/Next.js)  
**Pages:** 500+  
**Sitemap:** Available but massive  

**Why it's hard:** Heavy JS rendering, dynamic content loading, conditional content by tabs, massive URL count. Exercises every part of the pipeline.

**Known behaviors:**
- Pages crash Playwright occasionally (JS memory pressure) — good for testing page pool auto-replacement
- Some content loads lazily and isn't available at `networkidle`
- API reference section is huge — make sure the filter excludes it unless wanted

**Good for testing:** Page pool resilience, memory leak detection, blocked response detection, content dedup.

---

## 4. Cloudflare docs (Extreme)
**URL:** `https://developers.cloudflare.com/`  
**Generator:** Custom  
**Pages:** Thousands (multiple products)  
**Sitemap:** Sitemap index with nested sitemaps  

**Why it's extreme:** Supports `Accept: text/markdown` content negotiation — the only test site that exercises `fetch_markdown_native()`. Enormous scope with multiple product sections. Sitemap index with sub-sitemaps tests recursive sitemap parsing.

**Known behaviors:**
- Native markdown endpoint returns `text/markdown` content-type with `x-markdown-tokens` header
- Some sub-sitemaps may have different formats
- Use `filter_sitemap_by_path: true` to scope to a specific product section, or the crawl will attempt thousands of pages

**Good for testing:** Native markdown path, sitemap index parsing, path filtering, massive URL volume.

---

## 5. NVIDIA docs (Edge Case)
**URL:** `https://docs.nvidia.com/`  
**Generator:** Custom  
**Pages:** Varies by section  

**Known behaviors:**
- Some sitemap files have **invalid XML** — parser must handle gracefully
- Sitemap references URLs that return 404
- Works at `max_depth=2` but may timeout at `max_depth=3`
- Test with defensive sitemap parsing (defusedxml)

**Good for testing:** XML error handling, 404 tolerance, depth sensitivity.

---

## 6. OpenClaw docs (Edge Case)
**URL:** `https://docs.openclaw.ai/`  
**Generator:** Mintlify  
**Pages:** ~27 (concepts section)  

**Known behaviors:**
- Framework noise from Mintlify is extreme (JS hydration, inline CSS)
- **This was the site that caused the 57-chunks-per-page crisis** — see LESSONS.md
- Code blocks in some pages load dynamically and may appear empty if scraped without waiting
- Output may be wrapped in ` ```markdown ``` ` fences by the LLM

**Good for testing:** DOM pre-cleaning effectiveness, chunk count comparison before/after, LLM output post-processing.

---

## 7. Requests docs (Regression)
**URL:** `https://requests.readthedocs.io/`  
**Generator:** Sphinx/ReadTheDocs  

**Known behaviors:**
- Was the first site to pass after discovery fixes
- Clean Sphinx output, good baseline for regression testing

---

## Configuration Matrix for Pool Testing

| Config | Pool | Concurrent | What it tests |
|--------|------|-----------|--------------|
| Saturation | 2 | 3 | Workers waiting on pool queue |
| Balanced | 5 | 5 | 1:1 page:worker ratio |
| Legacy | 0 | 3 | Pool disabled, old create/close path |
| Serialized | 1 | 3 | Forced bottleneck |
| Oversized | 10 | 2 | Idle pages in queue |
