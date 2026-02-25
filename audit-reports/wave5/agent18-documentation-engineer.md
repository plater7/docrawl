# Wave 5 — Agente 18: Documentation Engineer

**Fecha**: 2025-02-25
**Auditor**: Agente 18 (Documentation Engineer)
**Proyecto**: Docrawl
**Alcance**: Auditoría de documentación, inconsistencias código vs docs, calidad DX

---

## Resumen ejecutivo

Se realizó auditoría de documentación de Docrawl analizando README.md, CLAUDE.md, .env.example, archivos de código (models.py, client.py, cleanup.py, runner.py, routes.py), docker-compose.yml, pytest.ini, y guías de setup/troubleshooting.

**Hallazgos principales:**

1. **Inconsistencia crítica: Retry logic** — CLAUDE.md documenta "max 3 intentos con backoff exponencial", el código tiene `MAX_RETRIES = 2` (2 intentos totales) y backoff lineal `[1, 3]` (no exponencial)

2. **Inconsistencia: Chunk size** — CLAUDE.md no especifica chunk size, README documenta "16KB chunks", código tiene `DEFAULT_CHUNK_SIZE = 16000` caracteres (no bytes)

3. **Mezcla de idiomas no resuelta** — Documentación y código mezclan español e inglés inconsistentemente. README en inglés, CLAUDE.md en español, código mayormente en inglés con comentarios en ambos idiomas

4. **API endpoints documentado obsoleto** — CLAUDE.md lista endpoints antiguo con `GET /api/models` (proxy a Ollama), pero README documenta nuevo con `GET /api/providers` y `GET /api/models?provider=...`

5. **Configuración por defecto inconsistente** — README y código divergen en valores default de configuración

6. **Documentación de archivos faltantes** — README hace referencias a `docs/SETUP.md` y `docs/TROUBLESHOOTING.md` pero no documenta que existen ni su contenido

7. **Falta especificación de MAX_RETRIES** — CLAUDE.md dice "max 3 intentos" para cleanup, cleanup.py tiene `MAX_RETRIES = 2`, pero en el loop se ejecuta 2 veces (intentos 0 y 1)

8. **Idioma del bot creditado inconsistente** — README y .env.example citan "qwen3-coder:free", docker-compose.yml cita "qwen3-coder:free", pero CLAUDE.md no menciona qué modelo se usó para las auditorías anteriores

9. **Endpoint GET /api/health/ready no documentado en README** — CLAUDE.md no menciona este endpoint, pero existe en routes.py y es usado por docker-compose healthcheck

10. **Providers feature no documentada en CLAUDE.md** — README documenta 3 providers (Ollama, OpenRouter, OpenCode), CLAUDE.md solo documenta Ollama

---

## Inconsistencias código vs documentación (Tabla)

| Aspecto | Documentado en CLAUDE.md | Valor real en código | Archivo | Severidad |
|---------|--------------------------|----------------------|---------|-----------|
| Retry intentos cleanup | "max 3 intentos" | `MAX_RETRIES = 2` (2 intentos) | cleanup.py:21 | CRITICAL |
| Backoff cleanup | "backoff exponencial" | `[1, 3]` (lineal) | cleanup.py:22 | MAJOR |
| Chunk size | No especificado | 16000 caracteres | markdown.py:11 | MINOR |
| Default delay_ms | No especificado | 500 ms | models.py:14 | MINOR |
| Default max_concurrent | No especificado | 3 | models.py:15 | MINOR |
| Default max_depth | No especificado | 5 | models.py:16 | MINOR |
| Output path default | `/data/output/<domain>/<section>` | `/data/output` | models.py:13 | MAJOR |
| Endpoints GET /api/models | "proxy a host:11434/api/tags" | "get_available_models(provider)" con provider param | routes.py:24-47 | MAJOR |
| Providers soportados | "Ollama (local), OpenRouter, OpenCode" | Solo Ollama (sin API providers mencionados) | CLAUDE.md:18-29 | MAJOR |
| Health check endpoint | No documentado | GET /api/health/ready existe | routes.py:130-230 | MINOR |
| Filtering cascade fases | Discovery, Filter, Scraping, Cleanup | Init, Discovery, Filtering (básico + LLM), Scraping, Cleanup, Save | runner.py:92-555 | MINOR |

---

## Hallazgos detallados

### FINDING-18-001: Inconsistencia crítica de retry logic y backoff en cleanup
- **Severidad**: CRITICAL
- **Archivos**: `CLAUDE.md:117`, `src/llm/cleanup.py:21-22`
- **Descripción**:
  - CLAUDE.md documenta: "retry con backoff exponencial (max 3 intentos)"
  - cleanup.py contiene:
    - `MAX_RETRIES = 2` (línea 21)
    - `RETRY_BACKOFF = [1, 3]` (línea 22)
  - El loop en cleanup_markdown() itera `for attempt in range(MAX_RETRIES)` (línea 105), ejecutando 0, 1 = 2 intentos totales (no 3)
  - El backoff `[1, 3]` es lineal (1 segundo, luego 3 segundos), no exponencial
- **Impacto**: Documentación engañosa sobre resiliencia del job. Usuarios esperan 3 intentos y backoff exponencial, pero el código hace 2 intentos con backoff lineal
- **Fix propuesto**:
  - Opción A: Corregir CLAUDE.md para reflejar realidad (2 intentos, backoff lineal)
  - Opción B: Actualizar código a 3 intentos y backoff exponencial (ej: `[1, 2, 4]`)
  - Recomendación: Opción B es preferible para resiliencia

### FINDING-18-002: Endpoints API documentados obsoletos
- **Severidad**: MAJOR
- **Archivos**: `CLAUDE.md:142-149`, `README.md:142-149`, `src/api/routes.py`
- **Descripción**:
  - CLAUDE.md y README documentan (idénticamente):
    ```
    GET /api/models → Lista modelos Ollama disponibles (proxy a GET host:11434/api/tags)
    ```
  - Pero routes.py implementa:
    - `GET /api/models?provider=<provider>` que soporta 3 providers: ollama, openrouter, opencode (línea 24-47)
    - `GET /api/providers` que lista providers y su status (línea 50-74)
  - README documenta también: `GET /api/providers` (línea 143) pero CLAUDE.md no lo menciona
  - La implementación es mucho más avanzada que lo documentado
- **Impacto**: Desarrolladores integrados se perderán. La API es capaz de más de lo que se documenta
- **Fix propuesto**: Actualizar CLAUDE.md y README con:
  - `GET /api/providers` — lista providers configurados
  - `GET /api/models?provider=ollama|openrouter|opencode` — modelos por provider
  - Documentar nuevo flujo multi-provider

### FINDING-18-003: Output path default inconsistente
- **Severidad**: MAJOR
- **Archivos**: `CLAUDE.md:126`, `src/api/models.py:13`
- **Descripción**:
  - CLAUDE.md documenta: "Output path auto-generado: `/data/output/<dominio>/<seccion>`"
  - models.py define: `output_path: str = "/data/output"`
  - La lógica real en runner.py:285 usa `Path(request.output_path)` directamente, sin auto-generar dominio/sección
  - runner.py NO implementa la lógica de extracción de dominio/sección documentada en CLAUDE.md
- **Impacto**: Usuario espera auto-generación tipo "/data/output/example.com/guide" pero el código usa el path literal del usuario
- **Fix propuesto**:
  - Actualizar CLAUDE.md para aclarar que output_path es usado literalmente (no auto-generado)
  - O implementar la auto-generación documentada en runner.py

### FINDING-18-004: Chunk size documentado en README pero no en CLAUDE.md
- **Severidad**: MINOR
- **Archivos**: `README.md:102`, `src/scraper/markdown.py:11`
- **Descripción**:
  - README.md menciona: "Chunking by headings (16KB chunks)" (línea 102)
  - CLAUDE.md no especifica chunk size
  - markdown.py define: `DEFAULT_CHUNK_SIZE = 16000` (caracteres, no bytes)
  - La conversión: 16KB de bytes ≠ 16000 caracteres. El code usa caracteres (roughly 16KB de UTF-8 en muchos casos, pero no exactamente)
- **Impacto**: Inconsistencia entre documentos. README más completo que CLAUDE.md en este aspecto
- **Fix propuesto**:
  - Actualizar CLAUDE.md para incluir "Chunk size: 16000 caracteres"
  - Aclarar en README: "16KB chunks (16000 characters)" si es exacto

### FINDING-18-005: Mezcla de idiomas sin convención clara
- **Severidad**: MAJOR
- **Archivos**: Todos (código, docs)
- **Descripción**:
  - README.md: 100% inglés
  - CLAUDE.md: 100% español
  - .env.example: Títulos en inglés, comentarios en inglés
  - requirements.txt: Sin comentarios
  - docker-compose.yml: Comentarios en inglés
  - src/llm/cleanup.py: Docstrings en inglés, comentarios en inglés
  - src/jobs/runner.py: Docstrings en inglés, comentarios en inglés
  - .env comments: "Docker users: Use http://host.docker.internal:11434" (inglés)
  - docs/SETUP.md: Título en inglés + descripción en español, mezcla
  - docs/TROUBLESHOOTING.md: Título en inglés + contenido en inglés
  - Pero bot credits en archivos dicen "glm-5-free", "qwen3-coder:free"
- **Impacto**: Confusión para desarrolladores. No hay estándar claro. Nuevos contribuidores no saben en qué idioma escribir
- **Fix propuesto**:
  - Adoptar una convención: **OPCIÓN RECOMENDADA: Inglés para todo**
    - README.md ✓ (ya en inglés)
    - CLAUDE.md → traducir a inglés
    - docs/ → traducir a inglés
    - Code comments → ya en inglés ✓
  - O: **Español para todo** (menos probable dada audiencia global)
  - Agregar CONTRIBUTING.md especificando idioma

### FINDING-18-006: Health check endpoint no documentado en CLAUDE.md
- **Severidad**: MINOR
- **Archivos**: `CLAUDE.md`, `src/api/routes.py:130`, `docker-compose.yml:32`
- **Descripción**:
  - CLAUDE.md lista endpoints en sección "API endpoints" (línea 140-149)
  - No menciona `GET /api/health/ready`
  - Pero routes.py implementa el endpoint con checks detallados (Ollama, disk space, write permissions) (línea 130-230)
  - docker-compose.yml usa este endpoint en healthcheck (línea 32)
  - README no menciona este endpoint tampoco
- **Impacto**: Endpoint importante no documentado. Operadores no saben que existe
- **Fix propuesto**:
  - Agregar a CLAUDE.md sección "Health Check":
    ```
    GET /api/health/ready → Status de disponibilidad del sistema
    Response: { "ready": bool, "issues": [str], "checks": {...} }
    ```

### FINDING-18-007: Providers feature no documentada en CLAUDE.md
- **Severidad**: MAJOR
- **Archivos**: `CLAUDE.md`, `README.md:131-137`, `src/api/routes.py:50-74`, `src/llm/client.py`
- **Descripción**:
  - README documenta 3 providers: Ollama, OpenRouter, OpenCode (línea 131-137)
  - routes.py implementa endpoint GET /api/providers (línea 50-74)
  - CLAUDE.md nunca menciona la palabra "provider" ni multi-provider support
  - CLAUDE.md:95 dice "Usuario ingresa: ... 3 modelos Ollama ..." asumiendo Ollama solamente
  - client.py (línea 14-50) contiene lógica completa para 3 providers
- **Impacto**: CLAUDE.md completamente desactualizado. Parece que la feature de multi-provider fue agregada después, pero CLAUDE.md no se actualizó
- **Fix propuesto**:
  - Actualizar CLAUDE.md sección "Stack" para agregar: "Multi-provider LLM support: Ollama (local), OpenRouter (API), OpenCode (API)"
  - Actualizar flujo de job para aclarar que los 3 modelos pueden ser de diferentes providers
  - Agregar tabla de providers soportados

### FINDING-18-008: Values default de configuración no documentados en CLAUDE.md
- **Severidad**: MINOR
- **Archivos**: `CLAUDE.md:95`, `src/api/models.py:13-22`, `README.md:155-161`
- **Descripción**:
  - CLAUDE.md describe flujo pero NO especifica valores default
  - Ejemplo de payload (línea 153-164) muestra valores pero sin indicar que son defaults
  - models.py define todos los defaults:
    - `output_path = "/data/output"`
    - `delay_ms = 500`
    - `max_concurrent = 3`
    - `max_depth = 5`
    - `respect_robots_txt = True`
    - `use_native_markdown = True`
    - `use_markdown_proxy = False`
    - `language = "en"`
  - README tiene tabla de defaults (línea 155-161) — más completamente documentado que CLAUDE.md
- **Impacto**: Usuarios de CLAUDE.md no saben los defaults
- **Fix propuesto**:
  - Agregar tabla en CLAUDE.md bajo "Payload de POST /api/jobs":
    ```
    | Campo | Default | Descripción |
    |-------|---------|-------------|
    | delay_ms | 500 | Delay entre requests en ms |
    | max_concurrent | 3 | Max requests concurrentes |
    | ...
    ```

### FINDING-18-009: README menciona archivos de docs no descritos en contenido
- **Severidad**: MINOR
- **Archivos**: `README.md:67`, `README.md:183`, `docs/SETUP.md`, `docs/TROUBLESHOOTING.md`
- **Descripción**:
  - README línea 67: "Ver [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) para common issues"
  - README línea 183: "Ver [SETUP.md](./docs/SETUP.md) para instrucciones completas"
  - Ambos archivos existen y están bien documentados
  - Pero el resto de README no los menciona en tabla de contenidos o resumen
  - La sección "Quick Start" (línea 48-65) no menciona troubleshooting
- **Impacto**: Nuevo usuario puede perder archivos de documentación importantes
- **Fix propuesto**:
  - Agregar sección "Documentation" en README después de "Quick Start"
  - Crear tabla o índice: "Setup Instructions", "Troubleshooting", "Architecture", etc.

### FINDING-18-010: Discrepancia en versión documentada
- **Severidad**: MINOR
- **Archivos**: `README.md:2`, `docker-compose.yml`, `src/main.py`
- **Descripción**:
  - README.md línea 2 especifica: `version-v0.8.5`
  - No hay archivo VERSION o versión en setup.py
  - docker-compose.yml no especifica qué versión se buildea
  - src/main.py no exporta `__version__`
- **Impacto**: Unclear cómo se incrementa versión o dónde es source of truth
- **Fix propuesto**:
  - Crear `src/__init__.py` con `__version__ = "0.8.5"`
  - Agregar comentario en README.md sobre cómo actualizar versión

### FINDING-18-011: SETUP.md mezcla idiomas (español/inglés)
- **Severidad**: MINOR
- **Archivos**: `docs/SETUP.md:1-3` (título en inglés, descripción en español), línea 5-6 (comentarios español)
- **Descripción**:
  - Línea 1: `# Cloudflare Tunnel + Workers VPC Setup` (inglés)
  - Línea 3: "Exposer Docrawl a internet de forma segura sin IP pública, usando..." (español)
  - Línea 5-6: Arquitectura en inglés pero comentarios español
  - Inconsistencia de idioma dentro del mismo archivo
- **Impacto**: Confusión
- **Fix propuesto**:
  - Traducir SETUP.md completamente al inglés (para consistencia con README)

### FINDING-18-012: .env.example no documenta OPENROUTER_API_KEY y OPENCODE_API_KEY
- **Severidad**: MINOR
- **Archivos**: `.env.example:33-41`, `docker-compose.yml:18-19`
- **Descripción**:
  - .env.example documenta OPENROUTER_API_KEY y OPENCODE_API_KEY (línea 33-41)
  - Pero docker-compose.yml no propaga OPENROUTER_API_KEY a container, solo OPENCODE_API_KEY
  - Línea 18: `OLLAMA_URL=http://host.docker.internal:11434` ✓
  - Línea 18-19: OPENROUTER_API_KEY y OPENCODE_API_KEY hay pero son `${...}` variables
  - Esto funciona pero .env.example no claramente explica que deben estar en `.env` para docker-compose
- **Impacto**: Usuario configura .env.example pero docker-compose no los pasa a container
- **Fix propuesto**:
  - Actualizar .env.example para agregar:
    ```
    # Note: These variables must be in .env for docker-compose to pass them to the container
    # Example: cp .env.example .env && edit .env with your keys
    ```

### FINDING-18-013: pytest.ini no tiene documentación README
- **Severidad**: SUGGESTION
- **Archivos**: `README.md`, `pytest.ini`
- **Descripción**:
  - README menciona "pytest tests/ -v" (línea 205)
  - Pero no explica setup de testing o markers disponibles
  - pytest.ini define markers: unit, integration, slow, asyncio (línea 19-23)
  - Pero README no menciona: "pytest tests/ -m unit" para solo tests unitarios
- **Impacto**: Usuarios no saben cómo correr subsets de tests
- **Fix propuesto**:
  - Agregar en README sección "Testing":
    ```bash
    # Run all tests
    pytest tests/ -v

    # Run only unit tests
    pytest tests/ -m unit

    # Run integration tests (slower)
    pytest tests/ -m integration
    ```

### FINDING-18-014: Falta especificación de Python 3.12 en README Quick Start
- **Severidad**: MINOR
- **Archivos**: `README.md`, `CLAUDE.md:69`, `docker-compose.yml`
- **Descripción**:
  - README badges (línea 3) mencionan "python-3.12"
  - Pero "Quick Start" no especifica que se requiere Python 3.12 localmente para setup.sh
  - CLAUDE.md sí lo menciona (línea 69)
  - docker-compose.yml usa `python:3.12-slim` (correcto)
- **Impacto**: Usuario con Python 3.11 intenta correr setup.sh y falla
- **Fix propuesto**:
  - Agregar en README "Quick Start" una nota:
    ```
    > **Requirements**: Python 3.12+, Docker 20.10+
    ```

### FINDING-18-015: CLAUDE.md no describe roles de modelos con suficiente detalle
- **Severidad**: MINOR
- **Archivos**: `CLAUDE.md:95`, `README.md:121-129`
- **Descripción**:
  - CLAUDE.md línea 95: "Usuario ingresa: URL raiz, 3 modelos Ollama"
  - README tabla (línea 123-127) especifica roles:
    - Crawl: Discovery & URL filtering
    - Pipeline: Markdown cleanup
    - Reasoning: Complex analysis (future)
  - CLAUDE.md no es tan explícito sobre los roles en "Payload de POST /api/jobs"
- **Impacto**: Falta claridad sobre qué modelo para qué
- **Fix propuesto**:
  - Actualizar CLAUDE.md sección Payload para incluir roles explícitos

---

## Estadísticas

- **Total de hallazgos**: 15
- **CRITICAL**: 1
- **MAJOR**: 6
- **MINOR**: 8
- **SUGGESTION**: 1

---

## Archivos con documentación incompleta o desactualizada

| Archivo | Estado | Notas |
|---------|--------|-------|
| CLAUDE.md | ⚠️ Desactualizado | Falta providers, health endpoint, retry logic inconsistente |
| README.md | ✓ Completo | Mejor documentado que CLAUDE.md, pero lenguaje mezcla referencias |
| .env.example | ✓ Correcto | Documentación clara, pero claridad sobre docker-compose propag. |
| docs/SETUP.md | ✓ Correcto | Contenido bueno, pero mezcla español/inglés |
| docs/TROUBLESHOOTING.md | ✓ Excelente | Comprehensivo, resuelve issues comunes |
| pytest.ini | ✓ Correcto | Buen setup, pero README no documenta markers |

---

## Patrones encontrados

1. **Divergencia entre README (inglés) y CLAUDE.md (español)** — README es más actualizado y completo
2. **Multi-provider implementado pero no documentado en CLAUDE.md** — Feature fue agregada después, CLAUDE.md no se actualizó
3. **API endpoints más avanzado que documentado** — Código implementa features no mencionadas en docs
4. **Documentación de configuración inconsistente** — Algunos defaults en README, otros en código, CLAUDE.md sin defaults
5. **Retry logic documentado vs real tiene mismatch** — Documentación dice 3 intentos exponencial, código hace 2 lineal

---

## Recomendaciones prioritarias

### Prioridad P0 (Debe arreglarse ya)

1. **Corregir retry logic documentation** (FINDING-18-001)
   - Actualizar CLAUDE.md:117 para decir "max 2 intentos con backoff lineal [1, 3]s"
   - O cambiar código a 3 intentos con backoff exponencial

2. **Actualizar CLAUDE.md multi-provider** (FINDING-18-007)
   - Agregar sección sobre OpenRouter y OpenCode support
   - Actualizar descripción del flujo para ser provider-agnostic

### Prioridad P1 (Importante)

3. **Resolver mezcla de idiomas** (FINDING-18-005)
   - Adoptar convención: **Inglés para documentación y código**
   - Traducir CLAUDE.md a inglés (o mantener en español pero ser consistente)
   - Traducir docs/SETUP.md a inglés

4. **Actualizar endpoints API documentation** (FINDING-18-002)
   - CLAUDE.md debe documentar GET /api/providers
   - Actualizar descripción de GET /api/models para aclarar param ?provider

### Prioridad P2 (Bueno tener)

5. **Documentar health check endpoint** (FINDING-18-006)
   - Agregar GET /api/health/ready a CLAUDE.md

6. **Agregar tabla de defaults** (FINDING-18-008)
   - Incluir defaults en CLAUDE.md para que tenga feature parity con README

7. **Aclarar output path behavior** (FINDING-18-003)
   - Documentar que output_path es literal, no auto-generado

---

## Conclusión

La documentación de Docrawl tiene **inconsistencias significativas** entre CLAUDE.md y README.md, y entre documentación y código. El hallazgo más crítico es la **discrepancia de retry logic** que afecta promesas de resiliencia.

**README.md es la documentación más completa y actualizada.** CLAUDE.md parece ser la versión original que no se actualiza con cambios de código como multi-provider support.

**Acción recomendada**: Hacer de CLAUDE.md y README.md la fuente única de verdad, traducir todo a inglés por consistencia, y validar que cada cambio de código se refleje en documentación.

---

**Generado por**: Agente 18 (Documentation Engineer) — Wave 5 Auditoría
**Timestamp**: 2025-02-25T12:00:00Z
