# Docrawl: Auditoría Multi-Agente — Estado y Continuación

## Context

Auditoría completa de **docrawl** (Python 3.12 / FastAPI / Playwright / LLM multi-provider) antes de producción.
- **Repo:** `C:\Users\splatero\claude-code\docrawl` (~42 archivos, ~4500 LOC)
- **GitHub:** `plater7/docrawl` | Branch: `main`
- **Audit reports:** `docrawl/audit-reports/`
- **Memory:** `C:\Users\splatero\.claude\projects\C--Users-splatero-claude-code\memory\docrawl-audit.md`

---

## Estado Actual

| Wave | Estado | Agentes | Findings (raw) | Critical |
|------|--------|---------|----------------|----------|
| 0 — GitHub Infra | ✅ DONE | git-workflow + deployment | — | — |
| 1 — Core Code Review | ✅ DONE | 5x sonnet | 174 | 15 |
| 2 — Infra & DevOps | ✅ DONE | 2x sonnet, 1x haiku, 1x opus | 70 | 5 |
| 3 — AI/ML Engineering | ⏳ PENDING | 2x opus, 1x sonnet | — | — |
| 4 — Quality & Security | ⏳ PENDING | 2x opus, 3x sonnet | — | — |
| 5 — Docs & DX | ⏳ PENDING | 1x sonnet, 2x haiku | — | — |
| 6 — Architecture | ⏳ PENDING | 1x opus | — | — |
| 7 — Synthesis + Issues | ⏳ PENDING | 1x opus, 1x sonnet | — | — |

**Cumulative findings so far:** ~244 raw (Waves 1+2), fully saved in `audit-reports/`

---

## Wave 0 — Completada ✅

- 14 labels creados, 6 milestones creados
- Issue templates: bug_report.yml, feature_request.yml, security_vulnerability.yml, audit_finding.yml
- PR template con security checklist
- Workflows: lint.yml, security.yml, docker-build.yml, release.yml
- dependabot.yml, CODEOWNERS, CONTRIBUTING.md, SECURITY.md
- Commit: `1bc154e` pushed to main
- Project board: https://github.com/users/plater7/projects/1
  - ⚠️ Pendiente manual: agregar columnas "Triage" e "In Review" via UI

---

## Hallazgos Críticos Acumulados (Waves 1-2)

### Seguridad — MUST FIX BEFORE PROD
1. **Path traversal** via `output_path` — CVSS 9.1 | `models.py:13`, `runner.py:285`
2. **SSRF** via Playwright a URLs internas — CVSS 9.1 | `page.py:161`, `discovery.py:237`
3. **Sin autenticación** en ningún endpoint — CVSS 9.8 | toda la API
4. **Worker sin auth** — CVSS 9.8 | `worker/src/index.js`
5. **XSS** via `innerHTML` con datos SSE — `index.html:1274,1332`
6. **Sin rate limiting** / job concurrency cap — DoS trivial
7. **Port 8002 en 0.0.0.0** — bypassa Worker perimeter | `docker-compose.yml:11`
8. **Prompt injection** via contenido scrapeado | `cleanup.py:101`, `filter.py:43`

### Performance / Correctness
9. **Blocking sync HTTP** en async context (`_get_openrouter_models`) | `client.py:97`
10. **`max_concurrent` nunca usado** — secuencial pese a aceptar el param | `runner.py:295`
11. **`_generate_index` links rotos** — usa `_` en vez de `/` | `runner.py:579`
12. **Chunk overlap → contenido duplicado** en output | `markdown.py:126`

### Infra / DevOps
13. **Sin `.dockerignore`** — build context incluye `.git/`, `data/`, `worker/`
14. **Test deps en imagen runtime** — pytest en producción | `requirements.txt:9-11`
15. **Security CI gates deshabilitados** — `|| true` en bandit y pip-audit
16. **`cloudflared:latest` unpinned** | `docker-compose.yml:39`
17. **Sin backup strategy** para `/data`
18. **Estado in-memory** — se pierde en restart, sin persistencia

---

## Próximas Waves — Ejecución

### Wave 3 — AI/ML Engineering (3 agentes en paralelo)

**Agente 10:** `voltagent-data-ai:ai-engineer` (opus)
- Archivos: `src/llm/client.py`, `src/llm/filter.py`, `src/llm/cleanup.py`, `src/jobs/runner.py`
- Foco: No token counting, `num_ctx` mismatch con chunk size, `reasoning_model` sin usar, no model fallback, dead code (`generate_legacy`)
- Contexto previo: `num_ctx: 8192` insuficiente para 16KB chunks; 2 retries contados como 3; `_get_openrouter_models` es sync

**Agente 11:** `voltagent-data-ai:llm-architect` (opus)
- Archivos: `src/llm/client.py`, `src/llm/cleanup.py`, `src/llm/filter.py`
- Foco: 3 funciones `_generate_*` casi idénticas (DRY), sync HTTP en async, no connection pooling, no caching de model lists, provider routing frágil (openai/gpt-4 → Ollama por error)
- Contexto previo: `get_provider_for_model` falla con prefijos desconocidos; no hay `httpx.AsyncClient` compartido

**Agente 12:** `voltagent-data-ai:prompt-engineer` (sonnet)
- Archivos: `src/llm/filter.py`, `src/llm/cleanup.py`
- Foco: Prompts sin few-shot examples, sin JSON schema, cleanup prompt muy breve, prompt injection via URLs, `temperature: 0.1` innecesario para cleanup
- Contexto previo: contenido scrapeado inyectado sin sanitizar directamente en el prompt

### Wave 4 — Quality & Security (5 agentes en paralelo)

**Agente 13:** `voltagent-qa-sec:code-reviewer` (opus)
- Archivos: `src/jobs/runner.py`, `src/crawler/discovery.py`, `src/llm/client.py`, `src/jobs/manager.py`
- Foco: Race conditions, robots.py lowercasea paths (case-sensitive en Linux), `filter_urls` dropea query strings, off-by-one en retry

**Agente 14:** `voltagent-qa-sec:security-auditor` (opus)
- Archivos: `src/api/routes.py`, `src/jobs/runner.py`, `src/scraper/page.py`, `src/ui/index.html`, `src/llm/filter.py`
- Foco: OWASP assessment completo — path traversal, SSRF, XSS, prompt injection, DoS, data exfiltration a APIs externas
- Contexto previo: security-engineer (Wave 2) ya cubrió varios; buscar hallazgos nuevos en lógica de negocios

**Agente 15:** `voltagent-qa-sec:performance-engineer` (sonnet)
- Archivos: `src/jobs/runner.py`, `src/crawler/discovery.py`, `src/scraper/page.py`, `src/scraper/markdown.py`, `src/llm/client.py`
- Foco: Procesamiento secuencial, no connection pooling, `write_text` sync en async, `html.parser` vs `lxml`, sin request pipelining LLM

**Agente 16:** `voltagent-qa-sec:qa-expert` (sonnet)
- Archivos: `tests/` (todos), `pytest.ini`
- Foco: 0 tests para routes, manager, runner, llm/*, exceptions. Coverage matrix, gap analysis.
- Tests existentes: test_discovery.py, test_filter.py, test_robots.py, test_markdown_negotiation.py

**Agente 17:** `voltagent-qa-sec:test-automator` (sonnet)
- Archivos: `tests/`, `pytest.ini`, `.github/workflows/test.yml`, `requirements.txt`
- Foco: No pytest-xdist, no property-based testing, no snapshot testing, CI no cachea Playwright browsers

### Wave 5 — Docs & DX (3 agentes en paralelo)

**Agente 18:** `voltagent-dev-exp:documentation-engineer` (haiku)
- Archivos: `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `docs/SETUP.md`, `.env.example`
- Foco: Inconsistencias (CLAUDE.md dice "max 3 intentos" pero `MAX_RETRIES=2`), mix español/inglés, sin ADRs

**Agente 19:** `voltagent-dev-exp:git-workflow-manager` (haiku)
- Archivos: `.gitignore`, `.github/workflows/test.yml`, `CHANGELOG.md`, git history
- Foco: Sin branch protection, sin pre-commit hooks, sin conventional commits. Nota: PR/issue templates YA creados en Wave 0

**Agente 20:** `voltagent-dev-exp:refactoring-specialist` (sonnet)
- Archivos: `src/jobs/runner.py`, `src/ui/index.html`, `src/llm/client.py`, `src/crawler/discovery.py`
- Foco: `runner.py` = función monolítica de ~465 líneas, `index.html` = 1485 líneas, 3x `_generate_*` duplicados, dead code, `print()`+`logger` duplication

### Wave 6 — Architecture Review (1 agente)

**Agente 21:** `voltagent-qa-sec:architect-reviewer` (opus)
- Archivos: TODO el código fuente
- Input: Hallazgos de Waves 1-5 (pasar summary de hallazgos críticos al prompt)
- Foco: Evaluación global, "simplicidad vs realidad", escalabilidad, estado in-memory, technical debt heat map

### Wave 7 — Synthesis + GitHub Issues (2 agentes en paralelo)

**Agente 22:** `voltagent-meta:agent-organizer` (sonnet)
- Input: Todos los summaries de waves 1-6
- Foco: Deduplicar, categorizar, taxonomía consistente (severity: critical/major/minor/suggestion)
- Output: Lista deduplicada lista para crear issues

**Agente 23:** `voltagent-meta:multi-agent-coordinator` (opus)
- Input: Output de agente 22 + todos los summaries
- Foco: Executive summary, remediation roadmap priorizado, effort/impact matrix
- Output: Reporte final + crear GitHub Issues con `gh issue create` para cada hallazgo

---

## Instrucciones para el siguiente /compact

Al inicio de la próxima sesión, leer:
1. Este plan: `C:\Users\splatero\.claude\plans\recursive-snuggling-bonbon.md`
2. Memory: `C:\Users\splatero\.claude\projects\C--Users-splatero-claude-code\memory\docrawl-audit.md`
3. Wave 1 summary: `C:\Users\splatero\claude-code\docrawl\audit-reports\wave1-summary.md`
4. Wave 2 summary: `C:\Users\splatero\claude-code\docrawl\audit-reports\wave2-summary.md`

Luego ejecutar Wave 3 → Wave 4 → Wave 5 → Wave 6 → Wave 7, cada una en paralelo.

---

## Verificación Final (Wave 7)

1. `gh label list` — 14+ labels presentes
2. `gh milestone list` — 6 milestones presentes
3. `gh issue list` — todos los hallazgos críticos como issues con labels + milestones
4. `gh project list` — project board activo
5. Los 5 archivos críticos cubiertos por 3+ agentes: `runner.py`, `routes.py`, `client.py`, `index.html`, `discovery.py` ✅
6. Reporte final en `audit-reports/final-report.md`
