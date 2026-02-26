# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
