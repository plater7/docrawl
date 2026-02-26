<p align="center">
  <img src="https://img.shields.io/badge/version-v0.9.2-blue?style=for-the-badge" alt="version">
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
GET  /api/providers             # Lista providers y estado
GET  /api/models?provider=...   # Modelos disponibles
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
| **Issues** | 80 (total) |
| **PRs** | 36 (total) / 7 (abiertos) |
| **Branches** | 17 |

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

#### P0 — Bloqueantes de Producción (14 issues)

| # | Hallazgo | Severidad | Archivo(s) |
|---|----------|-----------|------------|
| 1 | Path Traversal via `output_path` | Critical | `models.py:13`, `runner.py:285` |
| 2 | SSRF via Playwright a URLs internas | Critical | `page.py`, `discovery.py` |
| 3 | Sin autenticación en endpoints | Critical | toda la API |
| 4 | Worker Cloudflare sin auth | Critical | `worker/src/index.js` |
| 5 | XSS via `innerHTML` con datos SSE | Critical | `index.html:1274,1332` |
| 6 | Prompt injection via contenido scrapeado | Critical | `cleanup.py`, `filter.py` |
| 7 | Sin rate limiting ni job concurrency cap | Critical | `routes.py`, `manager.py` |
| 8 | Puerto 8002 expuesto en 0.0.0.0 | Critical | `docker-compose.yml:11` |
| 9 | Blocking sync HTTP en async context | Major | `client.py:97` |
| 10 | `max_concurrent` nunca implementado | Major | `runner.py:295` |
| 11 | `_generate_index` links rotos | Major | `runner.py:579` |
| 12 | Chunk overlap → contenido duplicado | Major | `markdown.py:126` |
| 13 | Estado in-memory sin eviction | Major | `manager.py` |
| 14 | Playwright resource leaks | Major | `page.py`, `discovery.py` |

#### P1 — Alta Prioridad (21 issues)

- No `.dockerignore` — build context inflado
- Test deps en imagen runtime
- Security CI gates deshabilitados
- `cloudflared:latest` unpinned
- Sin backup strategy para `/data`
- `num_ctx: 8192` insuficiente para 16KB chunks
- Sync file writes en async context
- Health check no funcional
- No CORS configuración
- No API versioning
- Browser no almacenado/inicializado correctamente
- print() mixed with logging

#### P2 — Media Prioridad

- Dead code (`generate_legacy`, etc.)
- 3 funciones `_generate_*` duplicadas
- Sin connection pooling
- No caching de model lists
- Prompts sin few-shot examples
- Case-sensitive path handling (robots.txt)

#### P3 — Baja Prioridad / Nice to Have

- UI refactoring (index.html ~1500 líneas)
- runner.py monolítico (~465 líneas)
- ADRs para decisiones arquitectónicas
- Conventional commits
- Branch protection rules
- Pre-commit hooks

---

### Progreso de Fixes

| PR | Milestone | Issues | Estado |
|----|-----------|--------|--------|
| [#82](https://github.com/plater7/docrawl/pull/82) | v0.9.0 Security Hardening | 14 (P0/P1 security) | 🔄 Open — request changes |
| [#83](https://github.com/plater7/docrawl/pull/83) | v0.9.1 Code Quality | 4 (async, concurrency, context) | ✅ Merged |
| [#84](https://github.com/plater7/docrawl/pull/84) | v0.9.2 Infrastructure | 5 (dockerignore, CI, cloudflared, coverage) | ✅ Merged |
| [#85](https://github.com/plater7/docrawl/pull/85) | v0.9.4 Testing | 1 (coverage >80%) | 🔄 Open — ready to review |

**Cobertura actual de P0 (14 issues):** PRs #83 + #84 ✅ resuelven 2/14 directos · PR #82 pendiente cubre 10/14 → 2 resueltos, 10 en revisión.

### Cómo Contribuir

1. Fork → Branch → PR
2. Sign commits: `git commit -s`
3. AI-assisted code welcome with human review
4. Revisa los [issues P0](https://github.com/plater7/docrawl/labels/P0) primero

## 🤝 Contributing

1. Fork → Branch → PR
2. Sign commits: `git commit -s`
3. AI-assisted code welcome with human review

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
