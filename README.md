# Docrawl

Aplicacion web dockerizada que crawlea sitios de documentacion y los convierte a archivos Markdown organizados. Usa Playwright para renderizar paginas, markdownify para conversion HTML->MD, y Ollama (modelos locales) para filtrado inteligente de URLs y limpieza de contenido.

## Stack

- **Python 3.12**
- **FastAPI** — API + servir UI estatica
- **Playwright** — renderizado de paginas (headless Chromium)
- **markdownify** — conversion HTML a Markdown
- **Ollama** — LLM local via API REST (corre en el host)
- **SSE (Server-Sent Events)** — progreso en tiempo real a la UI
- **Docker** — container unico con docker-compose

## Requisitos

- Docker y Docker Compose
- Ollama corriendo en el host (puerto 11434)
- Al menos un modelo descargado (ej: `ollama pull mistral`)

## Uso

1. Asegurate de tener Ollama corriendo:
   ```bash
   ollama serve
   ```

2. Levanta el container:
   ```bash
   docker-compose up --build
   ```

3. Accede a la UI en http://localhost:8002

## UI

Interfaz web minimalista (HTML + CSS + JS vanilla, sin frameworks). Permite configurar y lanzar jobs de crawl con feedback en tiempo real.

- **URL raiz** — sitio de documentacion a crawlear
- **3 selectores de modelo Ollama** — uno por rol:
  - **Crawl Model** — discovery y filtrado de URLs (priorizar velocidad)
  - **Pipeline Model** — cleanup de markdown por chunks (balance velocidad/calidad)
  - **Reasoning Model** — analisis de estructura y decisiones complejas (reservado para uso futuro)
- **Output path** — auto-generado desde la URL (dominio + seccion), editable
- **Configuracion avanzada** — delay entre requests, concurrencia maxima, max depth, respetar robots.txt
- **Log de progreso** — consola en tiempo real con indicador de fase activa (discovery, filtering, scraping, cleanup, save), modelo en uso, y badges de color por fase
- **Cancelacion** — boton para detener el job en cualquier momento, conservando lo ya procesado

## Flujo de un job

1. **Discovery** — descubre URLs via sitemap.xml, navegacion del sitio, o crawl recursivo (cascada)
2. **Filtrado deterministico** — mismo dominio, excluir extensiones no-doc, deduplicar
3. **Filtrado LLM** — el modelo crawl filtra URLs irrelevantes y propone orden
4. **Scraping** — Playwright navega cada pagina, extrae HTML con pre-limpieza de DOM (remueve nav, footer, sidebar, etc.)
5. **Cleanup LLM** — cada chunk de markdown pasa por el modelo pipeline para limpieza (chunks limpios se saltan automaticamente)
6. **Output** — archivos .md respetando estructura de URLs + indice `_index.md`

## API

```
GET  /                          UI estatica
GET  /api/models                Lista modelos Ollama disponibles
POST /api/jobs                  Crear y lanzar job de crawl
GET  /api/jobs/{id}/events      SSE stream de progreso
POST /api/jobs/{id}/cancel      Cancelar job
GET  /api/jobs/{id}/status      Estado actual del job
```

## Estructura del proyecto

```
docrawl/
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── src/
│   ├── main.py              # FastAPI app
│   ├── api/
│   │   ├── routes.py        # Endpoints REST + SSE
│   │   └── models.py        # Pydantic models
│   ├── crawler/
│   │   ├── discovery.py     # sitemap, nav, crawl recursivo
│   │   ├── filter.py        # Filtrado de URLs
│   │   └── robots.py        # Parser robots.txt
│   ├── scraper/
│   │   ├── page.py          # Playwright + DOM pre-cleaning
│   │   └── markdown.py      # HTML a MD + chunking
│   ├── llm/
│   │   ├── client.py        # Cliente Ollama con inference params
│   │   ├── filter.py        # Filtrado LLM de URLs
│   │   └── cleanup.py       # Cleanup MD + smart skip
│   ├── jobs/
│   │   ├── manager.py       # Gestion de jobs + SSE stream
│   │   └── runner.py        # Orquestacion del pipeline
│   └── ui/
│       └── index.html       # UI estatica
├── worker/
│   ├── wrangler.jsonc       # Config Cloudflare Worker
│   └── src/
│       └── index.js         # Worker proxy via VPC binding
├── tests/
│   ├── conftest.py
│   └── crawler/
│       └── test_discovery.py
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## Output

Los archivos Markdown se guardan en `./data/` respetando la estructura de URLs del sitio crawleado. Se genera un `_index.md` con tabla de contenidos y links relativos.

## Exponer a internet (Cloudflare Tunnel + Workers VPC)

### Arquitectura

```
[Internet] → [Cloudflare Worker] → (VPC Service binding) → [Cloudflare Tunnel] → [cloudflared container] → [docrawl:8002]
```

La app queda completamente privada (sin hostname publico). El Worker es el unico punto de entrada y se conecta al servicio a traves de un VPC Service binding que rutea internamente por la red de Cloudflare.

### Prerequisitos
- Cuenta de Cloudflare con un dominio configurado
- [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) (plan gratuito funciona)
- Node.js 18+ (para deployar el Worker)
- Workers VPC (beta, disponible gratis en todos los planes Workers)

### 1. Crear el Tunnel

1. Ir al [Workers VPC dashboard](https://dash.cloudflare.com/) → Tunnels
2. Create Tunnel → nombrar (ej: `docrawl-tunnel`)
3. Copiar el token de instalacion
4. **No configurar Public Hostname**

### 2. Crear VPC Service

1. Workers VPC dashboard → VPC Services
2. Create VPC Service:
   - Name: `docrawl-service`
   - Tunnel: el creado en paso 1
   - Host: `docrawl`
   - HTTP Port: `8002`
3. Copiar el **Service ID**

### 3. Configurar variables de entorno

Crear archivo `.env` en la raiz del proyecto:

```
CLOUDFLARE_TUNNEL_TOKEN=eyJ...tu-token
```

Editar `worker/wrangler.jsonc` y reemplazar `<TU_VPC_SERVICE_ID>` con el Service ID del paso 2.

### 4. Levantar con tunnel

```bash
docker compose up -d
```

### 5. Deployar el Worker

```bash
cd worker
npm install
npx wrangler deploy
```

La aplicacion estara disponible en la URL del Worker o en tu custom domain.

## Changelog

### v0.5.0 — Ollama inference parameters
- `generate()` acepta `options` dict para Ollama API (`num_ctx`, `num_predict`, `temperature`, `num_batch`)
- Cleanup: `num_ctx: 8192`, `num_predict` dinamico capped a 4096, `temperature: 0.1`
- Filtering: `num_ctx: 4096`, `num_predict: 2048`, `temperature: 0.0`
- Previene truncado silencioso de contexto y generacion infinita de tokens

### v0.4.0 — Cleanup pipeline performance
- Pre-limpieza de DOM: remueve nav, footer, sidebar, cookie banners antes de extraer HTML
- Extraccion enfocada en contenido (`main`, `article`, `[role='main']`) con fallback a body
- Pre-limpieza de markdown con regex (hydration Next.js, atributos de framework, lineas de ruido)
- Chunks de 16K (antes 8K), split por heading boundaries
- Timeouts dinamicos: 45s base + 10s/KB, max 90s (antes fijo 120s)
- Smart skip: chunks >60% code blocks o <2000 chars sin ruido se saltan el LLM

### v0.3.0 — Job log con fase activa y modelo
- Indicador de fase con dot pulsante y colores por fase (init, discovery, filtering, scraping, cleanup, save, done, failed, cancelled)
- Eventos SSE enriquecidos: `phase_change` y `log` con `active_model`, `progress`, `url`
- Badges de color en cada entrada de log
- Timing por operacion

### v0.2.0 — Multi-model selectors + smart output path
- 3 selectores de modelo Ollama por rol (crawl, pipeline, reasoning)
- Auto-generacion de output path desde URL (extrae dominio sin subdominios comunes, ignora prefijos de version)
- UI responsive con hints por selector

### v0.1.0 — Release inicial
- Discovery en cascada: sitemap.xml → nav/sidebar → crawl recursivo BFS
- Filtrado deterministico + LLM de URLs
- Scraping con Playwright + conversion markdownify
- Cleanup LLM por chunks con retry y backoff
- SSE para progreso en tiempo real
- Cancelacion de jobs
- Soporte robots.txt
- Exposicion via Cloudflare Tunnel + Workers VPC
