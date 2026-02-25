# Wave 6 — Architecture Review Summary

**Estado:** ✅ DONE
**Agente:** 21 — architect-reviewer (opus)
**Hallazgos arquitectónicos:** 12 (5 critical, 5 major, 2 minor)
**Veredicto:** No listo para producción — Score 6/10, fixable a 8.5/10

Reporte detallado: `audit-reports/wave6/agent21-architect-reviewer.md`

---

## Veredicto global

> **"La arquitectura es fundamentalmente sólida. Los problemas son gaps de implementación, no fallas de diseño. No se necesita rediseño mayor."**

El diseño monolítico single-process es **apropiado** para el caso de uso real (single-user / small team). Las abstracciones elegidas (FastAPI + SSE, Playwright, Ollama via REST) son correctas. El principio de simplicidad se honra en el diseño pero se traiciona en la implementación (estado efímero 100%, async/sync mixing, sin validación de inputs).

**Arquitectura score: 6/10** — sólida en concepto, inmadura en implementación.

---

## Heat Map de Deuda Técnica

| Módulo | Deuda (1-10) | Acción |
|--------|-------------|--------|
| `src/jobs/runner.py` | 8 | Dividir en funciones privadas, fix async/sync |
| `src/llm/client.py` | 8 | Unificar _generate_*, connection pooling, async fix |
| `src/ui/index.html` | 7 | Fix XSS innerHTML, separar concerns JS |
| `src/crawler/discovery.py` | 6 | Eliminar print(), reducir nesting |
| `src/api/routes.py` | 6 | Auth, rate limiting, validación |
| `src/jobs/manager.py` | 5 | Evicción de jobs, lock para race condition |
| `src/scraper/page.py` | 5 | BrowserContext isolation, fix SSRF |
| `src/llm/filter.py` | 4 | Mejores prompts, delimitadores XML |
| `src/llm/cleanup.py` | 4 | Mejores prompts, fix truncamiento |
| `src/crawler/filter.py` | 3 | Fix query string stripping |
| `src/crawler/robots.py` | 3 | Fix case-sensitivity |
| `worker/src/index.js` | 7 | Auth, header sanitization |

---

## Hallazgos Críticos (5)

### ARCH-001: Sin autenticación en toda la cadena
- Worker → Tunnel → API: 0 autenticación en ningún punto
- Cualquier persona con la URL del Worker tiene acceso total
- **Esfuerzo:** 1 día — API key en FastAPI middleware + Worker

### ARCH-002: Estado 100% efímero — sin persistencia ni crash recovery
- Jobs en memoria pura — un restart del proceso pierde todo
- Sin checkpoint entre fases — si runner.py falla a mitad, no hay recovery
- **Esfuerzo:** 2-3 días — SQLite o file-based job journal

### ARCH-004: Truncamiento silencioso de LLM — corrupción de datos
- Chunks de 16K chars vs ventana de 8192 tokens → output incompleto sin error
- El usuario recibe markdown truncado creyendo que está limpio
- **Esfuerzo:** 4 horas — reducir chunk size + leer token counts de respuesta Ollama

### ARCH-005: Cloudflare Worker como puerta abierta
- 17 líneas, 0 autenticación, forward de todos los headers
- Único punto de entrada público completamente inoperante como control de seguridad
- **Esfuerzo:** 4 horas — API key validation en Worker

### ARCH-008: Path traversal en output_path (CVSS 9.1)
- Sin sanitización — escritura arbitraria en el filesystem
- Reconfirmado desde Wave 1 como el finding más urgente del proyecto

---

## Top 5 cambios antes de producción

| # | Cambio | Esfuerzo |
|---|--------|---------|
| 1 | API key auth en FastAPI + Worker | 1 día |
| 2 | Validación completa de inputs Pydantic (path traversal, bounds, SSRF) | 1 día |
| 3 | Fix truncamiento LLM (chunk size, leer token counts, delimitadores XML) | 4h |
| 4 | Port binding a 127.0.0.1 + SSRF blocklist para IPs privadas | 4h |
| 5 | Tests de regresión de seguridad + eliminar `\|\| true` del CI | 4h |

**Total estimado para production-ready mínimo: 3-5 días de desarrollo**

---

## Riesgos sistémicos identificados

- **Sin crash recovery**: restart del proceso → todos los jobs activos perdidos, usuario sin notificación
- **Single point of failure**: 1 proceso Python maneja todo — crash de Playwright tumba la API
- **Data loss silencioso**: truncamiento LLM, links rotos en _index.md, query strings eliminados — el usuario no sabe que el output está incompleto
- **Security theater**: CI security gates con `|| true`, port 8002 en 0.0.0.0, Worker sin auth — capas de seguridad que no funcionan

---

## Acumulado Waves 1-6

| Wave | Findings | Critical |
|------|----------|---------|
| 1 — Core Code | 174 | 15 |
| 2 — Infra & DevOps | 70 | 5 |
| 3 — AI/ML | 48 | 7 |
| 4 — Quality & Security | 90 | 13 |
| 5 — Docs & DX | 50 | 6 |
| 6 — Architecture | 12 | 5 |
| **Total** | **444** | **51** |
