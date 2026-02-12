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

## Exponer a internet (Cloudflare Tunnel + Worker)

### Prerequisitos
- Cuenta de Cloudflare con un dominio configurado
- [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) (plan gratuito funciona)
- Node.js (para el Worker, opcional)

### 1. Crear el Tunnel

1. Ir a [Zero Trust Dashboard](https://one.dash.cloudflare.com/) → Networks → Tunnels
2. Crear tunnel → tipo "Cloudflared"
3. Copiar el token generado
4. Configurar Public Hostname:
   - Subdomain: `docrawl` (o el que prefieras)
   - Domain: tu dominio en Cloudflare
   - Service: `http://docrawl:8002`

### 2. Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```
CLOUDFLARE_TUNNEL_TOKEN=eyJ...tu-token
```

### 3. Levantar con tunnel

```bash
docker compose up -d
```

La aplicación estará disponible en `https://docrawl.tudominio.com`

### 4. Worker de edge (opcional)

Para agregar un proxy en el edge de Cloudflare con lógica adicional:

```bash
cd worker
npm install
# Editar wrangler.toml con tu TUNNEL_HOSTNAME
npx wrangler deploy
```
