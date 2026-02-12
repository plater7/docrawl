# CLAUDE.md — Docrawl



## Qué es Docrawl

Una aplicación web dockerizada que crawlea sitios de documentación y los convierte a archivos Markdown organizados. Usa Playwright para renderizar páginas, markdownify para conversión HTML→MD, y Ollama (modelos locales) para filtrado inteligente de URLs y limpieza de contenido.

## Stack

- **Python 3.12**
- **FastAPI** — API + servir UI estática
- **Playwright** — renderizado de páginas (headless Chromium)
- **markdownify** — conversión HTML→Markdown (sin LLM)
- **Ollama** — LLM local vía API REST (corre en el host, expuesto en `host.docker.internal:11434`)
- **SSE (Server-Sent Events)** — progreso en tiempo real a la UI
- **Docker** — container único con docker-compose

## Principio rector

**Simplicidad le gana a todo.** Preferir soluciones directas sobre abstracciones elegantes. Código legible sobre código clever. Menos dependencias, mejor.

## Arquitectura

```
[Browser/UI :8002] → [FastAPI container] → [Ollama en host :11434]
                          │
                          ├── Discovery (cascada)
                          ├── Filtrado (determinístico + LLM)
                          ├── Scraping (Playwright + markdownify)
                          ├── LLM cleanup por chunks
                          └── Output → /data/{path_estructura}/*.md
```

### Flujo completo de un job

1. Usuario ingresa: URL raíz, modelo Ollama, path output, configuración de rate limiting
2. **Discovery** (cascada, se detiene en el primer método exitoso):
   - Intenta parsear `sitemap.xml`
   - Si no hay, parsea el nav/sidebar de la página con Playwright
   - Fallback: crawl recursivo por links internos con depth limit
3. **Filtrado determinístico**:
   - Solo URLs del mismo dominio/subpath que la URL raíz
   - Excluir extensiones no-doc: `.pdf`, `.zip`, `.png`, `.jpg`, `.mp4`, etc.
   - Deduplicar (normalizar trailing slashes, fragments, query params)
   - Excluir patrones comunes no-doc: `/blog/`, `/changelog/`, `/api-reference/` (configurable)
4. **Filtrado LLM**:
   - Se le pasa la lista prefiltrada de URLs al modelo Ollama
   - El LLM filtra URLs irrelevantes y propone orden de procesamiento
   - Si el LLM falla, se usa la lista prefiltrada tal cual
5. **Scraping página por página**:
   - Playwright navega a cada URL
   - Se extrae el HTML del body
   - markdownify convierte a Markdown (sin LLM)
   - Respetando delay entre requests y concurrencia máxima configurada
6. **LLM cleanup por chunks**:
   - Si el MD de una página excede el context window del modelo, se divide en chunks
   - Cada chunk se envía al LLM para limpieza (quitar residuos de nav, footers, ads, formateo)
   - Si un chunk falla (timeout, context overflow): retry con backoff exponencial (max 3 intentos)
   - Si sigue fallando: se guarda el markdown crudo sin cleanup y se loguea el error
   - **El job nunca se aborta por un chunk o página fallida**
7. **Output**:
   - Se respeta la estructura de URLs: `docs.example.com/guide/install` → `{output_path}/guide/install.md`
   - Se genera un `_index.md` en la raíz con tabla de contenidos y links relativos
   - Se reportan páginas/chunks que fallaron

### Cancelación de jobs

- El usuario puede cancelar un job desde la UI en cualquier momento
- Al cancelar, se conserva todo lo ya procesado en disco
- El job reporta estado final: completado parcialmente, qué se procesó y qué no

## API endpoints

```
GET  /                          → UI estática
GET  /api/models                → Lista modelos Ollama disponibles (proxy a GET host:11434/api/tags)
POST /api/jobs                  → Crear y lanzar un job de crawl
GET  /api/jobs/{id}/events      → SSE stream de progreso del job
POST /api/jobs/{id}/cancel      → Cancelar job
GET  /api/jobs/{id}/status      → Estado actual del job
```

### Payload de POST /api/jobs

```json
{
  "url": "https://docs.example.com",
  "model": "llama3.2",
  "output_path": "/data/example-docs",
  "delay_ms": 500,
  "max_concurrent": 3,
  "max_depth": 5,
  "respect_robots_txt": true
}
```

### Eventos SSE (GET /api/jobs/{id}/events)

```
event: discovery
data: {"phase": "sitemap", "status": "trying"}

event: discovery
data: {"phase": "sitemap", "status": "failed", "reason": "404"}

event: discovery
data: {"phase": "nav_parse", "status": "success", "urls_found": 47}

event: filtering
data: {"total": 47, "after_basic": 42, "after_llm": 38}

event: page_start
data: {"url": "https://docs.example.com/guide/install", "index": 1, "total": 38}

event: page_done
data: {"url": "https://docs.example.com/guide/install", "status": "ok", "chunks_failed": 0}

event: page_done
data: {"url": "https://docs.example.com/guide/advanced", "status": "partial", "chunks_failed": 2, "chunks_total": 5}

event: page_error
data: {"url": "https://docs.example.com/guide/broken", "error": "timeout"}

event: job_done
data: {"status": "completed", "pages_ok": 35, "pages_partial": 2, "pages_failed": 1, "output_path": "/data/example-docs"}

event: job_cancelled
data: {"pages_completed": 20, "pages_total": 38, "output_path": "/data/example-docs"}
```

## UI

HTML + CSS + JS vanilla. Sin frameworks. Un solo archivo `index.html` servido por FastAPI.

### Elementos:
- **URL raíz** — input text
- **Modelo Ollama** — dropdown que se puebla con GET /api/models al cargar la página
- **Path de output** — input text, default `/data/output`
- **Delay entre requests** — input number (ms), default 500
- **Max concurrent pages** — input number, default 3
- **Max depth** (crawl recursivo) — input number, default 5
- **Respetar robots.txt** — checkbox, default on
- **Botón Start** — lanza el job
- **Botón Cancel** — aparece cuando hay job en curso
- **Log de progreso** — área de texto/consola que muestra eventos SSE en tiempo real
- **Resumen final** — estadísticas al terminar

## Docker

### Dockerfile
- Base: `python:3.12-slim`
- Instalar Playwright + Chromium
- Copiar código
- Exponer puerto 8002

### docker-compose.yml
- Servicio principal: `docrawl`
- Puerto: `8002:8002`
- Volume: `./data:/data` (para persistir output)
- Extra host: `host.docker.internal:host-gateway` (acceso a Ollama en el host)
- Variable de entorno: `OLLAMA_URL=http://host.docker.internal:11434`
- Servicio sidecar: `cloudflared` (Cloudflare Tunnel)

## Estructura del proyecto

```
docrawl/
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── src/
│   ├── main.py              # FastAPI app, monta rutas y sirve UI
│   ├── api/
│   │   ├── routes.py         # Endpoints REST + SSE
│   │   └── models.py         # Pydantic models para request/response
│   ├── crawler/
│   │   ├── discovery.py      # Cascada: sitemap → nav → crawl recursivo
│   │   ├── filter.py         # Filtrado determinístico de URLs
│   │   └── robots.py         # Parser de robots.txt
│   ├── scraper/
│   │   ├── page.py           # Playwright: navegar + extraer HTML
│   │   └── markdown.py       # markdownify: HTML → MD + chunking
│   ├── llm/
│   │   ├── client.py         # Cliente HTTP para Ollama API
│   │   ├── filter.py         # Prompt de filtrado de URLs
│   │   └── cleanup.py        # Prompt de cleanup de MD por chunks
│   ├── jobs/
│   │   ├── manager.py        # Crear, cancelar, trackear jobs
│   │   └── runner.py         # Orquestación del flujo completo
│   └── ui/
│       └── index.html        # UI estática
├── worker/
│   ├── wrangler.jsonc        # Config Cloudflare Worker
│   ├── package.json
│   └── src/
│       └── index.js          # Worker proxy via VPC Service binding
├── requirements.txt
├── .gitignore
├── .env.example
├── README.md
└── CLAUDE.md
```

## Referencia: repos originales

Este proyecto se inspira en dos repos de scraping con LLM. El código de preprocessado (cleanup JS, conversión HTML) y la estructura de prompts son útiles como referencia:

- **llm-scraper (TS)**: Usa Playwright + AI SDK de Vercel. Relevante: `src/preprocess.ts` (formatos de preprocessado), `src/cleanup.ts` (JS para limpiar DOM), `examples/ollama.ts` (ejemplo con Ollama).
- **llm-scraper-py (Python)**: Port a Python. Relevante: `llm_scraper_py/preprocess.py` (preprocessado sync/async), `llm_scraper_py/playwright_js.py` (JS de cleanup/markdown/readability), `llm_scraper_py/models.py` (protocol de LanguageModel, helpers de schema).

Estos repos extraen datos estructurados con schemas. Docrawl es diferente: convierte documentación completa a Markdown. Pero el código de preprocessado y cleanup del DOM es reutilizable.

## Cloudflare Tunnel + Workers VPC

### Arquitectura de exposición a internet
```
[Internet] → [Worker] → (VPC binding) → [Tunnel] → [cloudflared] → [docrawl:8002]
```

- **cloudflared** corre como sidecar en docker-compose, crea conexión saliente al tunnel
- **NO hay Public Hostname** — la app es completamente privada
- Un **VPC Service** vincula el tunnel con el Worker
- El **Worker** usa un VPC Service binding (`env.VPC_SERVICE.fetch(...)`) para acceder al servicio privado
- El Worker es el único punto de entrada público

### Variables de entorno
- `CLOUDFLARE_TUNNEL_TOKEN` — en `.env`, token del tunnel (se obtiene del dashboard Workers VPC)

### Configuración del Worker
- Directorio `worker/` con Cloudflare Worker
- `wrangler.jsonc` contiene el `vpc_services` binding con el Service ID
- Deploy: `cd worker && npx wrangler deploy`

## Convenciones de código

- Python 3.12, type hints en todo
- async/await para I/O (Playwright, HTTP a Ollama, FastAPI)
- Pydantic para validación de datos
- Logging con `logging` estándar, no print()
- Docstrings breves, código autoexplicativo
- Sin abstracciones innecesarias: si algo se usa en un solo lugar, no crear una clase/interface para ello
