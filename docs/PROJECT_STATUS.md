# Project Status

> DocRawl v0.9.10 -- Last updated: 2026-03-09

## Current State

DocRawl is a **functional documentation crawler** in late beta. The core pipeline (discovery -> filter -> scrape -> cleanup -> output) is stable and handles production workloads. The project has mature CI/CD (13 GitHub Actions workflows), structured logging, security hardening, and a web UI.

### What Works

| Feature | Status | Since |
|---------|--------|-------|
| 3-strategy URL discovery (sitemap, nav parse, recursive crawl) | Stable | v0.7 |
| 5-level scraping fallback chain | Stable | v0.9.8 |
| Multi-provider LLM (Ollama, OpenRouter, OpenCode, LM Studio) | Stable | v0.9.0 |
| 3-tier cleanup classification (skip/cleanup/heavy) | Stable | v0.9.5 |
| Checkpoint pause/resume | Stable | v0.9.6 |
| PagePool (reusable Playwright pages) | Stable | v0.9.3 |
| Structured JSON output | Stable | v0.9.6 |
| Converter plugin system | Stable | v0.9.8 |
| HTTP fast-path (skip Playwright for static sites) | Stable | v0.9.3 |
| Page cache (24h TTL, opt-in) | Stable | v0.9.5 |
| Content dedup (SHA-256 hash) | Stable | v0.9.5 |
| Bot-detection / blocked page skip | Stable | v0.9.5 |
| Synthwave web UI (two-column layout) | Stable | v0.9.9 |
| REST API + SSE event stream | Stable | v0.7 |
| Docker deployment (GHCR) | Stable | v0.8 |
| Security hardening (SSRF, CSP, rate limiting, API key auth) | Stable | v0.9.0 |
| Structured JSON logging | Stable | v0.9.10 |

### CI/CD Pipeline

13 workflows covering:
- **lint.yml** -- ruff linting on push/PR
- **test.yml** -- pytest with coverage (fail-under: 60%, target: 65%)
- **security.yml** -- pip-audit + Snyk vulnerability scanning
- **codeql.yml** -- GitHub CodeQL static analysis
- **docker-build.yml** -- Docker image build validation
- **docker-publish.yml** -- Publish to GHCR on release
- **release.yml** -- Create GitHub release with changelog
- **auto-tag.yml** -- Auto-tag on version bump in main.py
- **update-snapshot.yml** -- Regenerate SNAPSHOT.md
- **update-docs-on-merge.yml** -- Auto-update docs on merge
- **stale.yml** -- Close stale issues/PRs
- **update-memory.yml** -- Auto-regenerate docs/MEMORY.md
- **update-changelog.yml** -- Auto-update CHANGELOG.md on PR merge

All workflow actions use pinned SHA versions. Concurrency groups prevent duplicate runs.

## Known Limitations

| Issue | Severity | Notes |
|-------|----------|-------|
| robots.txt parser ignores `Allow:` directive | Low | Over-blocks some valid URLs. Fix planned. |
| `reasoning_model` parameter unused | Low | Passed through but not used in any pipeline stage yet. Reserved for future site structure analysis. |
| No automatic resume on server restart | Medium | User must manually call resume endpoint after crash. |
| Cloud provider error handling not unified | Low | Timeout behavior and rate limit responses differ per provider. |
| Only markdown converter registered | Low | Plugin system works and accepts new converters, but only markdown is implemented. PDF/HTML planned. |

## Architecture Overview

```
CLI / Web UI / REST API
        |
   JobManager  (queue + state machine)
        |
   JobRunner   (orchestrates pipeline)
        |
   +---+---+---+---+
   |   |   |   |   |
  Disc Filt Scrp Cln Out
        |       |
     robots  PagePool + HTTP fast-path
              |
           LLM client (multi-provider)
```

### Key Design Decisions

1. **Fallback chain over single strategy** -- 5-level scraping ensures content extraction even on difficult sites
2. **LLM as cleanup, not extraction** -- LLM cleans noisy HTML; structured extraction uses deterministic parsers
3. **Checkpoint-first** -- Every stage writes state so jobs survive restarts
4. **Security by default** -- SSRF protection, CSP headers, rate limiting, API key auth all enabled out of the box

## Roadmap

### v0.9.11 (next)
- [ ] robots.txt `Allow:` directive support
- [ ] PDF converter plugin
- [ ] Unified cloud provider error handling

### v1.0.0
- [ ] HTML converter plugin
- [ ] Automatic resume on server restart
- [ ] Multi-site batch mode
- [ ] Public documentation site
- [ ] PyPI package publication
