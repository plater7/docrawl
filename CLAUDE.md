# CLAUDE.md — Docrawl



## Que es Docrawl

Una aplicacion web dockerizada que crawlea sitios de documentacion y los convierte a archivos Markdown organizados. Usa Playwright para renderizar paginas, markdownify para conversion HTML->MD, y Ollama (modelos locales) para filtrado inteligente de URLs y limpieza de contenido.

## Stack

- **Python 3.12**
- **FastAPI** — API + servir UI estatica
- **Playwright** — renderizado de paginas (headless Chromium)
- **markdownify** — conversion HTML->Markdown (sin LLM)
- **Ollama** — LLM local via API REST (corre en el host, expuesto en `host.docker.internal:11434`)
- **SSE (Server-Sent Events)** — progreso en tiempo real a la UI
- **Docker** — container unico con docker-compose

## Principio rector

**Simplicidad le gana a todo.** Preferir soluciones directas sobre abstracciones elegantes. Codigo legible sobre codigo clever. Menos dependencias, mejor.

## Arquitectura

```
[Browser/UI :8002] -> [FastAPI container] -> [Ollama en host :11434]
                          |
                          |-- Discovery (cascada)
                          |-- Filtrado (deterministico + LLM)
                          |-- Scraping (Playwright + markdownify)
                          |-- LLM cleanup por chunks
                          +-- Output -> /data/{path_estructura}/*.md
```

### Flujo completo de un job

1. Usuario ingresa: URL raiz, 3 modelos Ollama (crawl, pipeline, reasoning), path output, configuracion de rate limiting
2. **Discovery** (cascada, se detiene en el primer metodo exitoso):
   - Intenta parsear `sitemap.xml`
   - Si no hay, parsea el nav/sidebar de la pagina con Playwright
   - Fallback: crawl recursivo por links internos con depth limit
3. **Filtrado deterministico**:
   - Solo URLs del mismo dominio/subpath que la URL raiz
   - Excluir extensiones no-doc: `.pdf`, `.zip`, `.png`, `.jpg`, `.mp4`, etc.
   - Deduplicar (normalizar trailing slashes, fragments, query params)
   - Excluir patrones comunes no-doc: `/blog/`, `/changelog/`, `/api-reference/` (configurable)
4. **Filtrado LLM** (usa `crawl_model`):
   - Se le pasa la lista prefiltrada de URLs al modelo Ollama
   - El LLM filtra URLs irrelevantes y propone orden de procesamiento
   - Si el LLM falla, se usa la lista prefiltrada tal cual
5. **Scraping pagina por pagina**:
   - Playwright navega a cada URL
   - Se extrae el HTML del body
   - markdownify convierte a Markdown (sin LLM)
   - Respetando delay entre requests y concurrencia maxima configurada
6. **LLM cleanup por chunks** (usa `pipeline_model`):
   - Si el MD de una pagina excede el context window del modelo, se divide en chunks
   - Cada chunk se envia al LLM para limpieza (quitar residuos de nav, footers, ads, formateo)
   - Si un chunk falla (timeout, context overflow): retry con backoff exponencial (max 3 intentos)
   - Si sigue fallando: se guarda el markdown crudo sin cleanup y se loguea el error
   - **El job nunca se aborta por un chunk o pagina fallida**
7. **reasoning_model** (futuro):
   - Analisis de estructura del sitio antes del crawl
   - Filtrado complejo de contenido (seleccion de idioma, dedup cross-page)
   - Evaluacion de calidad de documentacion
   - Actualmente no usado, se pasa en el payload para fases futuras
8. **Output**:
   - Output path auto-generado: `/data/output/<dominio>/<seccion>`
   - El dominio se extrae de la URL sin subdominios comunes (www, docs, doc, wiki)
   - La seccion se deriva del path, ignorando prefijos de version (/latest, /stable, /v2/)
   - El usuario puede editar el path generado antes de iniciar
   - Se respeta la estructura de URLs: `docs.example.com/guide/install` -> `{output_path}/guide/install.md`
   - Se genera un `_index.md` en la raiz con tabla de contenidos y links relativos
   - Se reportan paginas/chunks que fallaron

### Cancelacion de jobs

- El usuario puede cancelar un job desde la UI en cualquier momento
- Al cancelar, se conserva todo lo ya procesado en disco
- El job reporta estado final: completado parcialmente, que se proceso y que no

## API endpoints

```
GET  /                          -> UI estatica
GET  /api/models                -> Lista modelos Ollama disponibles (proxy a GET host:11434/api/tags)
POST /api/jobs                  -> Crear y lanzar un job de crawl
GET  /api/jobs/{id}/events      -> SSE stream de progreso del job
POST /api/jobs/{id}/cancel      -> Cancelar job
GET  /api/jobs/{id}/status      -> Estado actual del job
```

### Payload de POST /api/jobs

```json
{
  "url": "https://docs.example.com",
  "crawl_model": "mistral:7b",
  "pipeline_model": "qwen3:14b",
  "reasoning_model": "deepseek-r1:32b",
  "output_path": "/data/output/example.com",
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
- **URL raiz** — input text
- **Crawl Model** — modelo para discovery y filtrado de URLs (priorizar velocidad/throughput)
- **Pipeline Model** — modelo para cleanup de markdown chunks (balance velocidad/calidad)
- **Reasoning Model** — modelo para analisis de estructura y decisiones complejas (maxima calidad)
- Los 3 selectores se pueblan con GET /api/models. Cada uno tiene una nota con ejemplos recomendados.
- **Path de output** — input text, auto-generado desde URL, editable
- **Delay entre requests** — input number (ms), default 500
- **Max concurrent pages** — input number, default 3
- **Max depth** (crawl recursivo) — input number, default 5
- **Respetar robots.txt** — checkbox, default on
- **Boton Start** — lanza el job
- **Boton Cancel** — aparece cuando hay job en curso
- **Log de progreso** — area de texto/consola que muestra eventos SSE en tiempo real
- **Resumen final** — estadisticas al terminar

## Docker

### Dockerfile
- Base: `python:3.12-slim`
- Instalar Playwright + Chromium
- Copiar codigo
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
|-- docker/
|   +-- Dockerfile
|-- docker-compose.yml
|-- src/
|   |-- main.py              # FastAPI app, monta rutas y sirve UI
|   |-- api/
|   |   |-- routes.py         # Endpoints REST + SSE
|   |   +-- models.py         # Pydantic models para request/response
|   |-- crawler/
|   |   |-- discovery.py      # Cascada: sitemap -> nav -> crawl recursivo
|   |   |-- filter.py         # Filtrado deterministico de URLs
|   |   +-- robots.py         # Parser de robots.txt
|   |-- scraper/
|   |   |-- page.py           # Playwright: navegar + extraer HTML
|   |   +-- markdown.py       # markdownify: HTML -> MD + chunking
|   |-- llm/
|   |   |-- client.py         # Cliente HTTP para Ollama API
|   |   |-- filter.py         # Prompt de filtrado de URLs
|   |   +-- cleanup.py        # Prompt de cleanup de MD por chunks
|   |-- jobs/
|   |   |-- manager.py        # Crear, cancelar, trackear jobs
|   |   +-- runner.py         # Orquestacion del flujo completo
|   +-- ui/
|       +-- index.html        # UI estatica
|-- worker/
|   |-- wrangler.jsonc        # Config Cloudflare Worker
|   |-- package.json
|   +-- src/
|       +-- index.js          # Worker proxy via VPC Service binding
|-- tests/
|   |-- conftest.py           # Fixtures compartidos
|   +-- crawler/
|       +-- test_discovery.py # Tests unitarios de discovery
|-- pytest.ini
|-- requirements.txt
|-- .gitignore
|-- .env.example
|-- README.md
+-- CLAUDE.md
```

## Referencia: repos originales

Este proyecto se inspira en dos repos de scraping con LLM. El codigo de preprocessado (cleanup JS, conversion HTML) y la estructura de prompts son utiles como referencia:

- **llm-scraper (TS)**: Usa Playwright + AI SDK de Vercel. Relevante: `src/preprocess.ts` (formatos de preprocessado), `src/cleanup.ts` (JS para limpiar DOM), `examples/ollama.ts` (ejemplo con Ollama).
- **llm-scraper-py (Python)**: Port a Python. Relevante: `llm_scraper_py/preprocess.py` (preprocessado sync/async), `llm_scraper_py/playwright_js.py` (JS de cleanup/markdown/readability), `llm_scraper_py/models.py` (protocol de LanguageModel, helpers de schema).

Estos repos extraen datos estructurados con schemas. Docrawl es diferente: convierte documentacion completa a Markdown. Pero el codigo de preprocessado y cleanup del DOM es reutilizable.

## Cloudflare Tunnel + Workers VPC

### Arquitectura de exposicion a internet
```
[Internet] -> [Worker] -> (VPC binding) -> [Tunnel] -> [cloudflared] -> [docrawl:8002]
```

- **cloudflared** corre como sidecar en docker-compose, crea conexion saliente al tunnel
- **NO hay Public Hostname** — la app es completamente privada
- Un **VPC Service** vincula el tunnel con el Worker
- El **Worker** usa un VPC Service binding (`env.VPC_SERVICE.fetch(...)`) para acceder al servicio privado
- El Worker es el unico punto de entrada publico

### Variables de entorno
- `CLOUDFLARE_TUNNEL_TOKEN` — en `.env`, token del tunnel (se obtiene del dashboard Workers VPC)

### Configuracion del Worker
- Directorio `worker/` con Cloudflare Worker
- `wrangler.jsonc` contiene el `vpc_services` binding con el Service ID
- Deploy: `cd worker && npx wrangler deploy`

## Convenciones de codigo

- Python 3.12, type hints en todo
- async/await para I/O (Playwright, HTTP a Ollama, FastAPI)
- Pydantic para validacion de datos
- Logging con `logging` estandar, no print()
- Docstrings breves, codigo autoexplicativo
- Sin abstracciones innecesarias: si algo se usa en un solo lugar, no crear una clase/interface para ello
