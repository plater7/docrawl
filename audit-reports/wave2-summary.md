# Wave 2 — Infrastructure & DevOps Summary

**Date:** 2026-02-24
**Agents:** 4 (2x sonnet, 1x haiku, 1x opus)
**Total Findings:** 70 raw (before deduplication)

## Findings by Agent

| # | Agent | Model | Findings | Critical | Major | Minor | Suggestion |
|---|-------|-------|----------|----------|-------|-------|------------|
| 6 | docker-expert | sonnet | 20 | 0 | 5 | 7 | 8 |
| 7 | deployment-engineer | haiku | 13 | 1 | 6 | 4 | 2 |
| 8 | devops-engineer | sonnet | 19 | 1 | 10 | 8 | 0 |
| 9 | security-engineer | opus | 18 | 3 | 7 | 5 | 0 |

## Critical Findings (Cross-Agent)

### 1. SSRF via Playwright (Agent: 9) — CVSS 9.1
- User-supplied URLs navigated by Playwright can target internal services (169.254.169.254, localhost)
- `markdown_proxy_url` also user-controllable → secondary SSRF vector
- `host.docker.internal:host-gateway` in docker-compose makes host reachable

### 2. Unauthenticated Cloudflare Worker (Agents: 8, 9) — CVSS 9.8
- Worker blindly proxies ALL requests with zero auth
- All headers forwarded verbatim (Cookie, Authorization, X-Forwarded-For)
- Anyone with the workers.dev URL has full API access

### 3. Path Traversal Confirmed with CVSS (Agent: 9) — CVSS 9.1
- Reconfirmed from Wave 1 with full attack scenario trace
- `_url_to_filepath` also vulnerable via malicious URL paths

### 4. No Deployment Pipeline (Agent: 7)
- Release workflow only creates GitHub Releases, no actual deployment
- No staging/production environments

## Major Findings (Deduplicated Top 10)

1. **No `.dockerignore`** — full build context sent to daemon, risk of secrets leakage (Agent: 6)
2. **Port 8002 exposed to 0.0.0.0** — bypasses Cloudflare Worker perimeter entirely (Agent: 8)
3. **Security CI gates disabled** — `bandit` and `pip-audit` run with `|| true` (Agents: 7, 8)
4. **No structured logging/metrics** — stdout only, no JSON, no Prometheus, no alerting (Agent: 8)
5. **No backup strategy for `/data`** — bind mount with no snapshots, no offsite copy (Agent: 8)
6. **No crash recovery** — in-memory job state lost on restart, no journal/checkpoint (Agent: 8)
7. **Test deps in production image** — pytest/pytest-cov installed in runtime container (Agents: 6, 7)
8. **`cloudflared:latest` unpinned** — floating tag can break tunnel silently (Agents: 6, 8)
9. **No coverage threshold** — tests pass regardless of coverage drop (Agent: 7)
10. **Prompt injection via scraped content** — LLM prompts include raw scraped markdown (Agent: 9)

## New Findings Not in Wave 1

| Finding | Agent | Severity |
|---------|-------|----------|
| SSRF via Playwright to cloud metadata | 9 | Critical |
| SSRF via `markdown_proxy_url` | 9 | Major |
| Prompt injection risk in LLM cleanup | 9 | Major |
| Data exfiltration to external LLM APIs | 9 | Major |
| No `.dockerignore` | 6 | Major |
| Port 8002 on 0.0.0.0 | 8 | Major |
| Non-atomic file writes | 8 | Minor |
| No dev/prod Worker environments | 8 | Minor |
| Worker forwards all headers | 8 | Major |
| XXE risk in sitemap parsing | 9 | Minor |
| Browser crash = job failure (no restart) | 8 | Minor |
