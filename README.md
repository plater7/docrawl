<p align="center">
  <img src="https://img.shields.io/badge/version-v0.10.0-blue?style=for-the-badge" alt="version">
  <img src="https://img.shields.io/badge/python-3.12-yellow?style=for-the-badge&logo=python" alt="python">
  <a href="https://github.com/plater7/docrawl/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/plater7/docrawl/test.yml?branch=main&style=for-the-badge&label=tests&logo=github" alt="tests"></a>
  <a href="https://codecov.io/gh/plater7/docrawl"><img src="https://img.shields.io/codecov/c/github/plater7/docrawl?style=for-the-badge&logo=codecov" alt="coverage"></a>
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="license">
  <img src="https://img.shields.io/badge/ai--assisted-✓-purple?style=for-the-badge" alt="ai-assisted">
  <a href="https://bestpractices.coreinfrastructure.org/projects"><img src="https://img.shields.io/badge/OpenSSF-Best_Practices-4ac151?style=for-the-badge&logo=openssf" alt="OpenSSF Best Practices"></a>
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
| 🌐 **LM Studio | Local (gratis) | Set `LMSTUDIO_URL` & `LMSTUDIO_API_KEY` (opcional) |

### Configuración de Providers

#### Ollama (local, sin costo)

```bash
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Descargar modelos recomendados
ollama pull mistral:7b        # crawl model (rápido)
ollama pull qwen2.5:14b       # pipeline model (balanceado)
```

No requiere configuración adicional. La URL por defecto es `http://localhost:11434`.
En Docker, se accede via `http://host.docker.internal:11434` (configurado automáticamente).

#### OpenRouter (API cloud, modelos gratuitos disponibles)

```bash
# En .env o variable de entorno:
export OPENROUTER_API_KEY=sk-or-...
```

Luego selecciona cualquier modelo en la UI con el prefijo `openrouter/`. Los modelos marcados con 🆓 son gratuitos.

#### OpenCode (API cloud)

```bash
# En .env o variable de entorno:
export OPENCODE_API_KEY=...
```

Modelos disponibles: `opencode/claude-sonnet-4-5`, `opencode/claude-haiku-4-5`, `opencode/gpt-5-nano`, y más.

#### LM Studio
```bash
# En .env o variable de entorno:
export LMSTUDIO_URL=...
export LMSTUDIO_API_KEY=...
```
> 💡 **Tip**: Puedes usar proveedores distintos para cada rol (e.g., Ollama para crawl y OpenRouter para pipeline).

## 📡 API

```
GET  /                              # UI dashboard
GET  /api/info                      # App metadata: versión, repo, author, models_used
GET  /api/providers                 # Lista providers y estado
GET  /api/models?provider=...       # Modelos disponibles
GET  /api/health/ready              # Readiness check (Ollama, disco, permisos)
POST /api/jobs                      # Crear job
GET  /api/jobs/{id}/events          # SSE stream
POST /api/jobs/{id}/cancel          # Cancelar
GET  /api/jobs/{id}/status          # Estado actual
POST /api/jobs/{id}/pause           # Pausar job (PR 3.1)
POST /api/jobs/{id}/resume          # Reanudar job pausado (PR 3.1)
POST /api/jobs/resume-from-state    # Nuevo job desde checkpoint .job_state.json (PR 3.1)
GET  /api/converters                # Listar convertidores HTML→MD registrados (PR 3.4)
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
| `use_page_pool` | `true` | Reusar páginas Playwright entre requests — PR 1.2 |
| `use_http_fast_path` | `true` | Intentar HTTP plano antes de Playwright — PR 1.3 |
| `filter_sitemap_by_path` | `true` | Filtrar URLs del sitemap al subpath base — PR 1.3 |
| `use_cache` | `false` | Caché de páginas en disco con TTL 24h — PR 2.4 |
| `output_format` | `"markdown"` | Formato de salida: `markdown` o `json` — PR 3.2 |
| `use_pipeline_mode` | `false` | Pipeline productor/consumidor async — PR 3.3 |
| `converter` | `"markdownify"` | Convertidor HTML→Markdown — PR 3.4 |

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

## 🤝 Contributing

1. Fork → Branch → PR
2. Sign commits: `git commit -s`
3. AI-assisted code welcome with human review

---

## 📄 License

MIT

---
<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/plater7">plater7</a> + Claude Code 🤖 + OpenCode 🤖</sub>
</p>

