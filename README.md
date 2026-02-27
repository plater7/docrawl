<p align="center">
  <img src="https://img.shields.io/badge/version-v0.9.6b-blue?style=for-the-badge" alt="version">
  <img src="https://img.shields.io/badge/python-3.12-yellow?style=for-the-badge&logo=python" alt="python">
  <a href="https://github.com/plater7/docrawl/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/plater7/docrawl/test.yml?branch=main&style=for-the-badge&label=tests&logo=github" alt="tests"></a>
  <a href="https://codecov.io/gh/plater7/docrawl"><img src="https://img.shields.io/codecov/c/github/plater7/docrawl?style=for-the-badge&logo=codecov" alt="coverage"></a>
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="license">
  <img src="https://img.shields.io/badge/ai--assisted-✓-purple?style=for-the-badge" alt="ai-assisted">
</p>

<h1 align="center">🕷️ Docrawl</h1>

<p align="center">
  <strong>Transforma cualquier documentación web en Markdown limpio y organizado</strong>
</p>

<p align="center">
  <em>Powered by LLMs • Docker-ready • Real-time progress</em>
</p>

---

## ✨ Features

| Feature | Descripción |
|---------|-------------|
| 🔍 **Discovery Inteligente** | Sitemap → Navegación → Crawl recursivo en cascada |
| 🧠 **Filtrado LLM** | Solo URLs relevantes, ordenadas por importancia |
| 📝 **Markdown Limpio** | DOM pre-cleaning + LLM cleanup por chunks |
| ⚡ **Native Markdown** | `Accept: text/markdown` cuando el server lo soporta |
| 🌐 **Multi-Provider** | Ollama (local), OpenRouter, OpenCode APIs |
| 🌍 **Language Filter** | Filtra por idioma (default: English only) |
| 🎨 **UI Themes** | Synthwave, Terminal y Basic — selector persistido por localStorage |
| 📊 **Real-time UI** | SSE con phases, modelos y progreso en vivo |
| 🐳 **Docker-ready** | Un comando: `docker compose up` |

## 📋 System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **RAM** | 4GB | 8GB+ |
| **CPU** | 2 cores | 4+ cores |
| **Disk** | 5GB free | 20GB+ free |
| **Docker** | 20.10+ | Latest |
| **Ollama** | Optional | 1 model pulled |

> 💡 **Note**: Without Ollama, you'll need to use OpenRouter or OpenCode API (set keys in `.env`)

## 🚀 Quick Start

```bash
# 1. Clone and verify prerequisites
git clone https://github.com/plater7/docrawl.git
cd docrawl
./setup.sh  # Checks Docker, memory, creates ./data directory

# 2. Setup Ollama (if using local LLMs)
ollama serve
ollama pull mistral:7b        # Crawl model (fast)
ollama pull qwen2.5:14b       # Pipeline model (balanced)

# 3. Start Docrawl
docker compose up --build

# 4. Open http://localhost:8002
```

> ⚠️ **Troubleshooting**: See [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) for common issues.

## 🎯 Cómo Funciona

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: https://docs.example.com                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔍 DISCOVERY (cascade)                                         │
│  sitemap.xml → nav/sidebar → recursive crawl                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  🧹 FILTERING                                                    │
│  • Deterministic: same domain, exclude .pdf/.zip/etc           │
│  • Language: /en/ only (configurable)                          │
│  • LLM: filter irrelevant URLs, sort by relevance              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  📄 SCRAPING                                                     │
│  1. Try native markdown (Accept: text/markdown)                │
│  2. Fallback to markdown proxy (optional)                      │
│  3. Final fallback: Playwright → html_to_md                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ✨ LLM CLEANUP                                                  │
│  • DOM pre-cleaning (remove nav, footer, sidebar)              │
│  • Chunking by headings (16KB chunks)                          │
│  • LLM cleanup per chunk (smart skip for clean chunks)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  💾 OUTPUT                                                       │
│  ./data/example.com/                                            │
│  ├── introduction.md                                            │
│  ├── getting-started.md                                         │
│  ├── api/                                                       │
│  │   ├── endpoints.md                                           │
│  │   └── authentication.md                                      │
│  └── _index.md                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🤖 Modelos

Docrawl usa **3 modelos especializados** por rol:

| Rol | Uso | Tamaño sugerido |
|-----|-----|-----------------|
| 🏃 **Crawl** | Discovery & filtrado de URLs | 3B-8B (rápido) |
| 🔧 **Pipeline** | Cleanup de markdown | 6B-14B (balanceado) |
| 🧠 **Reasoning** | Análisis complejo (futuro) | 14B+ (potente) |

**Hints dinámicos** - La UI sugiere modelos basados en los disponibles en tu provider.

### Providers Soportados

| Provider | Tipo | Config |
|----------|------|--------|
| 🦙 **Ollama** | Local (gratis) | Corre en `localhost:11434` |
| 🌐 **OpenRouter** | API | Set `OPENROUTER_API_KEY` |
| 💎 **OpenCode** | API | Set `OPENCODE_API_KEY` |

## 📡 API

```
GET  /                          # UI dashboard
GET  /api/info                  # App metadata: versión, repo, author, models_used
GET  /api/providers             # Lista providers y estado
GET  /api/models?provider=...   # Modelos disponibles
GET  /api/health/ready          # Readiness check (Ollama, disco, permisos)
POST /api/jobs                  # Crear job
GET  /api/jobs/{id}/events      # SSE stream
POST /api/jobs/{id}/cancel      # Cancelar
GET  /api/jobs/{id}/status      # Estado actual
```

## 🔧 Configuración

### Job Options

| Campo | Default | Descripción |
|-------|---------|-------------|
| `language` | `"en"` | Filtrar por idioma (`en`, `es`, `all`, etc.) |
| `max_depth` | `5` | Profundidad máxima de crawl |
| `delay_ms` | `500` | Delay entre requests |
| `max_concurrent` | `3` | Requests concurrentes |
| `respect_robots_txt` | `true` | Respetar robots.txt |
| `use_native_markdown` | `true` | Intentar `Accept: text/markdown` |
| `use_markdown_proxy` | `false` | Usar proxy como fallback |

## 🎨 UI Themes

El selector de tema persiste en `localStorage`. Tres opciones disponibles:

| Tema | Descripción |
|------|-------------|
| **SYNTHWAVE** (default) | Neon magenta/cyan, fuente Orbitron + VT323, estética retro-futurista |
| **TERMINAL** | Fósforo verde CRT, IBM Plex Mono, scanlines y viñeta retro |
| **BASIC** | Dark UI limpia y minimalista |

## 🌐 Exponer a Internet

Docrawl se puede exponer vía **Cloudflare Tunnel + Workers VPC** sin IP pública:

```
[Internet] → [Worker] → (VPC binding) → [Tunnel] → [docrawl:8002]
```

Ver [SETUP.md](./docs/SETUP.md) para instrucciones completas.

## 📁 Estructura

```
docrawl/
├── src/
│   ├── main.py              # FastAPI app
│   ├── api/                 # REST + SSE endpoints
│   ├── crawler/             # Discovery, filter, robots
│   ├── scraper/             # Playwright, markdown
│   ├── llm/                 # Client, filter, cleanup
│   ├── jobs/                # Manager, runner
│   └── ui/                  # Dashboard HTML
├── worker/                  # Cloudflare Worker
├── tests/                   # Pytest suite
└── docker/                  # Dockerfile
```

## 🧪 Testing

```bash
pytest tests/ -v
```

## 📜 Changelog

Ver [CHANGELOG.md](./CHANGELOG.md) para historial de versiones.

## 🗺️ Roadmap de Mejoras

### Estado del Proyecto (Feb 2026)

| Métrica | Cantidad |
|---------|----------|
| **Issues** | 113+ (total) · 24 abiertos |
| **PRs** | 119+ (total) · 2 abiertos |
| **Branches** | 3 activos |
| **Tests** | 335 passing · 58.68% coverage |
| **Releases** | v0.9.1 → v0.9.6b (7 releases) |

### Auditoría Multi-Agente — Progreso

| Wave | Estado | Hallazgos |
|------|--------|-----------|
| 0 — GitHub Infra | ✅ DONE | — |
| 1 — Core Code Review | ✅ DONE | 174 (15 critical) |
| 2 — Infra & DevOps | ✅ DONE | 70 (5 critical) |
| 3 — AI/ML Engineering | ✅ DONE | 48 (7 critical) |
| 4 — Quality & Security | ✅ DONE | 90 (13 critical) |
| 5 — Docs & DX | ✅ DONE | 50 (6 critical) |
| 6 — Architecture | ✅ DONE | 12 (5 critical), Score: 6/10 |
| 7 — Synthesis | ✅ DONE | 444→62 findings |

---

### 🎯 Roadmap Priorizado

> Estado sincronizado con [GitHub Issues](https://github.com/plater7/docrawl/issues) · 22 issues abiertos (11 P1 + 11 P3)

#### P0 — Bloqueantes de Producción ✅ Todos resueltos

| # | Hallazgo | Severidad | Estado |
|---|----------|-----------|--------|
| 1 | Path Traversal via `output_path` | Critical | ✅ Fixed v0.9.0 (#47) |
| 2 | SSRF via Playwright a URLs internas | Critical | ✅ Fixed v0.9.0 (#51) |
| 3 | Sin autenticación en endpoints | Critical | ✅ Fixed v0.9.0 (#48) |
| 4 | Worker Cloudflare sin auth | Critical | ✅ Fixed v0.9.0 (#50) |
| 5 | XSS via `innerHTML` con datos SSE | Critical | ✅ Fixed v0.9.0 (#52) |
| 6 | Prompt injection via contenido scrapeado | Critical | ✅ Fixed v0.9.0 (#58) + v0.9.5 (#94) |
| 7 | Sin rate limiting ni job concurrency cap | Critical | ✅ Fixed v0.9.0 (#53) |
| 8 | Puerto 8002 expuesto en 0.0.0.0 | Critical | ✅ Fixed v0.9.0 (CORS + middleware) |
| 9 | Blocking sync HTTP en async context | Major | ✅ Fixed v0.9.1 (#59) |
| 10 | `max_concurrent` nunca implementado | Major | ✅ Fixed v0.9.1 (#56) |

**P0: 10/10 resueltos** — sin bloqueantes críticos de producción

#### P1 — Alta Prioridad (11 issues abiertos)

**Resueltos:**

| Item | Estado |
|------|--------|
| No `.dockerignore` | ✅ Fixed v0.9.2 (#77) |
| Test deps en imagen runtime | ✅ Fixed v0.9.2 (#78) |
| Security CI gates deshabilitados | ✅ Fixed v0.9.2 (#54) |
| `cloudflared:latest` unpinned | ✅ Fixed v0.9.2 (#79) |
| `num_ctx` insuficiente para chunks | ✅ Fixed v0.9.1 (#57) |
| Atomic file writes en async context | ✅ Fixed v0.9.6 (#99) |
| CORS no configurado | ✅ Fixed v0.9.0 (#80) |
| `print()` mixed with logging | ✅ Fixed v0.9.6 (#89) |

**Pendientes (GitHub issues abiertos):**

| Issue | Hallazgo | Label |
|-------|----------|-------|
| [#61](https://github.com/plater7/docrawl/issues/61) | Memory leak — jobs completados nunca se eliminan del dict | bug |
| [#62](https://github.com/plater7/docrawl/issues/62) | Race condition en `JobManager._jobs` — dict sin `asyncio.Lock` | bug |
| [#63](https://github.com/plater7/docrawl/issues/63) | Resource leak Playwright — browsers no cerrados en error | bug |
| [#69](https://github.com/plater7/docrawl/issues/69) | Sin connection pooling en cliente LLM — 150+ TCP connections por job | performance |
| [#70](https://github.com/plater7/docrawl/issues/70) | `_generate_index` produce links rotos — separador `_` en vez de `/` | bug |
| [#71](https://github.com/plater7/docrawl/issues/71) | `reasoning_model` validado pero nunca invocado en runner | bug |
| [#72](https://github.com/plater7/docrawl/issues/72) | Parser JSON frágil para output del LLM — falla >30% con modelos 7B | bug |
| [#73](https://github.com/plater7/docrawl/issues/73) | Exception handler de cleanup es dead code — `pages_partial` siempre 0 | bug |
| [#74](https://github.com/plater7/docrawl/issues/74) | Sin crash recovery — restart pierde todos los jobs activos | bug |
| [#75](https://github.com/plater7/docrawl/issues/75) | `__import__('os')` inline en `routes.py` — anti-patrón crítico | refactor |
| [#76](https://github.com/plater7/docrawl/issues/76) | Sync file writes en event loop — bloqueo en Docker volumes | performance |

#### P2 — Media Prioridad ✅ Todos resueltos

| Item | Estado |
|------|--------|
| No caching de model lists | ✅ Fixed v0.9.5/v0.9.6 (#92) |
| Case-sensitive path handling (robots.txt) | ✅ Fixed v0.9.5 |
| Retry backoff fijo → exponencial | ✅ Fixed v0.9.6 (#100) |
| MAX_RETRIES insuficiente | ✅ Fixed v0.9.6 (#94) |
| Dead code (`generate_legacy`, etc.) | ✅ Fixed v0.9.5 (#116) |
| 3 funciones `_generate_*` duplicadas | ✅ Fixed v0.9.5 (#116) |

#### P3 — Baja Prioridad / Nice to Have (11 issues abiertos)

| Issue | Hallazgo |
|-------|----------|
| [#103](https://github.com/plater7/docrawl/issues/103) | Sin API versioning |
| [#104](https://github.com/plater7/docrawl/issues/104) | Health check no funcional |
| [#105](https://github.com/plater7/docrawl/issues/105) | Sin tracking de tokens |
| [#106](https://github.com/plater7/docrawl/issues/106) | Sin pre-commit hooks |
| [#107](https://github.com/plater7/docrawl/issues/107) | Sin conventional commits |
| [#108](https://github.com/plater7/docrawl/issues/108) | Sin deployment pipeline |
| [#109](https://github.com/plater7/docrawl/issues/109) | Sin structured logging |
| [#110](https://github.com/plater7/docrawl/issues/110) | Inconsistencia de idioma en docs |
| [#111](https://github.com/plater7/docrawl/issues/111) | Multi-provider no documentado |
| [#112](https://github.com/plater7/docrawl/issues/112) | Playwright innecesario en CI |
| [#113](https://github.com/plater7/docrawl/issues/113) | Info leakage en errores |

---

### Progreso de Fixes

| PR | Milestone | Issues | Estado |
|----|-----------|--------|--------|
| [#82](https://github.com/plater7/docrawl/pull/82) | v0.9.0 Security Hardening | 14 (P0/P1 security) | ✅ Merged |
| [#83](https://github.com/plater7/docrawl/pull/83) | v0.9.1 Code Quality | 4 (async, concurrency, context) | ✅ Merged |
| [#84](https://github.com/plater7/docrawl/pull/84) | v0.9.2 Infrastructure | 5 (dockerignore, CI, cloudflared, coverage) | ✅ Merged |
| [#85](https://github.com/plater7/docrawl/pull/85) | v0.9.4 Testing | 1 (coverage >80%) | ✅ Merged |
| [#116](https://github.com/plater7/docrawl/pull/116) | v0.9.5 Backlog P2 | 16 (P2 backlog) | ✅ Merged |
| [#119](https://github.com/plater7/docrawl/pull/119) | v0.9.6 P2 Followup | 5 (#89, #92, #94, #99, #100) | ✅ Merged |
| [#120](https://github.com/plater7/docrawl/pull/120) | v0.9.6a UI Meta | `/api/info` + UI footer | ✅ Merged |
| [#121](https://github.com/plater7/docrawl/pull/121) | v0.9.6b Footer Fix | footer `position: fixed` | ✅ Merged |

**Estado actual:** P0 ✅ · P1 11 open · P2 ✅ · P3 11 open · Tests: 335 passing · Coverage: 58.68%

### Cómo Contribuir

1. Fork → Branch → PR
2. Sign commits: `git commit -s`
3. AI-assisted code welcome with human review
4. Revisa los [issues P0](https://github.com/plater7/docrawl/labels/P0) primero

## 🤝 Contributing

1. Fork → Branch → PR
2. Sign commits: `git commit -s`
3. AI-assisted code welcome with human review

## 🔒 Security (v0.9.0)

v0.9.0 fixes 15 security vulnerabilities identified in a pre-production audit:

| # | Issue | Fix |
|---|-------|-----|
| CONS-001 | Path traversal via `output_path` | `Path.resolve()` boundary check |
| CONS-002 | No authentication | `X-Api-Key` middleware |
| CONS-005 | SSRF via Playwright | `validate_url_not_ssrf()` on all fetch paths |
| CONS-006 | XSS via `innerHTML` | Replaced with safe DOM API |
| CONS-007 | No rate limiting | `slowapi` 10 req/min + job concurrency cap |
| CONS-018 | XXE in sitemap parser | `defusedxml` replacing stdlib |
| CONS-019 | SSRF via markdown proxy | Proxy URL validator (HTTPS + private IP block) |
| CONS-022 | No security headers | `SecurityHeadersMiddleware` (CSP, X-Frame, etc.) |
| CONS-034 | No CORS | `CORSMiddleware` with `CORS_ORIGINS` env var |

See [`SECURITY.md`](SECURITY.md) for the full disclosure and [`CHANGELOG.md`](CHANGELOG.md) for all fixes.

---

## 📄 License

MIT

---

> 🤖 **AI-Assisted Development**: Este proyecto fue desarrollado con asistencia de IA y revisión humana.
> 
> **Bot**: OpenCode 🤖 (model: glm-5-free)
>
> _Co-authored-by: OpenCode 🤖 <opencode@anomaly.la>_

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/plater7">plater7</a> + OpenCode 🤖 (glm-5-free)</sub>
</p>
