# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v0.9.7] - 2026-02-27

### Added
- **Structured Logging** — logs emitidos como JSON (`timestamp`, `level`, `logger`, `message` + campos extra) — closes #109
- **Token Tracking** — cada llamada a Ollama loguea `prompt_tokens` y `completion_tokens` del response — closes #105
- **API Versioning** — middleware `X-API-Version: 0.9.7` header en todas las respuestas — closes #103
- **Docker Publish Workflow** — nuevo `.github/workflows/docker-publish.yml` que publica imagen a GHCR al hacer push de un tag `v*` — closes #108
- **Pre-commit Hooks** — `.pre-commit-config.yaml` con `ruff` (lint + format) — closes #106
- **Multi-provider docs** — sección en README con instrucciones de configuración para Ollama, OpenRouter y OpenCode — closes #111
- **Conventional Commits** — documentado en CONTRIBUTING.md con tipos, ejemplos y reglas — closes #107

### Fixed
- **Health Check** — `/api/health/ready` retorna HTTP 503 cuando el provider LLM no está disponible (antes retornaba 200 con `ready: false`) — closes #104
- **Error Sanitization** — handler global de excepciones retorna `{"error": "Internal server error"}` sin exponer stack traces — closes #113
- **CI optimization** — eliminada instalación innecesaria de Playwright en `test.yml` (browsers no requeridos para unit tests) — closes #112

### Changed
- CONTRIBUTING.md estandarizado en español con sección de Conventional Commits — closes #110

---

## [v0.9.6b] - 2026-02-26

### Fixed
- **Footer siempre visible** ([#121](https://github.com/plater7/docrawl/pull/121)) — `position: relative` ocultaba el footer bajo el fold (después del `.summary` con `display:none`); cambiado a `position: fixed; bottom: 0` para que sea permanentemente visible en los 3 temas; fondo semi-transparente + `backdrop-filter: blur` para legibilidad; `padding-bottom: 3rem` en `body` para que el contenido no quede tapado

---

## [v0.9.6a] - 2026-02-26

### Added
- **Footer de identidad en UI** ([feat](https://github.com/plater7/docrawl)) — leyenda inferior con nombre del proyecto, versión dinámica (desde `/api/info`), URL del repo, autor, y modelos usados durante el desarrollo; se actualiza automáticamente al cargar la UI
- **Endpoint `GET /api/info`** — expone metadata del build: `name`, `version`, `repo`, `author`, `models_used`; la UI lo consume para mostrar siempre la versión que está corriendo en el container
- **`APP_VERSION` constante** en `main.py` — fuente canónica única de versión, usada tanto en FastAPI metadata como en `/api/info`

### Changed
- `main.py`: `version="0.9.0"` → `version=APP_VERSION` ("0.9.6a") — sincroniza FastAPI OpenAPI con el tag del release
- `README.md`: roadmap P0/P1/P2 actualizado con estado real de fixes (10/14 P0 resueltos), métricas del repo (113+ issues, 119+ PRs), API docs incluyen nuevo endpoint

---

## [v0.9.6] - 2026-02-26

### Fixed
- **Escrituras atómicas en runner.py** ([#99](https://github.com/plater7/docrawl/issues/99)) — `file_path.write_text()` reemplazado por escritura a `.tmp` + `Path.rename()` para prevenir archivos corruptos en caso de crash durante el guardado
- **`print()` eliminados de discovery.py** ([#89](https://github.com/plater7/docrawl/issues/89)) — ~27 llamadas `print(f"[DISCOVERY] ...", flush=True)` removidas; logging ya existía via `logger.info/warning/error` duplicado

---

## [v0.9.5] - 2026-02-26

### Fixed
- **Cache de listas de modelos** ([#92](https://github.com/plater7/docrawl/issues/92)) — `get_available_models()` ahora cachea resultados 60s por provider (`_model_cache` + `time.monotonic()`); evita HTTP repetidos a Ollama/OpenRouter en cada job
- **Retry con backoff exponencial en filter_urls_with_llm** ([#94](https://github.com/plater7/docrawl/issues/94)) — agregado `FILTER_MAX_RETRIES = 3` y `asyncio.sleep(2**attempt)` (1s, 2s, 4s); antes fallaba silenciosamente en el primer error
- **Backoff exponencial en cleanup_markdown** ([#100](https://github.com/plater7/docrawl/issues/100)) — `MAX_RETRIES` 2→3, lista hardcodeada `[1, 3]` reemplazada por `2**attempt` para consistencia

---

## [v0.9.4] - 2026-02-26

### Added
- **Suite de tests unitarios** ([#55](https://github.com/plater7/docrawl/issues/55)) — 200 tests nuevos (295 total), cobertura del código unit-testable de ~20% a 57%
  - `tests/api/test_models.py` (29) — validación de `JobRequest`, `OllamaModel`, `JobStatus`
  - `tests/api/test_routes.py` (19) — endpoints FastAPI vía TestClient
  - `tests/jobs/test_manager.py` (21) — ciclo de vida de `Job`, CRUD de `JobManager`
  - `tests/crawler/test_url_filter.py` (38) — `filter_urls()`, `_matches_language()` todos los branches
  - `tests/llm/test_client.py` (26) — routing de providers, fetching de modelos, `generate()`
  - `tests/llm/test_filter.py` (13) — `filter_urls_with_llm()` incluyendo fallbacks
  - `tests/llm/test_cleanup.py` (25) — `needs_llm_cleanup()`, `cleanup_markdown()` con reintentos
  - `tests/scraper/test_markdown.py` (29) — `html_to_markdown()`, `chunk_markdown()`
- **`.coveragerc`** — excluye `runner.py` y `page.py` (requieren Playwright, pertenecen a tests de integración)

---

## [v0.9.2] - 2026-02-26

### Fixed
- **Security CI gates habilitados** ([#54](https://github.com/plater7/docrawl/issues/54)) — eliminado `|| true` de bandit y pip-audit en `security.yml`; bandit corre con `-ll` (solo HIGH severity), fallos ahora bloquean el build
- **`.dockerignore` añadido** ([#77](https://github.com/plater7/docrawl/issues/77)) — excluye `.git/`, `data/`, `tests/`, `worker/node_modules`, `audit-reports/`, `.env.*`; reduce build context y previene leakage accidental de secretos
- **Test deps separados de imagen de producción** ([#78](https://github.com/plater7/docrawl/issues/78)) — `requirements.txt` solo contiene deps runtime; creado `requirements-dev.txt` con `-r requirements.txt` + pytest stack; workflows actualizados
- **`cloudflared` pinneado a versión específica** ([#79](https://github.com/plater7/docrawl/issues/79)) — `cloudflare/cloudflared:latest` → `cloudflare/cloudflared:2024.12.2`
- **Coverage threshold añadido** ([#81](https://github.com/plater7/docrawl/issues/81)) — `--cov-fail-under=50` en `pytest.ini`; tests fallan si coverage cae por debajo del 50%

### Changed
- Workflows `lint.yml` y `test.yml` usan `requirements-dev.txt` para cache key y dependencias

---

## [v0.9.1] - 2026-02-26

### Fixed
- **`max_concurrent` ahora funciona** — semaphore-based concurrency con `asyncio.Semaphore` + `asyncio.Lock` para contadores compartidos; el parámetro ya no se ignora silenciosamente (#56)
- **Truncamiento silencioso del LLM eliminado** — `num_ctx` ahora se calcula dinámicamente (`max(2048, tokens_estimados + 1024)`) en vez del valor hardcodeado `8192`; chunk size reducido de 16KB a 6KB (#57)
- **Blocking sync HTTP en async context** — `_get_openrouter_models()` convertido a `async def` con `httpx.AsyncClient`; ya no bloquea el event loop (#59)
- **`asyncio.create_task` fire-and-forget** — añadido `done_callback` para loguear errores/cancelaciones; `JobManager.shutdown()` cancela y awaita todas las tareas activas vía FastAPI lifespan (#60)

### Changed
- `DEFAULT_CHUNK_SIZE` reducido de 16000 a 6000 caracteres para evitar context overflow en modelos pequeños
- Versión de la app: `0.1.0` → `0.9.1`

---

## [v0.9.0] - 2026-02-26

### Security (15 vulnerabilities fixed)
- **Path Traversal (CONS-001 / #47)** — `output_path` validated against `/data` boundary via `Path.resolve()`
- **Auth on all endpoints (CONS-002 / #48)** — `X-Api-Key` middleware; dev-local mode if `API_KEY` unset
- **Port 8002 bypass (CONS-003 / #49)** — API key middleware covers all non-exempt paths
- **Worker auth (CONS-004 / #50)** — Cloudflare Worker validates `X-Api-Key` before proxying
- **SSRF via Playwright (CONS-005 / #51)** — `validate_url_not_ssrf()` in `PageScraper.get_html()`, `fetch_markdown_native()`, `fetch_markdown_proxy()`
- **XSS via innerHTML (CONS-006 / #52)** — Replaced all untrusted `innerHTML` assignments with safe DOM API (`textContent`, `createElement`, `appendChild`)
- **Rate limiting (CONS-007 / #53)** — `slowapi` limiter: 10 req/min on `POST /api/jobs`; concurrent job cap via `MAX_CONCURRENT_JOBS`
- **Prompt injection (CONS-012 / #58)** — LLM prompts sanitized
- **XXE in sitemap parser (CONS-018 / #64)** — `defusedxml` replacing stdlib `xml.etree`
- **SSRF via markdown proxy (CONS-019 / #65)** — `validate_proxy_url` validator blocks non-HTTPS and private IPs
- **Parameter limits (CONS-020 / #66)** — Pydantic `Field` bounds on `delay_ms`, `max_concurrent`, `max_depth`, model name pattern
- **Data exfiltration (CONS-021 / #67)** — Warning banner when external provider selected
- **Security headers (CONS-022 / #68)** — `SecurityHeadersMiddleware`: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`
- **CORS (CONS-034 / #80)** — `CORSMiddleware` with `CORS_ORIGINS` env var; default deny

### Added
- `src/utils/security.py` — shared `validate_url_not_ssrf()` utility
- Concurrent job limit (`MAX_CONCURRENT_JOBS` env, default 5)
- Rate limiter error handler (429 JSON response)

### Tests
- 41 new tests covering security validators, SSRF utility, job manager, and routes
- Patch coverage raised from 11.57% to >70% on new code

---

## [v0.8.5] - 2026-02-20

### Added
- **UI Theme Selector** - Selector de tema con persistencia `localStorage`
  - 🌈 **SYNTHWAVE** (default) — neon magenta/cyan, Orbitron + VT323
  - 💚 **TERMINAL** — fósforo verde CRT, IBM Plex Mono, scanlines, viñeta
  - ⚪ **BASIC** — dark UI limpia y minimalista
- **Smart Sitemap Sampling** — sub-sitemaps genéricos se muestrean (5 primeros) antes de descargar todos; se saltan si <10% de URLs son relevantes
- **Regional Language Variants** — filtrado de idioma expandido con variantes regionales (`es-mx`, `en-au`, `fr-ca`, `de-at`, `zh-hk`, `pt-pt`, etc.)
- **Cloudflare Setup Docs** — `docs/SETUP.md` con instrucciones completas de Tunnel + Workers VPC
- **Global Sitemap Timeout** — descubrimiento limitado a 360s para evitar timeouts en sitemaps masivos
- **Language-aware URL filtering** — si la URL base tiene prefijo de idioma, excluye URLs sin prefijo (evita falsos positivos)

### Fixed
- **Path Prefix False Positive** — filtro `startswith` ahora requiere separador `/` para evitar matches parciales (p.ej. `/intune` no es prefijo de `/intune-for-education`)

---

## [v0.7.0-alpha] - 2026-02-19

### Added
- **Free Model Indicators** - Badges visuales para modelos gratuitos
  - 🏠 **Local** para Ollama (todos son locales/free)
  - 🆓 **Free** para OpenRouter/OpenCode modelos gratuitos
- **Priority Sorting** - Modelos free se muestran primero en selectores
- **Smart Hints** - Sugerencias priorizan modelos free disponibles
- **API Enhancement** - Nuevo campo `is_free` en `/api/models`

### Changed
- Selectores ordenan modelos: free → paid
- Hints dinámicos muestran badge de tipo (Local/Free)

---

## [v0.6.0-alpha] - 2026-02-19

### Added
- **Dynamic Model Suggestions** - Los hints muestran modelos disponibles del provider seleccionado
- **Language Filtering** - Filtrado de idioma para evitar docs multilingües (default: English)
  - Patrones: `/en/`, `/es/`, `/fr/`, `/de/`, `/ja/`, `/zh/`, `/pt/`
  - UI selector con opción "All languages"
- **Native Markdown Support** - `Accept: text/markdown` con fallback a proxy/Playwright
  - Track de fetch method: native, proxy, playwright
  - Stats en UI: `⚡ N via native markdown`

### Fixed
- **Syntax Error** - Corregido error en expresión ternaria de `routes.py:44`

### Tests
- Comprehensive tests for `filter.py` (language filtering, URL patterns)
- Comprehensive tests for `robots.py` (parsing, caching)

---

## [v0.5.10-alpha] - 2026-02-18

### Added
- **Multi-Provider Support** - Ollama, OpenRouter, OpenCode APIs
- **Model Filtering by Role** - UI muestra solo modelos apropiados por selector

### Fixed
- **Discovery Tests** - Alineados con estrategia cascade

---

## [v0.5.5-alpha] - 2026-02-14

### Fixed
- **ASGI Crash** - `GeneratorExit` handling en `event_stream()` 
- **SSE Stability** - Ping cada 15s, frontend reconnection logic
- **Discovery Cascade** - Se detiene en primera estrategia exitosa
- **Docker Logs** - Todos los eventos SSE logueados con timestamps

---

## [v0.5.0-alpha] - 2026-02-14

### Added
- **Ollama Inference Parameters** - `num_ctx`, `num_predict`, `temperature`, `num_batch`
- Dynamic timeouts basados en tamaño de chunk

---

## [v0.4.0-alpha] - 2026-02-14

### Added
- **DOM Pre-cleaning** - Remueve nav, footer, sidebar, cookie banners
- **Content Extraction** - Focus en `main`, `article`, `[role='main']`
- **Smart Skip** - Chunks limpios saltan LLM cleanup

### Changed
- Chunk size: 8KB → 16KB
- Timeouts: fijo 120s → dinámico 45-90s

---

## [v0.3.0-alpha] - 2026-02-14

### Added
- **Phase Banner** - Indicador visual de fase activa con colores
- **SSE Enriched Events** - `phase_change`, `log` con `active_model`, `progress`
- **Log Badges** - Colores por fase en cada entrada

---

## [v0.2.0-alpha] - 2026-02-14

### Added
- **Multi-Model Selectors** - 3 modelos por rol (crawl, pipeline, reasoning)
- **Smart Output Path** - Auto-generado desde URL

---

## [v0.1.0-alpha] - 2026-02-10

### Added
- **Cascade Discovery** - sitemap.xml → nav/sidebar → recursive crawl
- **Deterministic + LLM Filtering** - URL filtering pipeline
- **Playwright Scraping** - Headless Chromium rendering
- **LLM Cleanup** - Markdown cleanup por chunks con retry
- **SSE Progress** - Real-time updates
- **Job Cancellation** - Stop anytime, keep processed
- **robots.txt Support** - Respetar crawl-delay
- **Cloudflare Exposure** - Tunnel + Workers VPC

---

> 🤖 **Note**: This project uses AI-assisted development with human review.
> 
> **Bot**: OpenCode 🤖 (model: glm-5-free)
>
> _Co-authored-by: OpenCode 🤖 <opencode@anomaly.la>_
