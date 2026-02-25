# Docrawl -- Reporte Final de Auditoria Pre-Produccion

**Fecha:** 2026-02-25
**Waves completadas:** 8 (0-7)
**Agentes ejecutados:** 23
**Findings totales:** 444 raw -> 62 unicos (deduplicados y consolidados)

---

## Veredicto ejecutivo

Docrawl **no esta listo para produccion**. La arquitectura es fundamentalmente solida -- un monolito single-process apropiado para su caso de uso (single-user / small team) con abstracciones correctas (FastAPI + SSE, Playwright, Ollama via REST). Sin embargo, la implementacion tiene brechas criticas de seguridad que hacen que un deployment publico sea inaceptable en su estado actual. Hay 14 findings P0 bloqueantes, de los cuales 8 son vulnerabilidades de seguridad con CVSS >= 7.5, incluyendo path traversal (CVSS 9.1), ausencia total de autenticacion (CVSS 9.8), SSRF (CVSS 9.1), y XSS almacenado (CVSS 7.5).

El camino a produccion es claro y estimado en 3-5 dias de desarrollo enfocado. No se necesita rediseno arquitectonico -- los problemas son gaps de implementacion, no fallas de diseno. Los fixes de seguridad mas criticos (auth, path traversal, port binding) son cambios pequenos y bien definidos. El principal riesgo residual es la cobertura de tests al 20%, que significa que cualquier fix puede revertirse sin deteccion.

La recomendacion es: **resolver los 14 P0 antes de cualquier deploy publico**, con enfasis en seguridad primero. Luego abordar los P1 en la primera semana post-lanzamiento para estabilidad operativa.

---

## Estadisticas finales

| Categoria   | P0 | P1 | P2 | P3 | Total |
|-------------|----|----|----|----|-------|
| security    |  8 |  5 |  0 |  1 |    14 |
| bug         |  3 |  8 |  4 |  1 |    16 |
| ci-cd       |  1 |  4 |  0 |  3 |     8 |
| performance |  0 |  2 |  2 |  0 |     4 |
| refactor    |  0 |  1 |  2 |  1 |     4 |
| testing     |  1 |  0 |  0 |  0 |     1 |
| dx          |  0 |  0 |  0 |  2 |     2 |
| docs        |  0 |  0 |  0 |  2 |     2 |
| **Total**   | **14** | **21** | **16** | **11** | **62** |

### Por wave de origen

| Wave | Findings raw | Critical |
|------|-------------|----------|
| 1 -- Core Code Review | 174 | 15 |
| 2 -- Infra & DevOps | 70 | 5 |
| 3 -- AI/ML Engineering | 48 | 7 |
| 4 -- Quality & Security | 90 | 13 |
| 5 -- Docs & DX | 50 | 6 |
| 6 -- Architecture | 12 | 5 |
| 7 -- Synthesis | 62 (dedup) | 14 |
| **Total** | **444 raw -> 62 unicos** | **14 P0** |

---

## Top 10 hallazgos mas criticos

| # | ID | Titulo | CVSS | Categoria |
|---|-----|--------|------|-----------|
| 1 | CONS-002 | Sin autenticacion en ningun endpoint de la API | 9.8 | security |
| 2 | CONS-003 | Puerto 8002 en 0.0.0.0 -- bypass del perimetro Cloudflare | 9.8 | security |
| 3 | CONS-004 | Cloudflare Worker sin auth -- proxy abierto | 9.8 | security |
| 4 | CONS-001 | Path Traversal via output_path -- escritura arbitraria | 9.1 | security |
| 5 | CONS-005 | SSRF via Playwright -- acceso a metadata de cloud | 9.1 | security |
| 6 | CONS-012 | Prompt injection via contenido scrapeado | 8.0 | security |
| 7 | CONS-006 | XSS via innerHTML con datos SSE no sanitizados | 7.5 | security |
| 8 | CONS-007 | Sin rate limiting ni cap de jobs -- DoS | 7.5 | security |
| 9 | CONS-008 | Security CI gates desactivados con `|| true` | -- | ci-cd |
| 10 | CONS-011 | Truncamiento silencioso del LLM -- corrupcion de datos | -- | bug |

---

## Roadmap de remediacion

### Sprint 0 -- Antes de cualquier deploy publico (3-5 dias)

| Finding | Descripcion | Esfuerzo |
|---------|-------------|----------|
| CONS-002 | API key auth en FastAPI middleware | 4h |
| CONS-004 | API key validation en Cloudflare Worker | 2h |
| CONS-003 | Port binding a 127.0.0.1 | 30min |
| CONS-001 | Pydantic validator para path traversal | 4h |
| CONS-005 | SSRF blocklist (IPs privadas, link-local, loopback) | 4h |
| CONS-006 | Reemplazar innerHTML con textContent | 2h |
| CONS-007 | Rate limiting con slowapi + MAX_CONCURRENT_JOBS | 4h |
| CONS-012 | Delimitadores XML en prompts LLM | 2h |
| CONS-008 | Eliminar `\|\| true` de CI security gates | 30min |
| CONS-009 | Tests de seguridad para path traversal y SSRF | 4h |
| CONS-011 | Reducir chunk size + leer token counts | 2h |
| CONS-013 | Convertir _get_openrouter_models a async | 1h |
| CONS-014 | Done callback + shutdown cleanup para tasks | 2h |
| CONS-010 | Implementar asyncio.Semaphore para max_concurrent | 3h |
| **Total Sprint 0** | | **~33h (4-5 dias)** |

### Sprint 1 -- Primera semana post-lanzamiento

| Finding | Descripcion | Esfuerzo |
|---------|-------------|----------|
| CONS-015 | TTL eviction para jobs en memoria | 2h |
| CONS-016 | asyncio.Lock para JobManager._jobs | 1h |
| CONS-017 | Context managers para Playwright browsers | 3h |
| CONS-018 | Reemplazar xml.etree con defusedxml | 30min |
| CONS-019 | Validacion SSRF en markdown_proxy_url | 1h |
| CONS-020 | Bounds en parametros Pydantic (ge/le) | 1h |
| CONS-021 | Warning en UI para providers externos | 2h |
| CONS-022 | Security headers middleware | 2h |
| CONS-023 | Connection pooling en cliente LLM | 2h |
| CONS-024 | Fix separador en _generate_index | 1h |
| CONS-025 | Marcar reasoning_model como experimental | 1h |
| CONS-026 | Parser JSON robusto para LLM output | 3h |
| CONS-027 | Fix exception handler de cleanup | 1h |
| CONS-028 | Job state journal (SQLite o JSON) | 8h |
| CONS-029 | Mover __import__('os') a top-level | 5min |
| CONS-030 | Async file writes con asyncio.to_thread | 2h |
| CONS-031 | Crear .dockerignore | 30min |
| CONS-032 | Separar requirements.txt y requirements-dev.txt | 30min |
| CONS-033 | Pinear version de cloudflared | 15min |
| CONS-034 | Configurar CORSMiddleware | 1h |
| CONS-035 | Agregar --cov-fail-under en CI | 15min |
| **Total Sprint 1** | | **~32h (4-5 dias)** |

### Backlog (P2 y P3)

**P2 (17 findings):** DRY violation en client.py (CONS-036), refactor run_job monolitica (CONS-037), prints en discovery.py (CONS-038), chunk overlap duplicado (CONS-039), networkidle innecesario (CONS-040), cache de modelos (CONS-041), provider routing silencioso (CONS-042), retry en filtrado LLM (CONS-043), timeout insuficiente para modelos lentos (CONS-044), dead code legacy (CONS-045), senal de completitud en cleanup (CONS-046), query string stripping (CONS-047), non-atomic writes (CONS-048), retry backoff muerto (CONS-049), discover_urls nesting (CONS-050), doble Playwright en nav_parse (CONS-051).

**P3 (10 findings):** API versioning (CONS-052), health check funcional (CONS-053), tracking de tokens (CONS-054), pre-commit hooks (CONS-055), conventional commits (CONS-056), deployment pipeline (CONS-057), structured logging (CONS-058), convencion de idioma en docs (CONS-059), documentar multi-provider (CONS-060), Playwright innecesario en CI (CONS-061), info leakage en errors (CONS-062).

---

## Matriz esfuerzo/impacto

| Finding | Impacto | Esfuerzo | Ratio | Accion |
|---------|---------|----------|-------|--------|
| CONS-003 (port binding) | Critico | 30min | 5/5 | Cambiar a 127.0.0.1 |
| CONS-008 (CI gates) | Critico | 30min | 5/5 | Eliminar `\|\| true` |
| CONS-029 (__import__) | Medio | 5min | 5/5 | Mover import al top |
| CONS-031 (.dockerignore) | Alto | 30min | 5/5 | Crear archivo |
| CONS-035 (cov threshold) | Medio | 15min | 4/5 | Agregar flag |
| CONS-033 (pin cloudflared) | Medio | 15min | 4/5 | Pinear version |
| CONS-006 (XSS innerHTML) | Critico | 2h | 4/5 | textContent |
| CONS-004 (Worker auth) | Critico | 2h | 4/5 | API key en Worker |
| CONS-012 (prompt injection) | Alto | 2h | 4/5 | Delimitadores XML |
| CONS-001 (path traversal) | Critico | 4h | 4/5 | Pydantic validator |
| CONS-002 (API auth) | Critico | 4h | 4/5 | Middleware |
| CONS-005 (SSRF) | Critico | 4h | 3/5 | IP blocklist |
| CONS-018 (XXE) | Alto | 30min | 4/5 | defusedxml |
| CONS-020 (param bounds) | Alto | 1h | 4/5 | Pydantic ge/le |
| CONS-028 (crash recovery) | Alto | 8h | 2/5 | SQLite journal |
| CONS-037 (run_job refactor) | Medio | 8h | 2/5 | Extraer funciones |

---

## GitHub Issues creados

- **Total issues creados:** 35
- **P0:** 14 issues
- **P1:** 21 issues
- Links: ver seccion "Issues" en https://github.com/plater7/docrawl/issues

### Issues P0

1. [P0][security] CONS-001: Path Traversal via output_path
2. [P0][security] CONS-002: Sin autenticacion en ningun endpoint
3. [P0][security] CONS-003: Puerto 8002 en 0.0.0.0 bypass perimetro
4. [P0][security] CONS-004: Worker sin autenticacion -- proxy abierto
5. [P0][security] CONS-005: SSRF via Playwright a servicios internos
6. [P0][security] CONS-006: XSS via innerHTML con datos SSE
7. [P0][security] CONS-007: Sin rate limiting ni cap de jobs
8. [P0][ci-cd] CONS-008: Security CI gates desactivados con || true
9. [P0][testing] CONS-009: Cobertura de tests en 20%
10. [P0][bug] CONS-010: max_concurrent ignorado en runner
11. [P0][bug] CONS-011: Truncamiento silencioso del LLM
12. [P0][security] CONS-012: Prompt injection via contenido scrapeado
13. [P0][bug] CONS-013: Sync HTTP bloquea event loop async
14. [P0][bug] CONS-014: create_task fire-and-forget sin error handling

### Issues P1

15-35. CONS-015 a CONS-035 (ver issues individuales en GitHub)

---

## Score final por area

| Area | Score | Notas |
|------|-------|-------|
| Seguridad | 2/10 | 8 vulnerabilidades CVSS >= 7.5, 0 autenticacion, 0 input validation |
| Calidad de codigo | 5/10 | Funcional pero runner.py monolitico, async/sync mixing, dead code |
| Testing | 2/10 | 20% cobertura, 0% en modulos criticos, CI gates desactivados |
| Performance | 5/10 | Funcional pero sin connection pooling, sync blocking, networkidle |
| Documentacion | 6/10 | CLAUDE.md excelente, README basico, multi-provider no documentado |
| CI/CD | 4/10 | Workflows existentes pero gates desactivados, no-deploy pipeline |
| Arquitectura | 7/10 | Diseno solido, monolito apropiado, gaps en implementacion |
| DX | 5/10 | UI funcional, sin API versioning, sin structured logging |
| **Global** | **4/10** | **No listo para produccion. Fixable a 7.5-8/10 en 2 sprints.** |

---

## Conclusion

Docrawl es un proyecto con una base arquitectonica solida que honra su principio de simplicidad en el diseno pero lo traiciona en la implementacion. Los 14 findings P0 bloqueantes -- dominados por vulnerabilidades de seguridad criticas -- hacen que cualquier deployment publico sea inaceptable sin remediacion previa. La buena noticia es que el camino a produccion esta bien definido: 3-5 dias de desarrollo enfocado para resolver los P0, seguidos de una semana para estabilizar con los P1.

La prioridad absoluta es la cadena de autenticacion (CONS-002 + CONS-004 + CONS-003), que combinada representa un CVSS compuesto de 9.8 y permite acceso total no autorizado a toda la funcionalidad. Inmediatamente despues, path traversal (CONS-001) y SSRF (CONS-005) deben resolverse para prevenir escritura arbitraria y exfiltracion de credenciales. El tercer bloque critico son los fixes de calidad de datos (CONS-011 truncamiento, CONS-010 concurrencia) que, aunque no son vulnerabilidades, causan que el producto entregue resultados incorrectos sin que el usuario lo sepa.

Esta auditoria de 23 agentes en 8 waves ha producido una hoja de ruta clara y priorizada. Con la ejecucion disciplinada de los Sprints 0 y 1, Docrawl puede alcanzar un score de 7.5-8/10 y estar listo para uso en produccion con un nivel de confianza aceptable.
