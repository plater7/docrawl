# Project Status

> DocRawl v0.9.10 — Last updated: 2026-03-08

## Current State

DocRawl is a **functional documentation crawler** in late beta. The core pipeline (discovery → filter → scrape → cleanup → output) is stable and handles production workloads. The project has mature CI/CD (11 GitHub Actions workflows), structured logging, security hardening, and a web UI.

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

12 workflows covering:
- **lint.yml** — ruff linting on push/PR
- **test.yml** — pytest with coverage (fail-under: 50%, target: 65%)
- **security.yml** — pip-audit + Snyk vulnerability scanning
- **codeql.yml** — GitHub CodeQL static analysis
- **docker-build.yml** — Docker image build validation
- **docker-publish.yml** — Publish to GHCR on release
- **release.yml** — Create GitHub release with changelog
- **auto-tag.yml** — Auto-tag on version bump in main.py
- **update-snapshot.yml** — Regenerate SNAPSHOT.md
- **update-docs-on-merge.yml** — Auto-update docs on merge
- **stale.yml** — Close stale issues/PRs
- **update-memory.yml** — Auto-regenerate docs/Memory.md

All workflow actions use pinned SHA versions. Concurrency groups prevent duplicate runs.

## Known Limitations

| Issue | Severity | Notes |
|-------|----------|-------|
| robots.txt parser ignores `Allow:` directive | Low | Over-blocks some valid URLs. Fix planned. |
| `reasoning_model` parameter unused | Low | Passed through but not used in any pipeline stage yet. Reserved for future site structure analysis. |
| Coverage threshold (50%) below actual (~60%) | Low | Threshold needs bump to match reality. |
| No automatic resume on server restart | Medium | User must manually call resume endpoint after crash. |
| Cloud provider error handling not unified | Low | Timeout behavior and rate limit responses differ per provider. |
| Single converter registered (markdownify) | Low | Plugin system exists but only default converter is available. |
| No WebSocket support for real-time events | Low | SSE works but WebSocket would reduce overhead for high-frequency updates. |

## Test Coverage

```
Module                          Coverage
──────────────────────────────────────────
 src/api/                        Good
 src/crawler/                    Good
 src/jobs/                       Partial (runner.py needs more)
 src/llm/                        Good
 src/scraper/                    Partial
 src/utils/                      Good
──────────────────────────────────────────
Overall:                         ~60%
Threshold (pytest.ini):          50% (needs bump)
Target:                          65%
```

## Roadmap (Tentative)

### v0.10 — Stability & Testing
- [ ] Bump coverage threshold to 60%, target 65%
- [ ] Add tests for `runner.py` core paths
- [ ] Support `Allow:` directive in robots.txt parser
- [ ] Unified error handling across LLM providers

### v1.0 — Production Ready
- [ ] Use `reasoning_model` for site structure analysis
- [ ] Additional converter plugins (html2text, trafilatura)
- [ ] Automatic resume on server restart
- [ ] WebSocket event stream option
- [ ] API documentation (OpenAPI schema is auto-generated, needs narrative docs)

### Future
- [ ] Multi-site batch jobs
- [ ] Incremental re-crawl (only process changed pages)
- [ ] Output to external stores (S3, GCS)
- [ ] Distributed crawling (worker pool)

## Documentation

| Document | Purpose |
|----------|--------|
| [README.md](../README.md) | Project overview, quick start, configuration |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | System design, pipeline diagram, module map |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Development workflow, commit conventions |
| [CHANGELOG.md](../CHANGELOG.md) | Version history (Keep a Changelog format) |
| [SECURITY.md](../SECURITY.md) | Security policy and reporting |
| [docs/SETUP.md](SETUP.md) | Detailed setup instructions |
| [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and solutions |
| [docs/adr/](adr/) | Architecture Decision Records |
| [docs/Memory.md](Memory.md) | Claude Code memory file (auto-generated) |
| [SNAPSHOT.md](../SNAPSHOT.md) | Full code snapshot (auto-generated) |

---

*This document is manually maintained. For auto-generated files, see `SNAPSHOT.md` (code) and `docs/Memory.md` (Claude Code memory).*
