# Wave 5 — Docs & DX Summary

**Estado:** ✅ DONE
**Agentes:** 3 (18 haiku, 19 haiku, 20 sonnet)
**Total findings:** 50 (6 critical, 22 major, 19 minor, 3 suggestion)

---

## Agentes

| Agente | Rol | Findings | Critical |
|--------|-----|----------|---------|
| 18 — documentation-engineer | Inconsistencias docs vs código, idioma | 15 | 1 |
| 19 — git-workflow-manager | CI/CD, pre-commit, convenciones | 11 | 1 |
| 20 — refactoring-specialist | Complejidad, DRY, dead code | 24 | 4 |

Reportes detallados: `audit-reports/wave5/agent1[8-9]-*.md`, `agent20-*.md`

---

## Hallazgos Críticos (6)

### Documentación (Agente 18)
- **Retry logic mismatch**: CLAUDE.md dice "3 intentos + backoff exponencial" — código tiene `MAX_RETRIES=2` + backoff lineal `[1,3]`. Inconsistencia confirmada en waves anteriores.

### CI/CD (Agente 19)
- **Security gates desactivados**: `security.yml:29,33,36` — bandit y pip-audit corren con `|| true`. CVSSs 9.1 pueden mergearse sin bloqueo. Fix: eliminar `|| true`.

### Refactoring (Agente 20)
- **`run_job` monolítica** — 463 LOC, complejidad ciclomática ~18, 14 responsabilidades mezcladas. Candidata a extracción en 5 funciones privadas (~80 LOC de flow-control).
- **DRY violation client.py** — `_generate_openrouter` y `_generate_opencode` son 77 líneas donde 72 son idénticas. Fix: extraer `_generate_chat_completion(api_key, base_url, provider_name)`.
- **Dead code confirmado** — `generate_legacy` y `get_available_models_legacy` (client.py:299-312): 0 callers en todo el proyecto.
- **XSS innerHTML** — `index.html:1274` (ya conocido de waves anteriores, reconfirmado).

---

## Hallazgos Major (selección)

| Agente | Finding | Archivo |
|--------|---------|---------|
| 18 | Endpoints API desactualizados (multi-provider no documentado) | CLAUDE.md |
| 18 | Multi-provider feature (OpenRouter/OpenCode) no en CLAUDE.md | CLAUDE.md |
| 18 | README en inglés, CLAUDE.md en español, sin convención | — |
| 19 | Sin `.pre-commit-config.yaml` — no hay hooks locales | — |
| 19 | Sin conventional commits enforcement | — |
| 19 | Codecov no bloqueante (`fail_ci_if_error: false`) | test.yml |
| 19 | Sin semantic-release automation | — |
| 20 | 27 `print()` en discovery.py duplicando logger | discovery.py |
| 20 | `max_concurrent` engaña al usuario — siempre secuencial | runner.py |
| 20 | `reasoning_model` validado (puede rechazar jobs) pero nunca usado | runner.py |
| 20 | `discover_urls` 113 LOC con 4 niveles de nesting | discovery.py |
| 20 | Links rotos en `_index.md` por diseño (separador `_` vs `/`) | runner.py |
| 20 | `_get_openrouter_models` síncrona en dispatcher async | client.py |

---

## Mapa de complejidad (Agente 20)

| Archivo | LOC | CC estimado | Prioridad refactoring |
|---------|-----|-------------|----------------------|
| `src/jobs/runner.py` | ~591 | ~18 | Alta — dividir run_job |
| `src/ui/index.html` | ~1485 | — | Media — separar concerns JS |
| `src/crawler/discovery.py` | ~400 | ~12 | Media — simplificar nesting |
| `src/llm/client.py` | ~320 | ~8 | Alta — unificar _generate_* |
| `src/api/routes.py` | ~230 | ~6 | Baja |

---

## Acumulado Waves 1-5

| Wave | Findings | Critical |
|------|----------|---------|
| 1 — Core Code | 174 | 15 |
| 2 — Infra & DevOps | 70 | 5 |
| 3 — AI/ML | 48 | 7 |
| 4 — Quality & Security | 90 | 13 |
| 5 — Docs & DX | 50 | 6 |
| **Total** | **432** | **46** |
