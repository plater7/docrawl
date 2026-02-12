# Docrawl

Aplicacion web dockerizada que crawlea sitios de documentacion y los convierte a archivos Markdown organizados.

## Stack

- **Python 3.12**
- **FastAPI** - API + servir UI estatica
- **Playwright** - renderizado de paginas (headless Chromium)
- **markdownify** - conversion HTML a Markdown
- **Ollama** - LLM local via API REST (corre en el host)
- **SSE** - progreso en tiempo real a la UI
- **Docker** - container unico con docker-compose

## Requisitos

- Docker y Docker Compose
- Ollama corriendo en el host (puerto 11434)

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
│   │   ├── page.py          # Playwright
│   │   └── markdown.py      # HTML a MD
│   ├── llm/
│   │   ├── client.py        # Cliente Ollama
│   │   ├── filter.py        # Filtrado LLM
│   │   └── cleanup.py       # Cleanup MD
│   ├── jobs/
│   │   ├── manager.py       # Gestion de jobs
│   │   └── runner.py        # Orquestacion
│   └── ui/
│       └── index.html       # UI estatica
├── requirements.txt
└── CLAUDE.md
```

## Output

Los archivos Markdown se guardan en `./data/` respetando la estructura de URLs del sitio crawleado.

## Exponer a internet (Cloudflare Tunnel + Workers VPC)

### Arquitectura

```
[Internet] → [Cloudflare Worker] → (VPC Service binding) → [Cloudflare Tunnel] → [cloudflared container] → [docrawl:8002]
```

La app queda completamente privada (sin hostname público). El Worker es el único punto de entrada y se conecta al servicio a través de un VPC Service binding que rutea internamente por la red de Cloudflare.

### Prerequisitos
- Cuenta de Cloudflare con un dominio configurado
- [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) (plan gratuito funciona)
- Node.js 18+ (para deployar el Worker)
- Workers VPC (beta, disponible gratis en todos los planes Workers)

### 1. Crear el Tunnel

1. Ir al [Workers VPC dashboard](https://dash.cloudflare.com/) → Tunnels
2. Create Tunnel → nombrar (ej: `docrawl-tunnel`)
3. Copiar el token de instalación
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

Crear archivo `.env` en la raíz del proyecto:

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

La aplicación estará disponible en la URL del Worker o en tu custom domain.
