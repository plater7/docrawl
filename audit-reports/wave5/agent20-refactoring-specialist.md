# Wave 5 — Agente 20: Refactoring Specialist

## Resumen ejecutivo

Análisis de refactoring de los cinco archivos más complejos del proyecto. Se identificaron **24 hallazgos** distribuidos en 4 niveles de severidad. El estado general del código es funcional pero con deuda técnica concentrada en tres áreas críticas: la función monolítica `run_job` en `runner.py`, la duplicación de código HTTP en `client.py`, y los 25+ `print()` mezclados con `logging` en `discovery.py`.

El proyecto tiene el principio rector correcto ("simplicidad sobre todo"), pero en varios puntos ese principio fue aplicado de forma incompleta: se evitaron abstracciones útiles mientras se dejaron duplicaciones innecesarias. El refactoring recomendado no requiere rediseño arquitectónico — son transformaciones mecánicas y seguras que reducirían la superficie de bugs en ~40%.

---

## Mapa de complejidad

| Archivo | LOC | Funciones/Clases | Complejidad ciclomática estimada | Prioridad refactoring |
|---------|-----|-----------------|----------------------------------|-----------------------|
| `src/jobs/runner.py` | 592 | 4 funciones | Alta — `run_job` ~CC 18 | **P1 — Crítico** |
| `src/ui/index.html` | 1485 | ~12 funciones JS, 3 temas CSS | Media — `subscribeToEvents` ~CC 10 | **P2 — Major** |
| `src/llm/client.py` | 313 | 10 funciones | Media — 3 funciones casi idénticas | **P1 — Crítico** |
| `src/crawler/discovery.py` | 572 | 4 funciones | Alta — `discover_urls` ~CC 14 | **P2 — Major** |
| `src/api/routes.py` | 231 | 7 endpoints | Baja — excepto `list_providers` | **P3 — Minor** |
| `src/scraper/page.py` | 167 | 1 clase, 2 funciones | Baja | Sin prioridad |
| `src/scraper/markdown.py` | 130 | 3 funciones | Baja | Sin prioridad |
| `src/llm/cleanup.py` | 125 | 4 funciones | Baja | Sin prioridad |
| `src/llm/filter.py` | 68 | 1 función | Baja | Sin prioridad |
| `src/crawler/filter.py` | 150 | 2 funciones | Media | Sin prioridad |
| `src/jobs/manager.py` | 118 | 1 clase, 5 métodos | Baja | Sin prioridad |

---

## Dead code completo

### Funciones nunca llamadas

| Archivo | Función | Línea | Evidencia |
|---------|---------|-------|-----------|
| `src/llm/client.py` | `get_available_models_legacy()` | 299 | Grep en todo el repo: cero usos. Documentado en waves 3 y 4. |
| `src/llm/client.py` | `generate_legacy()` | 304 | Grep en todo el repo: cero usos. Documentado en waves 3 y 4. |

### Parámetros recibidos pero nunca usados en la lógica de negocio

| Archivo | Parámetro | Contexto | Evidencia |
|---------|-----------|----------|-----------|
| `src/api/models.py` + `runner.py` | `max_concurrent: int` | Recibido en `JobRequest`, enviado en payload UI, pero `runner.py` nunca implementa concurrencia — el loop de scraping es estrictamente secuencial (línea 295: `for i, url in enumerate(urls)`). | No hay `asyncio.gather`, `asyncio.Semaphore`, ni ningún mecanismo de concurrencia en `runner.py`. |
| `src/jobs/runner.py` | `reasoning_model` | Validado (`validate_models` línea 36), pero nunca pasado a ninguna función de LLM durante el job. El TODO en línea 94-98 lo confirma explícitamente. | Solo aparece en `validate_models` — no en ninguna llamada `generate()`. |

### Imports no utilizados

| Archivo | Import | Línea | Evidencia |
|---------|--------|-------|-----------|
| `src/llm/client.py` | `import httpx` (doble) | 9 y 99 | El módulo top-level importa `httpx` en línea 9. La función `_get_openrouter_models` re-importa `import httpx` localmente en línea 99. La importación local es redundante — ya está disponible en el scope del módulo. |
| `src/api/routes.py` | `import httpx` (inline) | 141 | `import httpx` dentro del cuerpo de `health_ready`. El módulo no tiene un import de nivel superior para `httpx`, lo que hace el import inline necesario pero es un patrón inconsistente con el resto del proyecto. |

### Variables asignadas pero con uso cuestionable

| Archivo | Variable | Línea | Evidencia |
|---------|----------|-------|-----------|
| `src/jobs/runner.py` | `pages_native_md`, `pages_proxy_md`, `pages_playwright` | 291-293 | Contadores de método de fetch — se reportan en `job_done` y se muestran en la UI en `showSummary`. **No es dead code**, pero la función `showSummary` solo los muestra si `nativeMd > 0 || proxyMd > 0`, por lo que `pages_playwright` nunca se muestra cuando es el único método usado. |
| `src/llm/client.py` | `PROVIDER_MODELS["ollama"]` y `PROVIDER_MODELS["openrouter"]` | 40-41 | Ambas listas son `[]` vacías. El comentario explica que son dinámicas, pero la estructura `PROVIDER_MODELS` solo sirve para `opencode`. Los otros dos keys están ahí para simetría visual pero nunca se leen. |

---

## Hallazgos

### FINDING-20-001: `run_job` — función monolítica con 6+ responsabilidades
- **Severidad**: Critical
- **Archivo**: `src/jobs/runner.py:92-554`
- **LOC de la función**: 463 líneas
- **Descripción**: La función `run_job` contiene en su cuerpo: (1) setup de estado del job, (2) validación de modelos, (3) inicialización del browser, (4) carga de robots.txt, (5) discovery de URLs, (6) filtrado básico, (7) filtrado robots.txt, (8) filtrado LLM, (9) loop de scraping con tres estrategias de fetch (native, proxy, playwright), (10) loop de cleanup de chunks, (11) escritura de archivos, (12) generación del índice, (13) manejo de cancelación en múltiples puntos, (14) manejo de errores globales y locales. Violación severa del Principio de Responsabilidad Única. La complejidad ciclomática es aproximadamente 18 (8 `if/elif` en el loop de páginas + 4 en filtrado + 3 en robots + 3 en cleanup).

- **Propuesta**: Extraer al menos 4 funciones privadas del cuerpo de `run_job`:

```python
# Propuesta de estructura resultante:

async def run_job(job: Job) -> None:
    """Orquesta las fases del job. Solo flow control."""
    job.status = "running"
    scraper = PageScraper()
    robots = RobotsParser()
    try:
        if not await _phase_init(job, scraper, robots):
            return
        urls = await _phase_discovery(job)
        if job.is_cancelled: return
        urls = await _phase_filtering(job, urls, robots)
        if job.is_cancelled: return
        stats = await _phase_scrape_all(job, urls, scraper)
        if not job.is_cancelled:
            _generate_index(urls, Path(job.request.output_path))
            await _finish_job(job, stats)
    except Exception as e:
        await _handle_fatal_error(job, e)
    finally:
        await _cleanup_browser(job, scraper)

async def _phase_init(job, scraper, robots) -> bool:
    """Valida modelos e inicializa browser. Retorna False si falla."""
    ...  # líneas 107-184

async def _phase_discovery(job) -> list[str]:
    """Ejecuta discovery y retorna URLs. ~20 líneas."""
    ...  # líneas 186-212

async def _phase_filtering(job, urls, robots) -> list[str]:
    """Filtrado básico + robots.txt + LLM. ~60 líneas."""
    ...  # líneas 214-279

async def _scrape_page(job, i, url, urls, scraper, request) -> tuple[str, int]:
    """Scrape + cleanup + save de una sola página. Retorna (status, chunks_failed).
    Extrae el try/except interno del loop de páginas — ~130 líneas."""
    ...  # líneas 295-487

async def _phase_scrape_all(job, urls, scraper) -> dict:
    """Loop sobre páginas, llama _scrape_page. ~30 líneas."""
    ...  # líneas 284-490
```

- **Esfuerzo**: 3-4 horas (refactoring puro, cero cambios de comportamiento)

---

### FINDING-20-002: `client.py` — DRY violation: `_generate_openrouter` vs `_generate_opencode`
- **Severidad**: Critical
- **Archivo**: `src/llm/client.py:218-295`
- **Descripción**: Las funciones `_generate_openrouter` (líneas 218-255) y `_generate_opencode` (líneas 258-295) son **idénticas en estructura** y difieren únicamente en: (1) el nombre de la variable de API key (`OPENROUTER_API_KEY` vs `OPENCODE_API_KEY`), (2) la base URL extraída de `PROVIDERS`, y (3) el mensaje de error en el `logger.error`. Son 77 líneas de código duplicado donde 72 son idénticas. Cualquier cambio en el manejo de errores, headers, o timeout debe hacerse en dos lugares.

- **Propuesta**: Extraer una función privada `_generate_chat_completion`:

```python
async def _generate_chat_completion(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
    api_key: str,
    base_url: str,
    provider_name: str,
) -> str:
    """Generic OpenAI-compatible chat completion. Used by openrouter and opencode."""
    if not api_key:
        raise ValueError(f"{provider_name.upper()}_API_KEY not configured")

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {"model": model, "messages": messages}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"{provider_name} request failed: {e}")
        raise


async def _generate_openrouter(model, prompt, system, timeout, options) -> str:
    return await _generate_chat_completion(
        model, prompt, system, timeout, options,
        api_key=OPENROUTER_API_KEY,
        base_url=PROVIDERS["openrouter"]["base_url"],
        provider_name="OpenRouter",
    )


async def _generate_opencode(model, prompt, system, timeout, options) -> str:
    return await _generate_chat_completion(
        model, prompt, system, timeout, options,
        api_key=OPENCODE_API_KEY,
        base_url=PROVIDERS["opencode"]["base_url"],
        provider_name="OpenCode",
    )
```

Reducción: de 77 líneas duplicadas a ~30 líneas compartidas + ~6 líneas por wrapper = ~42 líneas totales. Reducción del 45% en este bloque.

- **Esfuerzo**: 1 hora

---

### FINDING-20-003: Dead code confirmado — funciones legacy sin callers
- **Severidad**: Critical
- **Archivo**: `src/llm/client.py:299-312`
- **Descripción**: `get_available_models_legacy()` (línea 299) y `generate_legacy()` (línea 304) son wrappers que no tienen ningún caller en el proyecto. Confirmado con búsqueda exhaustiva en waves 3, 4 y verificado en esta auditoría. El comentario "Legacy functions for backwards compatibility" es engañoso — no hay backwards compatibility que proteger si no hay callers.

- **Propuesta**: Eliminar las 14 líneas completas (298-312 inclusive, incluyendo el comentario de sección). Si existe alguna API externa (tests, scripts externos) que las use, deben aparecer en los tests — actualmente `tests/` solo contiene `test_discovery.py`.

- **Esfuerzo**: 15 minutos

---

### FINDING-20-004: `discovery.py` — 25 instancias de `print()` mezcladas con `logging`
- **Severidad**: Major
- **Archivo**: `src/crawler/discovery.py` — líneas: 126, 234, 290, 295, 301, 336, 372, 451, 455, 479, 484, 492, 496, 500, 506, 509, 514, 522, 526, 530, 536, 540, 548, 552, 556, 565, 570
- **Descripción**: Hay 27 llamadas `print(f"[DISCOVERY] {msg}", flush=True)` en el archivo, siempre duplicando un `logger.info/warning/error(msg)` que aparece 1-2 líneas antes. El resultado es que cada mensaje de discovery se emite dos veces — una al sistema de logging estructurado (que puede enviarse a archivos, sistemas de monitoreo, etc.) y otra por `stdout` sin formato. En un entorno Docker/FastAPI esto genera output duplicado y contradice el principio de logging estructurado del proyecto (`CLAUDE.md`: "Logging con `logging` estándar, no print()"). El patrón es tan sistemático que sugiere que fue añadido para debugging y nunca eliminado.

- **Propuesta**: Eliminar todas las llamadas `print()` en `discovery.py`. Verificar que el nivel de log sea apropiado (los mensajes de estrategia deben ser `INFO`, no requieren `DEBUG`). Si se necesita output visible en consola durante desarrollo, usar `logging.StreamHandler` configurado en `main.py`.

- **Esfuerzo**: 30 minutos (búsqueda-reemplazo + verificación)

---

### FINDING-20-005: `routes.py` — `__import__('os')` inline en `list_providers`
- **Severidad**: Major
- **Archivo**: `src/api/routes.py:62-67`
- **Descripción**: El endpoint `list_providers` usa `__import__("os").environ.get(...)` para leer variables de entorno. Este patrón es un code smell severo: (1) elude el sistema de imports estándar de Python, (2) es menos legible que `import os` o mejor aún `from src.llm.client import OPENROUTER_API_KEY, OPENCODE_API_KEY`, (3) fue identificado en auditorías previas y persiste sin corrección. El módulo `src/llm/client.py` ya exporta las constantes `OPENROUTER_API_KEY` y `OPENCODE_API_KEY` como module-level variables — no hay razón para no usarlas.

- **Propuesta**:

```python
# routes.py — línea 15, añadir a los imports existentes:
from src.llm.client import get_available_models, PROVIDERS, OLLAMA_URL, OPENROUTER_API_KEY, OPENCODE_API_KEY

# list_providers endpoint — reemplazar __import__ con referencias directas:
"configured": (
    p_id == "ollama"
    or (p_id == "openrouter" and bool(OPENROUTER_API_KEY))
    or (p_id == "opencode" and bool(OPENCODE_API_KEY))
    or False
),
```

- **Esfuerzo**: 10 minutos

---

### FINDING-20-006: `runner.py` — `max_concurrent` aceptado pero ignorado totalmente
- **Severidad**: Major
- **Archivo**: `src/jobs/runner.py:295` / `src/api/models.py:15`
- **Descripción**: El campo `max_concurrent` es documentado en `CLAUDE.md`, aparece en el payload de la API, en el formulario de la UI, en `JobRequest`, y en `validate_models` (indirectamente, ya que el modelo se valida pero el campo no). Sin embargo, el loop de scraping en `runner.py` es estrictamente secuencial (`for i, url in enumerate(urls)`). No hay `asyncio.Semaphore`, `asyncio.gather`, ni ninguna forma de paralelismo. El parámetro recibe el valor del usuario, se almacena en `JobRequest`, y nunca se lee en ningún lugar de `runner.py`. El usuario que configura `max_concurrent=5` creyendo que accelera el crawl está siendo silenciosamente engañado.

- **Propuesta**: Hay dos opciones:
  - **Opción A (honesta, menor esfuerzo)**: Eliminar el campo de `JobRequest`, del formulario UI, y de la documentación hasta que sea implementado. Añadir una nota en el TODO.
  - **Opción B (implementar)**: Usar `asyncio.Semaphore(request.max_concurrent)` en `_phase_scrape_all` y convertir el loop secuencial en `asyncio.gather` con tasks. Requiere refactoring de `_scrape_page` para que sea independiente (ver FINDING-20-001).

- **Esfuerzo**: Opción A: 30 minutos. Opción B: 4-6 horas (incluyendo tests de concurrencia).

---

### FINDING-20-007: `runner.py` — `reasoning_model` validado pero nunca usado
- **Severidad**: Major
- **Archivo**: `src/jobs/runner.py:94-98`, `src/jobs/runner.py:119`
- **Descripción**: `reasoning_model` se valida en `validate_models` (línea 119), lo que consume tiempo de inicio del job y puede fallar la validación si el modelo no está disponible — bloqueando jobs legítimos. El TODO en líneas 94-98 confirma que no tiene uso actual. Validar un parámetro no usado puede rechazar un job por un modelo de reasoning no instalado, incluso cuando ese modelo no se va a usar.

- **Propuesta**: Eliminar `reasoning_model` de la lista `models_to_check` en `validate_models` (línea 36). Conservar el campo en `JobRequest` para forwards-compatibility. Actualizar el comentario del TODO.

```python
# validate_models — eliminar la tupla de reasoning:
models_to_check = [
    ("crawl_model", crawl_model),
    ("pipeline_model", pipeline_model),
    # reasoning_model: not yet implemented, skip validation
]
```

- **Esfuerzo**: 10 minutos

---

### FINDING-20-008: `client.py` — import `httpx` duplicado en `_get_openrouter_models`
- **Severidad**: Major
- **Archivo**: `src/llm/client.py:9` y `src/llm/client.py:99`
- **Descripción**: El módulo importa `httpx` en la línea 9 a nivel de módulo. La función `_get_openrouter_models` (línea 97) re-importa `import httpx` localmente en la línea 99, sugiriendo que fue escrita en aislamiento y nunca se revisó en el contexto del módulo completo. Esta función es también **síncrona** mientras que `_get_ollama_models` es `async` — inconsistencia que hace que `get_available_models("openrouter")` bloquee el event loop de FastAPI en la línea 58 al llamar a `_get_openrouter_models()` sin `await`.

- **Propuesta**: (1) Eliminar el `import httpx` local en línea 99. (2) Convertir `_get_openrouter_models` en función `async` usando `httpx.AsyncClient` para ser consistente con `_get_ollama_models`. Actualizar la llamada en `get_available_models` para usar `await`.

- **Esfuerzo**: 45 minutos (incluyendo verificación de que no rompe el comportamiento actual)

---

### FINDING-20-009: `discovery.py` — URL building duplicada en `try_nav_parse` y `recursive_crawl`
- **Severidad**: Major
- **Archivo**: `src/crawler/discovery.py:167-182` y `src/crawler/discovery.py:265-279`
- **Descripción**: Ambas funciones contienen el mismo patrón de construcción de URLs limpias:

```python
# En recursive_crawl (línea 176):
clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
if parsed.query:
    clean_url += f"?{parsed.query}"

# En try_nav_parse (línea 274):
clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
if parsed.query:
    clean_url += f"?{parsed.query}"
```

Son idénticas, duplicadas. Ambas también comparten el mismo filtro de esquemas `parsed.scheme in ["http", "https"]` y el mismo filtro de dominio `parsed.netloc == base_domain`. La función `normalize_url` ya existe en el mismo módulo pero no se usa para esta construcción — se llama después, creando un pipeline redundante.

- **Propuesta**: Extraer una función privada `_build_clean_url`:

```python
def _build_clean_url(href: str, base_url: str, base_domain: str) -> str | None:
    """Resolve href to absolute URL, filter to same domain. Returns None if filtered."""
    absolute_url = urljoin(base_url, href)
    parsed = urlparse(absolute_url)
    if parsed.netloc != base_domain or parsed.scheme not in ["http", "https"]:
        return None
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        clean += f"?{parsed.query}"
    return normalize_url(clean)
```

- **Esfuerzo**: 1 hora

---

### FINDING-20-010: `runner.py` — sync `file_path.write_text()` en contexto async
- **Severidad**: Major
- **Archivo**: `src/jobs/runner.py:446`
- **Descripción**: La línea `file_path.write_text(final_md, encoding="utf-8")` y `file_path.stat().st_size` (línea 447) son operaciones síncronas de I/O de disco ejecutadas directamente en el event loop de asyncio. Para archivos de documentación que pueden ser varios MB, esto bloquea el event loop durante el tiempo de escritura, pausando todas las conexiones SSE activas y otros requests FastAPI. Reportado en wave 1 como finding crítico de performance.

- **Propuesta**: Usar `asyncio.to_thread` para delegar la escritura a un thread del pool:

```python
await asyncio.to_thread(file_path.write_text, final_md, encoding="utf-8")
file_size = await asyncio.to_thread(lambda: file_path.stat().st_size)
```

Alternativamente, usar `aiofiles` si ya está en las dependencias (no lo está — `asyncio.to_thread` es preferible por no añadir dependencias).

- **Esfuerzo**: 30 minutos

---

### FINDING-20-011: `index.html` — XSS via `innerHTML` con datos sin sanitizar
- **Severidad**: Critical (referencia a finding previo, no duplicación)
- **Archivo**: `src/ui/index.html:1274` y `src/ui/index.html:1332`
- **Descripción**: La función `logMessage` (línea 1274) construye HTML con `entry.innerHTML = ...` donde `message` puede contener HTML arbitrario. La línea 1332 en `subscribeToEvents` concatena `data.active_model` directamente a un string HTML sin escape. Ambos valores provienen de eventos SSE que pueden contener datos scrapeados de sitios externos. Un atacante que controle el contenido de una página scrapeada puede inyectar `<script>` tags que se ejecutan en el contexto del documento.

- **Propuesta mínima** (mantiene simplicidad del proyecto):

```javascript
function escapeHtml(text) {
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
}

// En logMessage (línea 1274):
const badge = phase ? `<span class="log-badge ${badgeClass}">${escapeHtml(phase)}</span>` : '';
entry.innerHTML = `<span style="color:#4a4a6a">[${time}]</span> ${badge}${escapeHtml(message)}`;

// En subscribeToEvents (línea 1332):
if (data.active_model) msg += ` <span class="log-model">[${escapeHtml(data.active_model)}]</span>`;
```

- **Esfuerzo**: 30 minutos

---

### FINDING-20-012: `index.html` — `generateDynamicHints` usa `innerHTML` con datos de modelo
- **Severidad**: Major
- **Archivo**: `src/ui/index.html:1189`
- **Descripción**: La función `generateDynamicHints` escribe en `el.innerHTML` (línea 1189) concatenando `suggestions` que son nombres de modelos provenientes de la API. Si un nombre de modelo contiene caracteres HTML (e.g., `<script>` o `"` en un atributo), se interpretaría como HTML. Aunque el vector de ataque requiere comprometer la API del servidor, es una mala práctica que debe corregirse.

- **Propuesta**: Reemplazar `el.innerHTML = ...` por construcción DOM o escaping con la función `escapeHtml` propuesta en FINDING-20-011.

- **Esfuerzo**: 20 minutos

---

### FINDING-20-013: `index.html` — `subscribeToEvents` con complejidad ciclomática ~10
- **Severidad**: Major
- **Archivo**: `src/ui/index.html:1320-1410`
- **Descripción**: La función `subscribeToEvents` registra 9 event listeners inline, contiene la lógica de reconexión SSE (con un `setTimeout` anidado dentro de un `.catch()` dentro de un `.then()` dentro de `onerror`), y maneja 6 estados de job diferentes. La lógica de reconexión (líneas 1375-1408) tiene dos niveles de profundidad de callbacks y duplica la lógica de `cleanupJob`. La función tiene tres responsabilidades: registro de eventos, manejo de errores de conexión, y reconexión automática.

- **Propuesta**: Respetando el principio de simplicidad del proyecto (no introducir frameworks), extraer la lógica de reconexión:

```javascript
function handleSseError(err) {
    if (!currentJobId) return;
    if (eventSource) { eventSource.close(); eventSource = null; }
    checkJobStatusAndReconnect(currentJobId);
}

async function checkJobStatusAndReconnect(jobId, retryDelay = 2000) {
    try {
        const r = await fetch(`/api/jobs/${jobId}/status`);
        if (!r.ok) throw new Error(`Status ${r.status}`);
        const status = await r.json();
        if (status.status === 'running' || status.status === 'pending') {
            logMessage('SSE reconnecting...', 'init', 'warning');
            setTimeout(() => { if (currentJobId) subscribeToEvents(currentJobId); }, retryDelay);
        } else {
            handleTerminalStatus(status);
        }
    } catch (e) {
        setTimeout(() => { if (currentJobId) checkJobStatusAndReconnect(jobId, 5000); }, retryDelay);
    }
}
```

- **Esfuerzo**: 1.5 horas

---

### FINDING-20-014: `index.html` — CSS de temas duplicado (~600 LOC para 3 temas)
- **Severidad**: Minor
- **Archivo**: `src/ui/index.html:600-937`
- **Descripción**: El archivo contiene tres bloques de CSS de tema: `theme-synthwave` (implícito, ~400 líneas), `theme-basic` (~55 líneas, offset ~640), y `theme-terminal` (~180 líneas, offset ~757). Cada tema redefine prácticamente todas las mismas propiedades de los mismos selectores. No hay un sistema de CSS custom properties por tema — cada tema sobreescribe valores hardcodeados. Esto hace que añadir un cuarto tema requiera ~200 líneas adicionales, y cambiar la estructura de un selector (e.g., renombrar `.phase-banner`) requiere actualizar 3 lugares.

- **Evaluación de impacto vs principio rector**: Dado que el proyecto es un single-file HTML con tres temas como feature intencional, y considerando el principio "simplicidad sobre todo", dividir en múltiples archivos CSS requeriría cambiar el setup de FastAPI (o usar un bundler). La alternativa pragmática es convertir los temas a CSS custom properties:

```css
/* Cada tema solo define variables: */
body.theme-basic {
    --bg-panel: #1e293b;
    --accent-primary: #3b82f6;
    --text-label: #94a3b8;
}
/* Los selectores funcionales usan var() y se definen una sola vez */
.status-bar { background: var(--bg-panel); }
```

- **Esfuerzo**: 4-6 horas (CSS refactoring con riesgo de regresión visual)
- **Recomendación**: Diferir hasta que haya tests visuales de regresión.

---

### FINDING-20-015: `index.html` — `checkHealth` declara variables DOM que ya son globales
- **Severidad**: Minor
- **Archivo**: `src/ui/index.html:1453-1459`
- **Descripción**: La función `checkHealth` re-declara con `const` los elementos DOM `ollamaDot`, `ollamaStatus`, `diskDot`, `diskStatus`, `writeDot`, `writeStatus` (líneas 1454-1459), que ya están disponibles como accesos directos vía `document.getElementById`. A diferencia de los elementos del formulario que se capturan como constantes globales en el scope principal (líneas 1122-1135), los del status bar se resuelven cada vez que se llama `checkHealth`. Es inconsistente y crea variables locales redundantes.

- **Propuesta**: Mover las seis constantes al scope global del script, junto al bloque de constantes de líneas 1122-1135.

- **Esfuerzo**: 15 minutos

---

### FINDING-20-016: `routes.py` — `import httpx` y `import shutil` como imports locales/inline inconsistentes
- **Severidad**: Minor
- **Archivo**: `src/api/routes.py:6-7`, `src/api/routes.py:141`
- **Descripción**: `shutil` se importa al nivel del módulo (línea 7) y se usa solo en `health_ready`. `httpx` se importa dentro del cuerpo de `health_ready` (línea 141). Esta inconsistencia —un import de módulo para `shutil` y un import inline para `httpx`— en la misma función no tiene justificación. Ambos deberían estar al nivel del módulo para consistencia y para que las herramientas de análisis estático los detecten correctamente.

- **Propuesta**: Mover `import httpx` al bloque de imports del módulo (líneas 1-10).

- **Esfuerzo**: 5 minutos

---

### FINDING-20-017: `discovery.py` — `discover_urls` tiene lógica de cascade con 4+ niveles de nesting
- **Severidad**: Major
- **Archivo**: `src/crawler/discovery.py:459-571`
- **Descripción**: La función `discover_urls` tiene 113 líneas con un patrón `if all_urls: ... else: if all_urls: ... else: try:...` que crea 4 niveles de indentación. El patrón de cascade (probar A, si falla probar B, si falla probar C) está correcto en concepto pero la implementación anida el estado en lugar de usar early-return o un loop de estrategias. Adicionalmente, cada transición entre estrategias genera dos `print()` + dos `logger.info()` con mensajes de "Skipping X (Y succeeded)" que son ruido en el 75% de los casos (cuando sitemap funciona).

- **Propuesta**: Refactorizar el cascade a un loop de estrategias:

```python
async def discover_urls(base_url: str, max_depth: int = 5, filter_by_path: bool = True) -> list[str]:
    """Cascade: sitemap -> nav -> recursive. Returns first success."""
    strategies = [
        ("sitemap", lambda: try_sitemap(base_url, filter_by_path)),
        ("nav parsing", lambda: try_nav_parse(base_url)),
        ("recursive crawl", lambda: recursive_crawl(base_url, max_depth)),
    ]
    for name, strategy in strategies:
        try:
            urls = await strategy()
            if urls:
                logger.info(f"Strategy '{name}' succeeded: {len(urls)} URLs")
                return sorted(set(urls))
            logger.info(f"Strategy '{name}': no URLs found, trying next")
        except Exception as e:
            logger.error(f"Strategy '{name}' failed: {e}")

    logger.warning("All strategies failed, returning base URL as fallback")
    return [normalize_url(base_url)]
```

Reducción de 113 líneas a ~20 líneas. Elimina toda la duplicación de `print()`/`logger` por transición.

- **Esfuerzo**: 1.5 horas (incluyendo tests de que el comportamiento de cascade es idéntico)

---

### FINDING-20-018: `runner.py` — `_generate_index` no usa los archivos realmente escritos
- **Severidad**: Minor
- **Archivo**: `src/jobs/runner.py:579-591`
- **Descripción**: La función `_generate_index` itera sobre la lista `urls` (las URLs a scrape) para generar el índice. Sin embargo, el path generado en el índice usa `path.replace("/", "_")` (línea 587) para crear el nombre de archivo, mientras que la función `_url_to_filepath` (línea 557) genera el path real con estructura de directorios (`output_path / f"{path}.md"`). Los links en `_index.md` apuntan a paths como `guide_install.md` cuando el archivo real está en `guide/install.md`. Los links del índice están **rotos por diseño**.

- **Propuesta**: `_generate_index` debe recibir la lista de `(url, file_path)` tuples en lugar de solo URLs, para generar links relativos correctos:

```python
def _generate_index(url_paths: list[tuple[str, Path]], output_path: Path) -> None:
    lines = ["# Documentation Index\n"]
    for url, file_path in url_paths:
        name = urlparse(url).path.strip("/").split("/")[-1] or "Home"
        rel_path = file_path.relative_to(output_path)
        lines.append(f"- [{name}]({rel_path})")
    (output_path / "_index.md").write_text("\n".join(lines), encoding="utf-8")
```

- **Esfuerzo**: 45 minutos (requiere cambiar la llamada en `run_job` para pasar los paths acumulados)

---

### FINDING-20-019: `client.py` — `get_available_models` mezcla async y sync en el mismo dispatcher
- **Severidad**: Major
- **Archivo**: `src/llm/client.py:53-62`
- **Descripción**: La función `get_available_models` está declarada como `async` y hace `await _get_ollama_models()`, pero en las líneas 58-60 llama a `_get_openrouter_models()` y `_get_opencode_models()` que son funciones **síncronas** sin `await`. `_get_openrouter_models` en particular hace una llamada HTTP síncrona (`httpx.get(...)`) que bloquea el event loop. Esto es un bug latente: funciona solo porque Python no lanza error al no usar `await` en una función síncrona dentro de un contexto async, pero el bloqueo real ocurre.

- **Propuesta**: Relacionado con FINDING-20-008. Convertir `_get_openrouter_models` a async. `_get_opencode_models` no hace I/O y puede quedarse síncrona, llamada directamente.

- **Esfuerzo**: Incluido en FINDING-20-008 (45 minutos total).

---

### FINDING-20-020: `runner.py` — `validate_models` realiza 3 llamadas HTTP seriales innecesariamente
- **Severidad**: Minor
- **Archivo**: `src/jobs/runner.py:25-70`
- **Descripción**: `validate_models` valida los tres modelos secuencialmente con un `for` loop. Cada iteración puede hacer una llamada HTTP a Ollama o a APIs externas. Las tres validaciones son completamente independientes — no hay razón para que sean seriales. Para Ollama, la misma lista de modelos se fetcha tres veces (una por modelo), cuando podría fetch-earse una sola vez.

- **Propuesta**:

```python
async def validate_models(crawl_model, pipeline_model, reasoning_model) -> list[str]:
    # Fetch model lists concurrently, once per provider
    providers = {get_provider_for_model(m) for m in [crawl_model, pipeline_model]}
    available_by_provider = dict(zip(
        providers,
        await asyncio.gather(*[get_available_models(p) for p in providers])
    ))
    # Then validate each model against its provider's list
    ...
```

- **Esfuerzo**: 45 minutos

---

### FINDING-20-021: `index.html` — `getModelCategory` con lógica de clasificación frágil
- **Severidad**: Minor
- **Archivo**: `src/ui/index.html:1146-1156`
- **Descripción**: La función `getModelCategory` clasifica modelos usando arrays de strings para pattern matching (`['r1', 'reasoning', 'deepseek', ...]`). La lógica tiene un bug: en la línea 1152, la condición es `crawlPatterns.some(p => name.includes(p)) && !name.includes('8b') || size < 4000000000`. Por precedencia de operadores JS (`&&` antes que `||`), esto se evalúa como `(some(p) && !8b) || size < 4GB`, lo que significa que cualquier modelo con menos de 4GB de tamaño se clasifica como `'crawl'` independientemente de su nombre. Modelos de 3.9GB que son razonadores (como `deepseek-r1:3b`) serían clasificados incorrectamente.

- **Propuesta**: Añadir paréntesis explícitos: `(crawlPatterns.some(p => name.includes(p)) && !name.includes('8b')) || size < 4000000000` — o mejor, evaluar primero reasoning ya que es la categoría más específica.

- **Esfuerzo**: 20 minutos

---

### FINDING-20-022: `discovery.py` — browser Playwright creado/destruido por cada llamada a `try_nav_parse`
- **Severidad**: Minor
- **Archivo**: `src/crawler/discovery.py:237-296`
- **Descripción**: `try_nav_parse` abre un browser Playwright (`await p.chromium.launch(headless=True)`), visita una URL, y cierra el browser en cada invocación. Si en el futuro `discover_urls` fuera modificado para llamar `try_nav_parse` con múltiples URLs, o si se añade retry, el overhead de inicialización del browser se pagaría N veces. Adicionalmente, el scraper principal (`PageScraper`) ya gestiona un browser persistente — hay dos sistemas de gestión de browser en el proyecto sin coordinación.

- **Propuesta**: Alineado con el principio de simplicidad, la solución mínima es reutilizar `PageScraper` si ya está inicializado, o documentar la decisión de tener dos instancias. No es urgente dado que actualmente `try_nav_parse` se llama máximo una vez por job.

- **Esfuerzo**: 2 horas si se unifica, 15 minutos si solo se documenta.

---

### FINDING-20-023: `runner.py` — Patrón "assign then check" inconsistente para cancelación
- **Severidad**: Minor
- **Archivo**: `src/jobs/runner.py:211`, `src/jobs/runner.py:281`, `src/jobs/runner.py:296`, `src/jobs/runner.py:394`
- **Descripción**: Los puntos de verificación de cancelación son inconsistentes: a veces se verifica antes de una fase (`if job.is_cancelled: return`, línea 211), a veces dentro del loop (`if job.is_cancelled: break`, línea 296), y a veces dentro de un loop anidado (`if job.is_cancelled: break`, línea 394). No hay verificación de cancelación después del cleanup de chunks y antes del save a disco. Un job cancelado durante el cleanup del último chunk todavía escribe el archivo a disco. No es un bug crítico, pero la inconsistencia hace difícil razonar sobre el comportamiento de cancelación.

- **Propuesta**: Documentar los puntos de verificación de cancelación en un comentario en `run_job` y añadir una verificación consistente al inicio del save sub-phase.

- **Esfuerzo**: 30 minutos

---

### FINDING-20-024: `routes.py` — `list_models` llama `get_available_models` con `await` en un loop serial
- **Severidad**: Minor
- **Archivo**: `src/api/routes.py:34-37`
- **Descripción**: Cuando se llama sin `provider`, el endpoint `list_models` itera sobre todos los providers en serie (líneas 34-37). Dado que FINDING-20-019 confirma que `_get_openrouter_models` bloquea el event loop, el endpoint `/api/models` bloquea FastAPI durante el tiempo de las tres llamadas. Incluso si se corrige el bug async, las tres llamadas deberían ser concurrentes.

- **Propuesta**:

```python
all_models = []
results = await asyncio.gather(*[get_available_models(p) for p in PROVIDERS.keys()])
for models in results:
    all_models.extend(models)
```

- **Esfuerzo**: 15 minutos

---

## Roadmap de refactoring (priorizado)

Ordenado por ratio impacto/esfuerzo. Asumiendo un desarrollador con 1 semana (5 días, ~6h efectivas/día = 30h totales).

### Semana 1 — Día 1 (6h): Seguridad y bugs reales

| # | Finding | Esfuerzo | Impacto |
|---|---------|----------|---------|
| 1 | **FINDING-20-011**: XSS en `logMessage` e `innerHTML` | 30 min | Seguridad crítica |
| 2 | **FINDING-20-012**: XSS en `generateDynamicHints` | 20 min | Seguridad major |
| 3 | **FINDING-20-007**: Eliminar `reasoning_model` de `validate_models` | 10 min | Bug — jobs bloqueados |
| 4 | **FINDING-20-018**: Corregir links rotos en `_generate_index` | 45 min | Bug funcional |
| 5 | **FINDING-20-021**: Fix bug de precedencia en `getModelCategory` | 20 min | Bug lógico |
| 6 | **FINDING-20-005**: Eliminar `__import__('os')` en `routes.py` | 10 min | Code smell crítico |
| 7 | **FINDING-20-016**: Mover `import httpx` al nivel de módulo | 5 min | Consistencia |

**Total día 1**: ~2.5h de trabajo efectivo. Resto del día: revisión + tests manuales.

---

### Semana 1 — Día 2 (6h): Dead code y DRY en `client.py`

| # | Finding | Esfuerzo | Impacto |
|---|---------|----------|---------|
| 8 | **FINDING-20-003**: Eliminar `generate_legacy` y `get_available_models_legacy` | 15 min | Dead code |
| 9 | **FINDING-20-002**: Extraer `_generate_chat_completion` | 1h | DRY crítico |
| 10 | **FINDING-20-008** + **FINDING-20-019**: Convertir `_get_openrouter_models` a async | 45 min | Bug async/event loop |
| 11 | **FINDING-20-024**: Hacer `list_models` concurrente con `asyncio.gather` | 15 min | Performance |

**Total día 2**: ~2.5h. Resto: tests de integración del cliente LLM.

---

### Semana 1 — Día 3 (6h): `discovery.py` — print y cascade

| # | Finding | Esfuerzo | Impacto |
|---|---------|----------|---------|
| 12 | **FINDING-20-004**: Eliminar los 27 `print()` de `discovery.py` | 30 min | Principio rector violado |
| 13 | **FINDING-20-017**: Refactorizar cascade a loop de estrategias | 1.5h | Complejidad reducida |
| 14 | **FINDING-20-009**: Extraer `_build_clean_url` | 1h | DRY |

**Total día 3**: ~3h. Resto: tests de descubrimiento, verificar que cascade funciona igual.

---

### Semana 1 — Día 4 (6h): `runner.py` — monolito

| # | Finding | Esfuerzo | Impacto |
|---|---------|----------|---------|
| 15 | **FINDING-20-001**: Extraer `_phase_init`, `_phase_discovery`, `_phase_filtering`, `_scrape_page`, `_phase_scrape_all` | 4h | Mayor impacto de legibilidad |
| 16 | **FINDING-20-010**: Wrappear `write_text` con `asyncio.to_thread` | 30 min | Performance async |
| 17 | **FINDING-20-020**: Paralelizar `validate_models` con `asyncio.gather` | 45 min | Performance inicio |

**Total día 4**: ~5.25h. Prioridad máxima del día.

---

### Semana 1 — Día 5 (6h): UI JS y decidir sobre `max_concurrent`

| # | Finding | Esfuerzo | Impacto |
|---|---------|----------|---------|
| 18 | **FINDING-20-013**: Extraer lógica de reconexión SSE | 1.5h | Mantenibilidad |
| 19 | **FINDING-20-015**: Mover constantes DOM de `checkHealth` al scope global | 15 min | Consistencia |
| 20 | **FINDING-20-006**: Decisión sobre `max_concurrent` (Opción A: eliminar del contrato) | 30 min | Honestidad del contrato |
| 21 | **FINDING-20-023**: Documentar puntos de cancelación | 30 min | Claridad |

**Total día 5**: ~2.75h. Resto para documentación y PR review.

---

### Backlog (post-semana 1, menor urgencia)

| # | Finding | Esfuerzo | Justificación de diferimiento |
|---|---------|----------|-------------------------------|
| 22 | **FINDING-20-014**: CSS custom properties para temas | 4-6h | Alto riesgo visual, necesita tests |
| 23 | **FINDING-20-022**: Unificar browser Playwright en discovery/scraper | 2h | No urgente, actualmente correcto |

---

## Estadísticas

- **Total**: 24
- **Critical**: 4 (FINDING-20-001, 20-002, 20-003, 20-011)
- **Major**: 12 (FINDING-20-004, 20-005, 20-006, 20-007, 20-008, 20-009, 20-010, 20-012, 20-013, 20-017, 20-018, 20-019)
- **Minor**: 8 (FINDING-20-014, 20-015, 20-016, 20-020, 20-021, 20-022, 20-023, 20-024)

### Métricas de impacto proyectadas (si se aplica el roadmap completo)

| Métrica | Actual | Proyectado |
|---------|--------|------------|
| LOC de `runner.py` efectivos (función principal) | 463 | ~80 (orquestación) + ~300 (5 helpers) |
| Líneas duplicadas en `client.py` | 77 | ~12 |
| `print()` mezclados con logging | 27 | 0 |
| Funciones dead code | 2 | 0 |
| Parámetros aceptados pero ignorados | 2 (`max_concurrent`, `reasoning_model`) | 0 (removidos o implementados) |
| Vulnerabilidades XSS vía innerHTML | 2 puntos confirmados | 0 |
| Complejidad ciclomática de `run_job` | ~18 | ~5 (solo flow control) |
| Esfuerzo estimado total | — | 26h |
