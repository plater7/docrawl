# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
> _Co-authored-by: OpenCode 🤖 <opencode@anomaly.la>_
