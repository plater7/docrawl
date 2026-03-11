# ADR-003: Three-Tier LLM Cleanup Classification

**Status:** Accepted  
**Date:** 2026-01 (retroactive, PR 2.2)  
**Deciders:** plater7

## Context

The original cleanup pipeline sent every markdown chunk to the LLM for cleaning. This was wasteful: code-heavy documentation pages (API references, SDK examples) are already clean and don't benefit from LLM processing. Sending them through the LLM added latency, consumed tokens, and sometimes degraded quality (the LLM would occasionally mangle code blocks).

Additionally, some pages needed *more* than standard cleanup — broken HTML tables and mangled LaTeX expressions required specific repair instructions in the prompt.

## Decision

Implement a 3-tier classification system in `src/llm/cleanup.py`:

| Level | Criteria | Action |
|-------|----------|--------|
| `skip` | Code density >60%, OR short text (<2000 chars) without noise indicators | Pass through unchanged |
| `cleanup` | Has noise indicators (cookie banners, nav residue, etc.) OR long text (>=2000 chars) | Standard LLM cleanup prompt |
| `heavy` | Has broken tables (pipe rows without separator) OR LaTeX expressions | Extended prompt with table repair + LaTeX fix instructions |

**Noise indicators** (16 patterns): cookie, privacy policy, terms of service, subscribe, toggle dark/light, skip to content, table of contents, on this page, all rights reserved, powered by.

**Code density** is calculated as the fraction of content inside fenced code blocks (triple backtick). This is a cheap O(n) regex scan.

**Broken table detection**: looks for pipe-separated rows (`|...|`) without a separator row (`|---|---|`). If table rows exist but no separator exists, it's classified as broken.

**LaTeX detection**: matches `\frac{`, `\begin{`, `\end{`, `\command{`, and `$expr$` patterns. Excludes false positives from price strings like `$9.99` by requiring at least one unambiguous LaTeX command match.

## Consequences

**Positive:**
- ~30% reduction in LLM calls (code-heavy and short clean chunks skip the LLM entirely)
- Heavy cleanup produces better results for complex content (tables actually get repaired)
- `classify_chunk()` is pure function, deterministic, easily testable
- Backward-compatible: `needs_llm_cleanup()` wraps `classify_chunk()` for existing callers

**Negative:**
- Heuristic-based — edge cases exist (e.g., a 1999-char chunk with subtle noise gets classified as `skip`)
- LaTeX false positive mitigation is simplistic (price pattern check)
- Adding new noise indicators requires code changes (not configurable)

**Future considerations:**
- The `skip` threshold (2000 chars, 60% code density) could be made configurable via environment variables
- A 4th tier (`extract`) could be added for pages that need content extraction rather than cleanup
