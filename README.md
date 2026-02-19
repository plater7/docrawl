<p align="center">
  <img src="https://img.shields.io/badge/version-v0.7.0--alpha-blue?style=for-the-badge" alt="version">
  <img src="https://img.shields.io/badge/python-3.12-yellow?style=for-the-badge&logo=python" alt="python">
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
| 📊 **Real-time UI** | SSE con phases, modelos y progreso en vivo |
| 🐳 **Docker-ready** | Un comando: `docker compose up` |

## 🚀 Quick Start

```bash
# 1. Asegurate de tener Ollama corriendo
ollama serve
ollama pull mistral  # o tu modelo favorito

# 2. Clona y levanta
git clone https://github.com/plater7/docrawl.git
cd docrawl
docker compose up --build

# 3. Abre http://localhost:8002
```

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

## 📄 License

MIT

---

> 🤖 **AI-Assisted Development**: Este proyecto fue desarrollado con asistencia de IA y revisión humana.
>
> _Co-authored-by: OpenCode 🤖 <opencode@anomaly.la>_

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/plater7">plater7</a> + OpenCode 🤖</sub>
</p>
