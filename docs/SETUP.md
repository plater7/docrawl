# Cloudflare Tunnel + Workers VPC Setup

Exposer Docrawl a internet de forma segura sin IP publica, usando Cloudflare Tunnel + Workers VPC.

## Arquitectura

```
[Internet] -> [Worker] -> (VPC binding) -> [Tunnel] -> [cloudflared] -> [docrawl:8002]
```

- **cloudflared** corre como sidecar en docker-compose y crea una conexion saliente al tunnel
- **No hay Public Hostname** -- la app es completamente privada
- Un **VPC Service** vincula el tunnel con el Worker
- El **Worker** es el unico punto de entrada publico

## Prerequisitos

- Cuenta Cloudflare con Zero Trust habilitado
- `npx wrangler` disponible (`npm install -g wrangler` o usar npx)
- Docker Compose corriendo con Docrawl

---

## Paso 1 -- Crear el Tunnel

1. Ve al dashboard de Cloudflare -> **Zero Trust** -> **Networks** -> **Tunnels**
2. Click **Create a tunnel** -> selecciona **Cloudflared**
3. Nombre el tunnel: `docrawl` (o el que prefieras)
4. Copia el token que aparece -- lo necesitaras en el siguiente paso
5. **No configures un Public Hostname** -- el tunnel sera privado (acceso solo via Worker)

## Paso 2 -- Configurar el token del tunnel

Copia `.env.example` a `.env` (si no lo hiciste ya) y agrega el token:

```bash
cp .env.example .env
```

Edita `.env`:

```env
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiMC4uLiAgIyB0b2tlbiBkZWwgZGFzaGJvYXJk
```

## Paso 3 -- Crear el VPC Service

1. En el dashboard de Cloudflare -> **Zero Trust** -> **Networks** -> **VPC Services**
2. Click **Create VPC Service**
3. Selecciona el tunnel `docrawl` que creaste
4. Copia el **Service ID** (formato UUID: `019c53c3-e7ab-7ca1-b454-93cdb207dbd4`)

## Paso 4 -- Configurar el Worker

Edita `worker/wrangler.jsonc` con el Service ID copiado:

```jsonc
{
  "name": "docrawl-worker",
  "main": "src/index.js",
  "compatibility_date": "2025-01-28",
  "vpc_services": [
    {
      "binding": "VPC_SERVICE",
      "service_id": "TU-SERVICE-ID-AQUI",
      "remote": true
    }
  ]
}
```

## Paso 5 -- Deployar el Worker

```bash
cd worker
npm install
npx wrangler deploy
```

El Worker quedara disponible en `https://docrawl-worker.<tu-subdominio>.workers.dev`

## Paso 6 -- Levantar Docrawl con cloudflared

```bash
docker compose up --build
```

El sidecar `cloudflared` se conecta automaticamente usando el `CLOUDFLARE_TUNNEL_TOKEN` del `.env`.

---

## Verificacion

1. Abre la URL del Worker en el browser
2. Deberias ver la UI de Docrawl
3. Comprueba los logs de cloudflared: `docker compose logs cloudflared`

## Seguridad

Por defecto el Worker **no tiene autenticacion**. Para restringir acceso:

- Agrega Cloudflare Access en el Worker (requiere Zero Trust)
- O agrega un header secreto en el Worker y validalo en FastAPI

---

## LM Studio Setup

> Added in v0.9.10 (PR #154)

[LM Studio](https://lmstudio.ai/) is supported as a 4th LLM provider alongside Ollama, OpenRouter, and OpenCode. It exposes an OpenAI-compatible API on a local port.

### 1. Install & Start LM Studio

1. Download LM Studio from [lmstudio.ai](https://lmstudio.ai/)
2. Load a model (e.g., `mistral-7b`, `llama-3.1-8b`)
3. Start the local server (default: `http://localhost:1234/v1`)

### 2. Configure Environment Variables

Add to your `.env`:

```env
LMSTUDIO_URL=http://host.docker.internal:1234/v1
LMSTUDIO_API_KEY=lm-studio                         # optional, default works
```

> **Note**: Use `host.docker.internal` when running Docrawl in Docker so the container can reach LM Studio on your host machine.

### 3. Select LM Studio in the UI

In the web UI, select **LM Studio** from the provider dropdown. Models loaded in LM Studio will appear automatically in the model list.

Alternatively, prefix model names with `lmstudio/` in API calls:

```json
{
  "url": "https://docs.example.com",
  "crawl_model": "lmstudio/mistral-7b"
}
```

---

## Environment Variables Reference

> New variables added in v0.9.8--v0.9.10

### LLM Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Ollama API endpoint |
| `LMSTUDIO_URL` | `http://host.docker.internal:1234/v1` | LM Studio API endpoint |
| `LMSTUDIO_API_KEY` | `lm-studio` | LM Studio API key (optional) |
| `OPENROUTER_API_KEY` | -- | OpenRouter API key |
| `OPENCODE_API_KEY` | -- | OpenCode API key |

### Performance Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPE_MAX_RETRIES` | `3` | Max retry attempts per page before marking as failed |
| `JOB_TTL_SECONDS` | `3600` | Time-to-live for completed jobs before cleanup (seconds) |
| `DISCOVERY_CONCURRENCY` | `5` | Max concurrent URL discovery requests |
| `PAGE_POOL_SIZE` | `3` | Number of reusable Playwright browser pages in the pool |

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `use_pipeline_mode` | `false` | Enable producer/consumer pipeline mode (async queue between discovery and scraping) |
| `use_cache` | `false` | Enable page cache (24h TTL, skips re-scraping unchanged pages) |
| `output_format` | `markdown` | Output format: `markdown` or `json` (structured 7-block JSON output) |

---

## Pause / Resume Endpoints

> Added in v0.9.6 (PR #132)

Jobs can be paused and resumed via the REST API. State is checkpointed to `.job_state.json`.

### Pause a Running Job

```bash
POST /api/jobs/{job_id}/pause
```

Response:
```json
{
  "status": "paused",
  "checkpoint": ".job_state.json",
  "pages_completed": 42,
  "pages_total": 120
}
```

### Resume a Paused Job

```bash
POST /api/jobs/{job_id}/resume
```

The job continues from the last checkpoint, skipping already-scraped pages.

### Get Job State

```bash
GET /api/jobs/{job_id}/status
```

Returns current phase, progress, and whether the job is pausable.

---

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| `cloudflared` no conecta | Verifica que `CLOUDFLARE_TUNNEL_TOKEN` sea correcto en `.env` |
| Worker responde 502 | El tunnel no esta conectado. Revisa `docker compose logs cloudflared` |
| Worker responde 403 | Verifica el VPC Service ID en `wrangler.jsonc` |
| No se ve la UI | Docrawl debe estar corriendo en el puerto 8002. Verifica con `docker compose ps` |
| LM Studio models not showing | Check `LMSTUDIO_URL` points to correct port. Verify LM Studio server is running with `curl http://localhost:1234/v1/models` |
| Pause endpoint returns 409 | Job is not in a pausable state (already paused, completed, or failed) |
