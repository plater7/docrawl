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

3. Accede a la UI en http://localhost:8080

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
