# Wave 4 — Agente 15: Performance Engineer

## Resumen ejecutivo

Docrawl tiene un throughput real que es entre **3x y 6x peor** que lo que el usuario espera al configurar `max_concurrent=3`. El parámetro de concurrencia es completamente ignorado: el procesamiento es estrictamente secuencial página por página. Para un job típico de 50 páginas con `delay_ms=500` y un modelo LLM de velocidad moderada, el tiempo real oscila entre **35 y 90 minutos**, mientras que el tiempo esperado por el usuario (asumiendo 3 páginas paralelas) sería de **12 a 30 minutos**.

Los tres cuellos de botella más críticos son, en orden de impacto:

1. **Concurrencia falsa**: `max_concurrent` es un parámetro UI que no tiene ninguna implementación en el runner. El bucle de páginas es secuencial sin excepción.
2. **Bloqueo síncrono del event loop**: `_get_openrouter_models()` usa `httpx.get()` síncrono, y `write_text()` más `stat()` se ejecutan en el hilo async principal bloqueando el event loop durante cada guardado de página.
3. **Nueva conexión HTTP por llamada LLM**: Cada `generate()` crea y destruye un `httpx.AsyncClient()`, incurriendo en overhead de TCP handshake y TLS negotiation para cada chunk de cada página.

El cuarto hallazgo en magnitud de impacto es la espera de `networkidle` de Playwright para cada página, que puede añadir 3-10 segundos adicionales por página en sitios con polling o websockets activos.

---

## Perfil de performance (job típico 50 páginas)

Supuestos: `delay_ms=500`, Playwright como método principal de scraping, modelo LLM local Ollama con velocidad media (qwen3:14b en GPU), páginas de documentación de tamaño medio (~30KB HTML, ~2 chunks markdown).

| Fase | Tiempo estimado | Notas |
|------|----------------|-------|
| Init + validación de modelos | 5-15s | 3 llamadas HTTP a Ollama `/api/tags` |
| Arranque de browser (Playwright) | 2-4s | Una sola vez, browser reutilizado |
| Discovery (sitemap) | 2-10s | Si sitemap disponible; httpx async |
| Discovery (nav parse o recursive) | 10-120s | Playwright cold-start adicional en nav; recursive hasta 500s en sitios grandes |
| LLM filtering (50 URLs) | 30-90s | Una sola llamada LLM; num_ctx=4096 |
| Scraping + cleanup x50 páginas (secuencial) | 30-80 min | Ver desglose abajo |
| Generación de índice | <1s | Síncrono, bloqueante |
| **Total estimado** | **35-90 min** | Con max_concurrent=3 implementado: ~12-30 min |

### Desglose por página (modo secuencial actual)

| Sub-fase | Tiempo/página |
|----------|--------------|
| `page.goto()` con `wait_until="networkidle"` | 3-12s |
| `_remove_noise()` (JS evaluate) | 0.1-0.3s |
| `_extract_content()` (hasta 9 selectores) | 0.1-0.5s |
| `html_to_markdown()` (markdownify, Python puro) | 0.05-2s (proporcional a tamaño) |
| `chunk_markdown()` + `_pre_clean_markdown()` | 0.01-0.1s |
| `cleanup_markdown()` LLM × 2 chunks | 20-60s (dominante) |
| `write_text()` + `stat()` síncronos | 0.001-0.05s |
| `asyncio.sleep(delay_s)` | 0.5s |
| **Total/página** | **24-73s** |

### Tiempo teórico con concurrencia real (max_concurrent=3)

Con semáforo de 3 trabajadores paralelos, el tiempo de scraping+cleanup se dividiría aproximadamente en 3 (limitado por el cuello de botella del LLM en el host), llevando el total a **12-30 minutos** en lugar de 35-90 minutos.

---

## Hallazgos

### FINDING-15-001: max_concurrent nunca implementado — procesamiento estrictamente secuencial

- **Severidad**: Critical
- **Archivo**: `src/jobs/runner.py:295`
- **Descripción**: El parámetro `request.max_concurrent` se recibe en el payload, se muestra en la UI, pero nunca se usa. El bucle `for i, url in enumerate(urls):` procesa cada página de forma completamente secuencial. No hay `asyncio.Semaphore`, no hay `asyncio.gather`, no hay pool de workers.

```python
# runner.py:295 — bucle secuencial sin concurrencia
for i, url in enumerate(urls):
    if job.is_cancelled:
        break
    # ... procesa una página completa antes de pasar a la siguiente
    await asyncio.sleep(delay_s)
```

- **Impacto en performance**: Para 50 páginas con `max_concurrent=3`, el throughput es 1/3 del esperado. Tiempo real: 35-90 min vs tiempo esperado: 12-30 min. El impacto escala linealmente con el número de páginas. Esta es la mayor oportunidad de mejora de performance del sistema.
- **Fix**: Implementar `asyncio.Semaphore(request.max_concurrent)` y procesar URLs con `asyncio.gather` o una cola de trabajo. El delay entre requests debe aplicarse por worker, no globalmente, para respetar el rate limiting por origen sin serializar la concurrencia.

---

### FINDING-15-002: httpx.get() síncrono bloquea el event loop en _get_openrouter_models()

- **Severidad**: Critical
- **Archivo**: `src/llm/client.py:102`
- **Descripción**: `_get_openrouter_models()` es una función síncrona (`def`, no `async def`) que llama a `httpx.get()` — el cliente HTTP síncrono de httpx. Esta función es llamada desde `get_available_models()` que es async, pero la llama sin `await` ni `asyncio.to_thread`. Cuando se invoca (desde `list_models()` en routes.py o `validate_models()` en runner.py), bloquea completamente el event loop de asyncio durante hasta 10 segundos.

```python
# client.py:97-105 — función síncrona con httpx.get() bloqueante
def _get_openrouter_models() -> list[dict[str, Any]]:
    """Get list of OpenRouter models from API."""
    import httpx

    try:
        response = httpx.get(          # BLOQUEANTE: congela el event loop
            "https://openrouter.ai/api/v1/models",
            timeout=10,
        )
```

- **Impacto en performance**: Bloquea el event loop hasta 10 segundos. Durante ese tiempo, ningún otro coroutine puede ejecutarse: SSE streams se congelan, cancelaciones de jobs no se procesan, heartbeats no se envían. Si múltiples usuarios usan OpenRouter simultáneamente, la degradación es acumulativa.
- **Fix**: Convertir `_get_openrouter_models()` a `async def` y usar `httpx.AsyncClient`, o envolver la llamada síncrona en `await asyncio.to_thread(_get_openrouter_models)`.

---

### FINDING-15-003: Nueva conexión HTTP por cada llamada LLM — sin connection pooling

- **Severidad**: Major
- **Archivo**: `src/llm/client.py:201`, `src/llm/client.py:243`, `src/llm/client.py:283`
- **Descripción**: Cada función `_generate_ollama()`, `_generate_openrouter()` y `_generate_opencode()` crea un nuevo `httpx.AsyncClient()` con `async with`, lo usa para una sola request, y lo destruye. En el flujo de scraping, esto ocurre para cada chunk de cada página. Para 50 páginas con 2 chunks promedio: 100 ciclos de creación/destrucción de cliente HTTP, cada uno con TCP handshake y TLS negotiation.

```python
# client.py:201 — nuevo cliente por cada generate()
async def _generate_ollama(...) -> str:
    ...
    async with httpx.AsyncClient() as client:   # Crear, conectar, cerrar
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            ...
        )
```

- **Impacto en performance**: Overhead de TCP handshake a Ollama (~1-5ms en loopback, pero acumulado en 100 llamadas = 0.1-0.5s). Para proveedores externos (OpenRouter, OpenCode) con TLS, el overhead por conexión es 50-200ms, resultando en 5-20 segundos de overhead puro en un job de 50 páginas. Además, sin keep-alive, el servidor Ollama no puede reutilizar conexiones.
- **Fix**: Crear un `httpx.AsyncClient` compartido a nivel de módulo o en una clase `LLMClient`, con connection pooling configurado (`limits=httpx.Limits(max_keepalive_connections=5)`). El cliente debe inicializarse una vez al inicio de la aplicación.

---

### FINDING-15-004: write_text() y stat() síncronos en contexto async bloquean el event loop

- **Severidad**: Major
- **Archivo**: `src/jobs/runner.py:446-447`, `src/jobs/runner.py:591`
- **Descripción**: El guardado de cada página usa `file_path.write_text()` y `file_path.stat()` — ambas operaciones de I/O síncrona ejecutadas directamente en el event loop async. Adicionalmente, `_generate_index()` en la línea 493 es una función síncrona que hace `write_text()` y se llama directamente sin `asyncio.to_thread`. En situaciones de disco lento (Docker volumes en Windows/Mac con VirtioFS, NFS, o discos llenos) esto puede bloquear el event loop durante 10-500ms por operación.

```python
# runner.py:446-447 — I/O síncrono en async context
file_path.write_text(final_md, encoding="utf-8")   # Bloqueante
file_size = file_path.stat().st_size               # Bloqueante

# runner.py:591 — función sync llamada sin to_thread
index_path.write_text("\n".join(lines), encoding="utf-8")  # Bloqueante
```

- **Impacto en performance**: En condiciones normales (SSD local), el impacto es de 1-10ms por página (50-500ms total para 50 páginas). En Docker con volúmenes montados (el caso de uso documentado en `docker-compose.yml`), el overhead de VirtioFS puede ser 10-100x mayor: 10-1000ms por página, totalizando 0.5-50 segundos de bloqueo puro del event loop.
- **Fix**: Usar `await asyncio.to_thread(file_path.write_text, final_md, encoding="utf-8")` para delegar a un thread pool. Para `_generate_index()`, convertirla a async o envolverla en `asyncio.to_thread`.

---

### FINDING-15-005: wait_until="networkidle" en Playwright añade latencia innecesaria

- **Severidad**: Major
- **Archivo**: `src/scraper/page.py:161`
- **Descripción**: `page.goto()` usa `wait_until="networkidle"`, que espera hasta que no haya requests de red activos por 500ms. Para sitios de documentación modernos con analytics, polling de telemetría, websockets de hot-reload, o CDNs con lazy-loading, esto puede tardar significativamente más que `"domcontentloaded"` o `"load"`. Playwright espera hasta el timeout de 30s si la red nunca se "calma".

```python
# page.py:161 — networkidle puede añadir 3-10s por página
await page.goto(url, timeout=timeout, wait_until="networkidle")
```

- **Impacto en performance**: En sitios con analytics activos (Google Analytics, Segment, Intercom, etc.) el tiempo de navegación por página aumenta de ~1-2s (domcontentloaded) a 3-10s (networkidle). Para 50 páginas: 100-400 segundos de overhead adicional solo en espera de red. En el peor caso (sitios con polling continuo), networkidle nunca se alcanza y cada página espera el timeout completo de 30s.
- **Fix**: Cambiar a `wait_until="domcontentloaded"` como default. Si se necesita contenido JS-renderizado, usar `wait_until="load"` o una espera explícita por el selector de contenido principal (`page.wait_for_selector("main", timeout=5000)`).

---

### FINDING-15-006: Nueva instancia de Playwright por llamada en try_nav_parse() durante Discovery

- **Severidad**: Major
- **Archivo**: `src/crawler/discovery.py:237-238`
- **Descripción**: `try_nav_parse()` crea un Playwright completo (`async_playwright()`), lanza un nuevo browser Chromium, carga la página y cierra todo al terminar. Esto ocurre durante la fase de discovery, después de que `run_job()` ya inició otro Playwright en `scraper.start()`. El costo de arranque de Chromium headless es de 1-3 segundos. Más crítico: esta instancia es completamente independiente del `PageScraper` que se reutiliza durante el scraping.

```python
# discovery.py:237-238 — segunda instancia Playwright, browser nuevo
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)   # 1-3s startup
    page = await browser.new_page()
```

- **Impacto en performance**: Overhead de 1-3s por invocación de `try_nav_parse()`. Más importante, consume recursos adicionales de memoria (~100-150MB por instancia de Chromium) durante la fase de discovery, superponiéndose con el browser principal que ya está inicializado. En sistemas con memoria limitada, puede causar presión de memoria que degrada el performance general.
- **Fix**: Pasar el `PageScraper` existente (o su browser) a `discover_urls()` para reutilizar la instancia de Playwright ya iniciada. Alternativamente, inicializar `PageScraper` antes de `discover_urls()` y reutilizarlo en ambas fases.

---

### FINDING-15-007: LLM filtering serializado — todos los URLs en un solo prompt sin límite de tamaño

- **Severidad**: Major
- **Archivo**: `src/llm/filter.py:43`, `src/llm/filter.py:27`
- **Descripción**: `filter_urls_with_llm()` concatena todos los URLs descubiertos en un solo string y los envía en un único prompt LLM. El `num_ctx` está fijo en 4096 tokens. Para un sitemap grande con 500+ URLs (cada URL ~60 caracteres = ~15 tokens), el prompt puede superar los 4096 tokens, causando truncamiento silencioso. El LLM entonces filtra URLs parciales y el resultado es impredecible.

```python
# filter.py:43 — todos los URLs en un prompt, sin verificar longitud
prompt = FILTER_PROMPT_TEMPLATE.format(urls="\n".join(urls))

# filter.py:27 — num_ctx fijo, no proporcional al número de URLs
FILTER_OPTIONS: dict[str, Any] = {
    "num_ctx": 4096,   # Insuficiente para >200 URLs
    ...
}
```

- **Impacto en performance**: Para sitios con sitemaps grandes (100-10,000 URLs es común), el LLM procesa un prompt truncado y devuelve resultados incorrectos. El fallback al `except` retorna la lista original sin filtrar, desperdiciando el tiempo de llamada LLM (30-90s) y procesando páginas irrelevantes en las fases siguientes. Para 500 URLs sin filtrar, el tiempo adicional de scraping puede ser de horas.
- **Fix**: Calcular la longitud estimada del prompt antes de enviarlo. Si supera `num_ctx * 3` (margen conservador), dividir en batches o escalar `num_ctx` dinámicamente. Como mínimo, limitar el número de URLs enviadas al LLM (ej. máx. 200) y documentar el límite.

---

### FINDING-15-008: Sitemap completo cargado en memoria — sin límite de URLs

- **Severidad**: Major
- **Archivo**: `src/crawler/discovery.py:338-413`
- **Descripción**: `parse_sitemap_xml()` descarga el sitemap completo en `response.content` y lo parsea con `ET.fromstring(content)` — ambos en memoria. Para sitemaps de 10,000+ URLs (caso real: sitios como Kubernetes, AWS, Microsoft Docs tienen sitemaps de 50,000+ URLs), el XML puede pesar 5-50MB y el `set` de URLs resultante puede ocupar 10-100MB de RAM. El parser `xml.etree.ElementTree` crea un árbol DOM completo en memoria, sin streaming.

```python
# discovery.py:355-369 — contenido completo en memoria
content = response.content          # Bytes completos en RAM
root = ET.fromstring(content)       # DOM completo en RAM
```

- **Impacto en performance**: Consumo de memoria de 10-100MB por sitemap grande. Para sitemaps anidados (sitemap index), la función es recursiva y puede acumular múltiples árboles DOM simultáneamente. En un container Docker con límite de memoria, esto puede causar OOM killer. El tiempo de parseo de un sitemap de 50,000 URLs puede ser de 2-10 segundos.
- **Fix**: Usar `xml.etree.ElementTree.iterparse()` para streaming parsing. Añadir un límite máximo de URLs extraídas del sitemap (ej. 5,000) con warning al usuario. Añadir validación de tamaño de respuesta antes de parsear (`if len(response.content) > 10_000_000: warn`).

---

### FINDING-15-009: BeautifulSoup con html.parser (Python puro) en recursive_crawl — lento en páginas grandes

- **Severidad**: Minor
- **Archivo**: `src/crawler/discovery.py:154`
- **Descripción**: En el fallback de crawl recursivo, `BeautifulSoup(response.text, "html.parser")` usa el parser HTML puro de Python. Para páginas HTML grandes (>500KB, frecuente en docs con mucho JavaScript inline), `html.parser` es 3-10x más lento que `lxml` o `html5lib`. Esto aplica solo al crawl recursivo (fallback), no al scraping principal.

```python
# discovery.py:154 — html.parser Python puro, lento para páginas grandes
soup = BeautifulSoup(response.text, "html.parser")
```

- **Impacto en performance**: Para páginas de 200KB con `html.parser`: ~50-200ms de parse. Con `lxml`: ~10-30ms. En un crawl recursivo de 100 URLs: diferencia de 4-17 segundos. El impacto es significativo solo en el caso de fallback (sitemap y nav parse fallaron), pero en ese caso la velocidad de discovery importa.
- **Fix**: Usar `"lxml"` si está disponible: `BeautifulSoup(response.text, "lxml")`. Añadir `lxml` a `requirements.txt`. El fallback a `"html.parser"` ocurrirá automáticamente si lxml no está instalado.

---

### FINDING-15-010: Sin pipelining entre scraping y LLM cleanup — CPU y GPU ociosos alternadamente

- **Severidad**: Minor
- **Archivo**: `src/jobs/runner.py:359-440`
- **Descripción**: El flujo actual para cada página es estrictamente secuencial: scraping completo → cleanup LLM completo → siguiente página. Mientras el LLM procesa el markdown de la página N (fase CPU/GPU intensiva), Playwright está ocioso. Mientras Playwright carga la página N+1 (fase I/O), el LLM está ocioso. No hay solapamiento entre las dos operaciones.

```python
# runner.py:359-446 — secuencial: scraping bloqueante, luego LLM bloqueante
html = await scraper.get_html(url)          # Playwright (3-12s)
markdown = html_to_markdown(html)           # CPU (0.1-2s)
chunks = chunk_markdown(markdown, ...)      # CPU (0.01s)
for ci, chunk in enumerate(chunks):
    cleaned = await cleanup_markdown(...)   # LLM (10-30s/chunk)
file_path.write_text(final_md, ...)        # I/O
```

- **Impacto en performance**: Sin pipelining, el tiempo total es `sum(scraping_time + cleanup_time)` por página. Con pipelining, podría ser aproximadamente `max(scraping_time, cleanup_time) + min(...)` para páginas solapadas. Para 50 páginas donde cleanup domina (20-60s/página), el gain potencial es de 10-30% en tiempo de wall-clock, sin añadir concurrencia real.
- **Fix**: Separar el job en dos etapas: una cola de scraping y una cola de cleanup. Usar `asyncio.Queue` para pasar markdown de una etapa a la otra, permitiendo que el browser scrape la página N+1 mientras el LLM limpia la página N. Este patrón es especialmente efectivo con `max_concurrent=3`: 3 scrapers en paralelo alimentando 3 LLM cleaners en paralelo.

---

### FINDING-15-011: Acumulación de HTML/MD en memoria — sin streaming ni liberación explícita

- **Severidad**: Minor
- **Archivo**: `src/jobs/runner.py:315-443`
- **Descripción**: Aunque el diseño procesa páginas de forma secuencial, para cada página se mantienen en memoria simultáneamente: el HTML raw (puede ser 500KB-5MB por página), el markdown convertido (100KB-2MB), los chunks individuales, y los chunks limpios. Dado que Python no libera memoria inmediatamente (GC no determinístico), el RSS del proceso puede crecer durante el job. En Docker con límite de memoria, esto puede causar problemas en jobs largos.

```python
# runner.py — múltiples copias del contenido en memoria simultáneamente
html = await scraper.get_html(url)          # Copia 1: HTML raw
markdown = html_to_markdown(html)           # Copia 2: MD completo
chunks = chunk_markdown(markdown, ...)      # Copia 3: lista de chunks
cleaned_chunks: list[str] = []             # Copia 4: chunks limpios
final_md = "\n\n".join(cleaned_chunks)     # Copia 5: MD final
```

- **Impacto en performance**: Para páginas grandes (1MB HTML), se mantienen hasta 3-5MB en memoria simultáneamente por "página activa". Con el diseño secuencial actual, el peak de memoria es bajo (~50MB). Si se implementa concurrencia (fix de FINDING-15-001), el peak se multiplica por `max_concurrent`: con `max_concurrent=3` y páginas de 1MB, el overhead de datos en vuelo sería ~15MB (aceptable). La presión real viene de la falta de liberación explícita: `del html` después de `html_to_markdown()` ayudaría a reducir el peak.
- **Fix**: Añadir `del html` después de la conversión a markdown, y `del markdown, chunks` después de limpiar. Esto no cambia la lógica pero señaliza al GC que puede liberar la memoria más pronto.

---

### FINDING-15-012: fetch_markdown_native() crea httpx.AsyncClient sin timeout global por conexión

- **Severidad**: Minor
- **Archivo**: `src/scraper/page.py:20-21`
- **Descripción**: `fetch_markdown_native()` crea `httpx.AsyncClient()` sin pool de conexiones ni headers de keepalive. Además, `fetch_markdown_proxy()` usa un timeout de 30 segundos para el proxy, que es demasiado alto para un fallback opcional. Ambas funciones crean y destruyen un cliente por URL, al igual que el cliente LLM.

```python
# page.py:20-21 — nuevo cliente HTTP por URL, sin pool
async with httpx.AsyncClient() as client:
    resp = await client.get(url, headers=headers, timeout=15.0, ...)
```

- **Impacto en performance**: Overhead de TCP handshake por cada URL donde se intenta native markdown. En un job de 50 páginas donde ninguna sirve markdown nativo, esto añade 50 ciclos de conexión/desconexión innecesarios (cada uno con overhead de 1-10ms en red local, 20-100ms en red externa).
- **Fix**: Compartir un cliente httpx a nivel de módulo o pasarlo como parámetro. Si se implementa un `httpx.AsyncClient` compartido para el LLM (fix de FINDING-15-003), el mismo cliente puede reutilizarse para fetch_markdown_native.

---

### FINDING-15-013: _generate_index() síncrona con write_text() llamada en contexto async

- **Severidad**: Minor
- **Archivo**: `src/jobs/runner.py:493`, `src/jobs/runner.py:579-591`
- **Descripción**: `_generate_index()` es una función síncrona (`def`, no `async def`) que construye el índice en memoria como una lista de strings y escribe el archivo con `write_text()`. Se llama directamente en el contexto async de `run_job()` sin `asyncio.to_thread`. Para jobs con 1000+ URLs (caso del crawl recursivo con cap de 1000), construir la lista de líneas y escribir el archivo puede bloquear durante 10-50ms.

```python
# runner.py:493 — función síncrona llamada sin to_thread
if not job.is_cancelled:
    _generate_index(urls, output_path)   # Síncrono, bloqueante

# runner.py:591 — write_text síncrono dentro de la función
index_path.write_text("\n".join(lines), encoding="utf-8")
```

- **Impacto en performance**: Bloqueo de 10-50ms del event loop al final del job. Impacto menor en términos absolutos, pero incorrecto arquitectónicamente ya que los SSE events finales se envían después de esta llamada.
- **Fix**: Convertir `_generate_index()` a `async def` y usar `await asyncio.to_thread(index_path.write_text, content, encoding="utf-8")`.

---

### FINDING-15-014: recursive_crawl tiene rate limiting propio de 0.5s que se suma al delay del job

- **Severidad**: Minor
- **Archivo**: `src/crawler/discovery.py:103`, `src/crawler/discovery.py:136`
- **Descripción**: `recursive_crawl()` tiene un `RATE_LIMIT_DELAY = 0.5` hardcodeado que se aplica antes de cada request. Este valor no es configurable y no respeta el `delay_ms` configurado por el usuario. Si el usuario configura `delay_ms=100` para un sitio que lo permite, el crawl recursivo seguirá usando 0.5s por URL. Para 100 URLs descubiertas: 50 segundos de delays obligatorios solo en discovery.

```python
# discovery.py:103, 136 — rate limit hardcodeado, no configurable
RATE_LIMIT_DELAY = 0.5  # seconds between requests

await asyncio.sleep(RATE_LIMIT_DELAY)  # Siempre 0.5s, ignora user config
response = await client.get(current_url)
```

- **Impacto en performance**: Discovery con recursive_crawl (fallback) para 100 URLs: mínimo 50 segundos en sleeps. No respeta la preferencia del usuario. Si el sitio tiene `Crawl-delay: 1` en robots.txt, el sistema usa 0.5s durante discovery pero 1s durante scraping — inconsistencia.
- **Fix**: Pasar `delay_ms` como parámetro a `recursive_crawl()` y usar `max(delay_ms / 1000, robots_crawl_delay)` como rate limit en lugar del hardcoded 0.5s.

---

### FINDING-15-015: SSE keepalive cada 20s con timeout — no tiene impacto de performance pero sí de UX

- **Severidad**: Suggestion
- **Archivo**: `src/jobs/manager.py:47-51`
- **Descripción**: El `event_stream` usa `asyncio.wait_for(..., timeout=20)` como mecanismo de keepalive, emitiendo un evento "keepalive" cada 20 segundos si no hay actividad. Esto es correcto para mantener conexiones SSE abiertas a través de proxies y balanceadores de carga. Sin embargo, la configuración `ping=15` en `EventSourceResponse` (routes.py:96) significa que hay dos mecanismos de keepalive solapados: el ping de sse_starlette cada 15s y el de la Queue cada 20s.

```python
# manager.py:47 — timeout de 20s para keepalive
event = await asyncio.wait_for(self._events.get(), timeout=20)

# routes.py:96 — ping adicional de sse_starlette cada 15s
return EventSourceResponse(job.event_stream(), ping=15)
```

- **Impacto en performance**: El overhead de SSE en sí es mínimo: cada evento es un string JSON pequeño sobre una conexión persistente. El impacto real es el uso de una coroutine adicional por cada cliente SSE conectado, y la contención de la `asyncio.Queue` entre el writer (runner) y el reader (event_stream). Para un solo job con un cliente, el overhead es <1ms. Para múltiples jobs simultáneos (sin límite de concurrencia de jobs), el overhead escala linealmente.
- **Fix**: Eliminar el `ping=15` de `EventSourceResponse` y confiar en el mecanismo de keepalive de la Queue (20s), o viceversa. No es necesario tener ambos. La deduplicación reduciría el tráfico de red de keepalive a la mitad.

---

## Estadísticas

- **Total**: 15
- **Critical**: 2 (FINDING-15-001, FINDING-15-002)
- **Major**: 6 (FINDING-15-003, FINDING-15-004, FINDING-15-005, FINDING-15-006, FINDING-15-007, FINDING-15-008)
- **Minor**: 6 (FINDING-15-009, FINDING-15-010, FINDING-15-011, FINDING-15-012, FINDING-15-013, FINDING-15-014)
- **Suggestion**: 1 (FINDING-15-015)

## Priorización de fixes por ROI

| Prioridad | Finding | Impacto estimado |
|-----------|---------|-----------------|
| 1 | FINDING-15-001 (max_concurrent) | 3x mejora de throughput en jobs multi-página |
| 2 | FINDING-15-002 (httpx síncrono) | Elimina bloqueo de hasta 10s del event loop |
| 3 | FINDING-15-005 (networkidle) | 100-400s menos por job de 50 páginas |
| 4 | FINDING-15-003 (sin connection pooling) | 5-20s menos overhead de red por job |
| 5 | FINDING-15-007 (LLM filter sin límite) | Previene horas de trabajo desperdiciado en sitios grandes |
| 6 | FINDING-15-004 (write_text síncrono) | Crítico en Docker volumes; 0.5-50s mejora |
| 7 | FINDING-15-006 (Playwright doble instancia) | 1-3s menos + 100-150MB menos RAM |
| 8 | FINDING-15-008 (sitemap en memoria) | Previene OOM en sitemaps grandes |
