# Wave 4 — Quality & Security Summary

**Estado:** ✅ DONE
**Agentes:** 5 (13 opus, 14 opus, 15 sonnet, 16 sonnet, 17 sonnet)
**Total findings:** 90 (13 critical, 32 major, 30 minor, 13 suggestion)

---

## Agentes

| Agente | Rol | Findings | Critical |
|--------|-----|----------|---------|
| 13 — code-reviewer | Race conditions, correctness, bugs | 18 | 0 |
| 14 — security-auditor | OWASP, business logic (nuevos) | 20 | 3 |
| 15 — performance-engineer | Throughput, blocking I/O, memory | 15 | 2 |
| 16 — qa-expert | Coverage gaps, test strategy | 22 | 5 |
| 17 — test-automator | CI/CD, infraestructura de testing | 15 | 3 |

Reportes detallados: `audit-reports/wave4/agent1[3-7]-*.md`

---

## Hallazgos Críticos (13)

### Security (Agente 14)
- **XXE en sitemap parser** — `discovery.py:369` usa `xml.etree.ElementTree` sin defusedxml. CVSS 8.6
- **SSRF via markdown_proxy_url** — `models.py:20` acepta cualquier URL sin validar. CVSS 8.1
- **Parámetros sin límites** — `delay_ms`, `max_concurrent`, `max_depth` sin `ge`/`le` → DoS/DDoS. CVSS 7.5

### Performance (Agente 15)
- **max_concurrent es decorativo** — `runner.py:295` procesa siempre secuencial. Throughput 3x-6x peor que prometido
- **sync httpx.get() bloquea event loop 10s** — `client.py:102` en `_get_openrouter_models`

### Quality / Testing (Agente 16)
- **0 tests para API layer** — `POST /api/jobs` (path traversal CVSS 9.1) sin test de validación
- **0 tests para runner.py** (591 LOC, módulo más complejo) — bug `_generate_index` sin regresión
- **0 tests para manager.py** — `event_stream` puede colgar clientes indefinidamente sin detection
- **0 security regression tests** — fixes de CVSSs 9.1/9.8 pueden revertirse silenciosamente
- **0 tests para llm/** (503 LOC) — provider routing incorrecto, retries miscounted, sin cobertura

### CI/CD (Agente 17)
- **Cobertura real: 20%** — 964/1209 líneas sin cubrir
- **Security gates con `|| true`** — Bandit y pip-audit nunca bloquean un PR (`security.yml:29,33,36`)
- **`_url_to_filepath` sin tests** — vector de path traversal CVSS 9.1 sin regresión

---

## Hallazgos Major (selección)

| Agente | Finding | Archivo |
|--------|---------|---------|
| 13 | Race condition en `JobManager._jobs` sin asyncio.Lock | `manager.py` |
| 13 | `_generate_index` produce links rotos (`_` en vez de `/`) | `runner.py` |
| 13 | Memory leak: jobs completados nunca se borran del dict | `manager.py` |
| 13 | `filter_urls` elimina query strings silenciosamente | `filter.py:95` |
| 14 | Data exfiltration: contenido scrapeado va a OpenRouter sin consent | `client.py:218-295` |
| 14 | Sin security headers (CSP, X-Frame-Options, HSTS) | `main.py` |
| 14 | Worker forward todos los headers verbatim (Host poisoning) | `worker/index.js` |
| 15 | `wait_until="networkidle"` añade 3-10s por página innecesariamente | `page.py` |
| 15 | Segunda instancia Playwright en `try_nav_parse` — doble memoria | `discovery.py` |
| 15 | `write_text()` síncrono en event loop (crítico en Docker volumes) | `runner.py` |
| 16 | Tests de discovery mockean demasiado alto — no testean internals | `test_discovery.py` |
| 17 | Playwright instalado en CI sin tests que lo usen (3-5 min perdidos) | `test.yml` |
| 17 | Test deps mezcladas con prod deps en requirements.txt | `requirements.txt` |

---

## Datos clave

- **Cobertura de tests:** 12-18% (estimado QA) / 20% (medido CI) — 9 de 14 módulos en 0%
- **Throughput real:** job de 50 páginas tarda 35-90 min vs 12-30 min prometidos
- **Esfuerzo para 80% cobertura:** 32-35 horas en 4 sprints prioritarios
- **Security gates:** completamente inoperantes (`|| true` en todos los steps)

---

## Acumulado Waves 1-4

| Wave | Findings | Critical |
|------|----------|---------|
| 1 — Core Code | 174 | 15 |
| 2 — Infra & DevOps | 70 | 5 |
| 3 — AI/ML | 48 | 7 |
| 4 — Quality & Security | 90 | 13 |
| **Total** | **382** | **40** |
