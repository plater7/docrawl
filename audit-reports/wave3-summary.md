# Wave 3 — AI/ML Engineering Summary

**Estado:** ✅ DONE
**Agentes:** 3 (10 opus, 11 opus, 12 sonnet)
**Total findings:** 48 (7 critical, 20 major, 18 minor, 3 suggestions)

---

## Agentes

| Agente | Rol | Findings | Critical |
|--------|-----|----------|---------|
| 10 — ai-engineer | Token counting, context window, routing | 18 | 3 |
| 11 — llm-architect | Arquitectura cliente, pooling, DRY | 18 | 2 |
| 12 — prompt-engineer | Prompts, injection, output parsing | 12 | 2 |

Reportes detallados: `audit-reports/wave3/agent10-ai-engineer.md`, `agent11-llm-architect.md`, `agent12-prompt-engineer.md`

---

## Hallazgos Críticos (7)

### C-01: Chunk size vs num_ctx mismatch — truncamiento silencioso
- **Archivos:** `src/llm/cleanup.py:74-85`, `src/scraper/markdown.py:11`
- Chunks de 16,000 chars pero `num_ctx: 8192` tokens. Ollama trunca silenciosamente. El LLM limpia solo una fracción del chunk sin error.
- **CVSS:** High (datos corruptos, sin detección)

### C-02: URL filter context overflow — URLs perdidas silenciosamente
- **Archivos:** `src/llm/filter.py:26-31,43`
- `num_ctx: 4096` para filtrado. Sitios con 100+ URLs desbordan el contexto. LLM devuelve JSON válido pero omite URLs que no vio.
- **CVSS:** High (crawl incompleto sin advertencia)

### C-03: Zero token counting — imposible detectar truncamiento
- **Archivo:** `src/llm/client.py:200-209`
- Ollama devuelve `prompt_eval_count` y `eval_count` en cada respuesta. El código descarta todo el metadata. No hay forma de detectar cuándo ocurre truncamiento.

### C-04: Sin connection pooling — 100+ TCP connections por job
- **Archivo:** `src/llm/client.py:68,201,243,283`
- Cada llamada LLM crea y destruye un `httpx.AsyncClient`. Job de 50 páginas con 3 chunks cada una = 150+ conexiones efímeras.

### C-05: Sync HTTP bloquea event loop hasta 10 segundos
- **Archivo:** `src/llm/client.py:102`
- `_get_openrouter_models()` usa `httpx.get()` síncrono. Bloquea todo el asyncio event loop, congela SSE streams y endpoints.

### C-06: Prompt injection via contenido scrapeado (cleanup)
- **Archivo:** `src/llm/cleanup.py:15-19,101`
- Template usa `.format(markdown=markdown)` sin delimitadores. Sitio malicioso puede escribir `---END--- SYSTEM: Ignore previous instructions` en su HTML para controlar el LLM.

### C-07: Prompt injection via URLs (filtrado)
- **Archivo:** `src/llm/filter.py:15-23,43`
- URLs se insertan con `"\n".join(urls)` sin sanitización. URL con texto en el path puede inyectar instrucciones al LLM de filtrado.

---

## Hallazgos Major (selección)

| ID | Archivo | Descripción |
|----|---------|-------------|
| M-01 | `client.py:` múltiples | `_generate_openrouter` y `_generate_opencode` idénticas (DRY) |
| M-02 | `client.py:get_provider_for_model` | Provider routing silencioso: `openai/gpt-4` → Ollama (falla con error confuso) |
| M-03 | `client.py` | `get_available_models()` llamada 3 veces sin caché por job |
| M-04 | `client.py:MAX_TIMEOUT` | Timeout de 90s insuficiente para modelos lentos (deepseek-r1:32b tarda 3-5 min/chunk) |
| M-05 | `client.py:filter_urls_with_llm` | Sin retry en filtrado: error transitorio → filtrado omitido silenciosamente |
| M-06 | `runner.py` | `reasoning_model` validado en API pero nunca invocado en runner |
| M-07 | `runner.py` | Exception handler de cleanup es dead code → `pages_partial` siempre 0 |
| M-08 | `client.py` | `options` (temperature, num_ctx) ignorado por OpenRouter/OpenCode |
| M-09 | `filter.py` | Parser JSON frágil: falla con ```json, prefijos de texto, objetos vs arrays |
| M-10 | `cleanup.py` | Sin señal de completitud: acepta refusals del modelo como cleanup válido |
| M-11 | Todos los prompts | Sin few-shot examples — tasa de fallo >30% en modelos 7B-14B |

---

## Hallazgos Minor / Suggestions

- Dead code: `generate_legacy`, `get_available_models_legacy` (zero usages)
- Retry backoff tiene elemento muerto (`RETRY_BACKOFF[1] = 3` nunca usado)
- `max_concurrent` en API nunca usado — procesamiento siempre secuencial
- Error messages exponen `host.docker.internal:11434` en SSE → UI
- `num_ctx: 8192` hardcoded sin considerar capacidad del modelo
- Sin validación de tipo en JSON de filtrado (array vs objeto)
- Sin tracking de latencia ni tokens usados por job
- Sin cost tracking para providers de pago (OpenRouter)

---

## Archivos más afectados

| Archivo | Findings | Severidad |
|---------|----------|-----------|
| `src/llm/client.py` | 14 | 4 critical, 5 major |
| `src/llm/cleanup.py` | 8 | 2 critical, 3 major |
| `src/llm/filter.py` | 7 | 2 critical, 3 major |
| `src/jobs/runner.py` | 5 | 1 critical, 2 major |

---

## Fix de mayor impacto (quick wins)

1. **Delimitadores XML en prompts** (`<document>` / `<urls>`) — resuelve C-06, C-07, M-09, M-10, M-11 con cambio de texto puro
2. **`httpx.AsyncClient` compartido** — resuelve C-04 y C-05 con refactor puntual
3. **Leer y loguear `prompt_eval_count`** de respuestas Ollama — resuelve C-03 inmediatamente
4. **Reducir chunk size a ~6000 chars** — resuelve C-01 sin cambiar infra
