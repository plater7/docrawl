# Wave 4 — Agente 16: QA Expert

## Resumen ejecutivo

El proyecto Docrawl tiene una cobertura de tests extremadamente baja para su estado de pre-produccion. De 14 modulos de codigo fuente (excluyendo `__init__.py`), solo 4 tienen tests: `crawler/discovery.py`, `crawler/filter.py`, `crawler/robots.py`, y `scraper/page.py` (parcialmente). Los modulos mas criticos — `api/routes.py`, `jobs/runner.py`, `jobs/manager.py`, `llm/*`, y `scraper/page.py` (Playwright) — tienen cobertura cero.

El total de tests existentes es de **95 funciones de test** distribuidas en 4 archivos. La mayoria abusan de mocks de alto nivel que testean la logica de `discover_urls` (coordinador) en vez de los componentes reales (`try_sitemap`, `try_nav_parse`, `recursive_crawl`). Los tests existentes son de buena calidad estructural pero no alcanzan la logica interna de los modulos individuales.

Se identifican **22 hallazgos**: 5 criticos, 7 mayores, 5 menores, 5 sugerencias.

**Cobertura estimada global: 12-18% de las lineas ejecutables del proyecto.**

---

## Cobertura actual

| Modulo | Tests existentes | Cobertura estimada | Criticidad |
|--------|-----------------|-------------------|-----------|
| `src/crawler/discovery.py` (571 LOC) | 27 tests | ~25% — solo `normalize_url` y `discover_urls` con mocks; internos `try_sitemap`, `try_nav_parse`, `recursive_crawl` sin cobertura real | ALTA |
| `src/crawler/filter.py` (149 LOC) | 37 tests | ~70% — buen cubrimiento; falta rama `base_url` con lenguaje en `_matches_language` | MEDIA |
| `src/crawler/robots.py` (64 LOC) | 26 tests | ~85% — bien cubierto; falta: `is_allowed` con disallow lowercaseado vs path case-sensitive (bug conocido) | MEDIA |
| `src/scraper/page.py` (166 LOC) | 3 tests | ~15% — solo `fetch_markdown_native` y `fetch_markdown_proxy`; `PageScraper` (Playwright) sin tests | MUY ALTA |
| `src/scraper/markdown.py` (129 LOC) | 1 test | ~5% — solo un caso de `chunk_markdown`; `_pre_clean_markdown`, multi-chunk, CHUNK_OVERLAP sin testear | ALTA |
| `src/api/routes.py` (230 LOC) | 0 tests | 0% | MUY ALTA |
| `src/api/models.py` (41 LOC) | 0 tests | 0% | BAJA |
| `src/jobs/manager.py` (117 LOC) | 0 tests | 0% | MUY ALTA |
| `src/jobs/runner.py` (591 LOC) | 0 tests | 0% | MUY ALTA |
| `src/llm/client.py` (312 LOC) | 0 tests | 0% | ALTA |
| `src/llm/filter.py` (67 LOC) | 0 tests | 0% | ALTA |
| `src/llm/cleanup.py` (124 LOC) | 0 tests | 0% | ALTA |
| `src/exceptions.py` (88 LOC) | 0 tests | 0% | BAJA |
| `src/main.py` (27 LOC) | 0 tests | 0% | BAJA |

**Modulos sin ningun test: 9 de 14 (64%)**
**LOC sin cobertura: ~1,597 de ~2,676 (60%)**

---

## Hallazgos

### FINDING-16-001: Cero tests para la capa de API (FastAPI routes)
- **Severidad**: Critical
- **Archivo**: `src/api/routes.py`
- **Descripcion**: Ninguno de los 7 endpoints de la API tiene tests. Esto incluye `POST /api/jobs` (que valida y lanza jobs), `GET /api/jobs/{id}/events` (SSE stream), `POST /api/jobs/{id}/cancel`, `GET /api/jobs/{id}/status`, `GET /api/models`, `GET /api/providers`, y `GET /api/health/ready`. La ausencia de tests de API significa que no hay validacion automatizada de contratos HTTP, codigos de respuesta, manejo de errores 404/422, ni comportamiento bajo entradas invalidas.
- **Impacto**: Cualquier regresion en los endpoints pasa a produccion sin deteccion. El endpoint `POST /api/jobs` acepta `output_path` (vector de path traversal CVSS 9.1) sin que exista ningun test que verifique que la validacion es correcta. El endpoint `GET /api/health/ready` hace side effects (escribe un archivo de prueba en `/data`) sin tests que verifiquen comportamiento bajo errores de permisos.
- **Fix**: Agregar tests con `FastAPI TestClient` para todos los endpoints. Priorizar: `POST /api/jobs` con payloads validos, invalidos, y con path traversal; `GET /api/jobs/{id}/status` con job inexistente (debe retornar 404); `POST /api/jobs/{id}/cancel` en jobs completados. Archivo sugerido: `tests/api/test_routes.py`.

---

### FINDING-16-002: Cero tests para jobs/runner.py -- modulo mas critico del proyecto
- **Severidad**: Critical
- **Archivo**: `src/jobs/runner.py`
- **Descripcion**: runner.py es el modulo mas complejo del proyecto (591 LOC). No existe ningun test. Las funciones sin tests: run_job (orquestacion de 7 fases), validate_models, _url_to_filepath, _generate_index, _log. Bug conocido de _generate_index en linea 587: path.replace ("/", "_") genera links incorrectos en _index.md -- guide_install.md en vez de guide/install.md -- documentado en PLAN.md sin test de regresion.
- **Impacto**: _url_to_filepath tiene logica de path resolution directa con filesystem. Comportamiento bajo cancelacion concurrente nunca testeado. Bug de links rotos puede reintroducirse indefinidamente.
- **Fix**: Tests unitarios para _url_to_filepath (URL base, URL con path, URL con extension, path traversal). Tests para _generate_index verificando links con "/" no "_". Tests de integracion con mocks para run_job. Archivo sugerido: tests/jobs/test_runner_utils.py.
---

### FINDING-16-003: Cero tests para jobs/manager.py -- gestion de estado y concurrencia
- **Severidad**: Critical
- **Archivo**: `src/jobs/manager.py`
- **Descripcion**: JobManager y Job no tienen ningun test. Job.event_stream tiene 5 ramas (evento normal, timeout con task muerto, timeout con task vivo, GeneratorExit, excepcion generica) -- ninguna testeada. La in-memory store self._jobs no tiene tests de comportamiento bajo concurrencia.
- **Impacto**: Race conditions entre cancel_job y run_job sin cobertura. Si runner task muere sin emitir job_done, los clientes SSE quedan colgados indefinidamente.
- **Fix**: Tests para Job.event_stream con asyncio.Queue real. Test para runner task died. Test cancel_job con job inexistente. Archivo sugerido: tests/jobs/test_manager.py.
---

### FINDING-16-004: Cero tests de seguridad -- path traversal, SSRF, XSS sin tests de regresion
- **Severidad**: Critical
- **Archivo**: `src/api/routes.py`, `src/jobs/runner.py`, `src/api/models.py`
- **Descripcion**: Ningun test verifica los vectores de seguridad de Waves 1-2. output_path en JobRequest es tipo str sin validacion Pydantic -- acepta rutas maliciosas sin error de validacion. La URL de crawl se pasa directamente a page.goto(url) sin filtrar URLs internas. Los hallazgos CVSS 9.1 y 9.8 de Waves 1-2 no tienen tests de regresion automatizados.
- **Impacto**: Un fix de path traversal puede ser revertido accidentalmente sin que CI lo detecte. Vulnerabilidades pueden introducirse en cualquier PR sin deteccion automatizada.
- **Fix**: Suite tests/security/test_path_traversal.py con output_path maliciosos que deben ser rechazados. Suite tests/security/test_ssrf.py para URLs internas. Estos tests deben escribirse simultaneamente con los fixes de seguridad para servir como tests de regresion permanentes.
---

### FINDING-16-005: Cero tests para llm/ -- cliente, filter, y cleanup
- **Severidad**: Critical
- **Archivo**: `src/llm/client.py`, `src/llm/filter.py`, `src/llm/cleanup.py`
- **Descripcion**: 503 LOC sin ningun test. Bugs especificos sin cobertura: (a) get_provider_for_model con namespace desconocido lanza ValueError: Unknown provider -- sin test. (b) cleanup_markdown hace 2 intentos (MAX_RETRIES=2) pero CLAUDE.md documenta max 3 intentos -- discrepancia sin test de regresion. (c) _get_openrouter_models es sincrona en contexto async (httpx.get bloqueante) sin test que detecte el bloqueo del event loop. (d) filter_urls_with_llm con JSON malformado del LLM nunca se testea.
- **Impacto**: Bugs conocidos (provider routing incorrecto, retry count incorrecto respecto a documentacion) sin regresion. Cambios en prompts o parsing de respuestas LLM pueden romper el pipeline sin deteccion.
- **Fix**: Tests para get_provider_for_model (bare model, namespaced correcto, namespace desconocido). Tests para needs_llm_cleanup (texto con noise, texto codigo >60%, texto corto <2000 chars). Tests para cleanup_markdown verificando exactamente 2 intentos antes del fallback al markdown original. Tests para filter_urls_with_llm: JSON valido, con code blocks markdown, JSON invalido (fallback), exception (fallback).

---

### FINDING-16-006: Tests de test_discovery.py mockean demasiado alto -- no testean implementacion real
- **Severidad**: Major
- **Archivo**: `tests/crawler/test_discovery.py`
- **Descripcion**: Los 27 tests mockean try_sitemap, try_nav_parse, y recursive_crawl directamente, testando solo la coordinacion de discover_urls. Implementaciones reales (parsing XML, gzip, sitemap index anidado, Playwright, BFS, rate limiting, MAX_URLS=1000) sin cobertura. Tests test_early_exit_with_large_sitemap y test_skip_nav_if_sitemap_100_plus asumen thresholds numericos (500, 100) que no existen en el codigo -- la logica de cascade es binaria: cualquier URL en all_urls salta la siguiente estrategia.
- **Impacto**: Bugs en el parsing XML real de try_sitemap no se detectan. Tests con nombres incorrectos enganan a futuros developers sobre el comportamiento real del sistema.
- **Fix**: Tests de try_sitemap con httpx.MockTransport usando fixtures XML de conftest.py (sample_sitemap_xml, nested_sitemap_index_xml -- actualmente sin usar). Tests de recursive_crawl con pytest-httpserver. Renombrar tests de thresholds a nombres que reflejen la logica binaria real: test_cascade_skips_nav_if_any_sitemap_url_found.

---

### FINDING-16-007: scraper/markdown.py con cobertura minima -- 1 test de 9 ramas posibles
- **Severidad**: Major
- **Archivo**: `tests/scraper/test_markdown_negotiation.py`, `src/scraper/markdown.py`
- **Descripcion**: 0 tests para _pre_clean_markdown (37 lineas con: deteccion de CSS/JS blocks con estado in_noise_block, 6 NOISE_PATTERNS regex, 8 NOISE_LINE_PATTERNS, collapsing de blank lines) y html_to_markdown. chunk_markdown tiene 9 ramas con solo 1 caso testeado. CHUNK_OVERLAP=200 genera contenido duplicado (bug documentado en PLAN.md) sin test de regresion.
- **Fix**: Tests para _pre_clean_markdown con: CSS block (linea sola con solo {), Next.js hydration pattern, noise line patterns como On this page. Tests para chunk_markdown con texto mayor que DEFAULT_CHUNK_SIZE (16000 chars) verificando split en heading boundary y solapamiento medible entre chunks consecutivos.
---

### FINDING-16-008: conftest.py tiene fixtures no utilizados y usa API deprecada de pytest-asyncio
- **Severidad**: Major
- **Archivo**: `tests/conftest.py`
- **Descripcion**: sample_urls nunca usado (0 referencias en todo el proyecto). sample_sitemap_xml, invalid_sitemap_xml, nested_sitemap_index_xml no usados porque los tests mockean try_sitemap en nivel mas alto. El fixture event_loop usa API deprecada en pytest-asyncio >= 0.22 generando DeprecationWarning que puede ocultar errores reales en CI.
- **Fix**: Eliminar fixture event_loop manual -- pytest.ini ya tiene asyncio_mode = auto que lo hace innecesario. Usar fixtures XML en tests reales de try_sitemap (FINDING-16-006).

---

### FINDING-16-009: Sin tests de concurrencia ni de cancelacion de jobs
- **Severidad**: Major
- **Archivo**: `src/jobs/manager.py`, `src/jobs/runner.py`
- **Descripcion**: self._jobs es dict compartido sin locks. Los 4 puntos de chequeo de cancelacion (is_cancelled) en runner.py sin tests: tras discovery, tras filtering, en el loop de URLs, en el loop de chunks. Cancelacion durante scraping de Playwright nunca verificada -- el bloque finally await scraper.stop() puede fallar silenciosamente causando resource leaks de browser.
- **Fix**: Test de cancelacion: crear job, cancelar inmediatamente via cancel_job, verificar job.status cancelled y evento SSE job_cancelled emitido. Test de creacion simultanea: N jobs con asyncio.gather, verificar IDs unicos en job_manager._jobs.

---

### FINDING-16-010: _url_to_filepath y _generate_index sin tests -- incluyendo bug documentado de links rotos
- **Severidad**: Major
- **Archivo**: `src/jobs/runner.py` (lineas 557 y 579)
- **Descripcion**: Bug conocido de _generate_index en linea 587: path.replace con slash genera underscore en los links -- docs/guide/install se convierte en docs_guide_install.md (link roto) en vez de docs/guide/install.md. _url_to_filepath sin tests para: URL igual a base (retorna index.md), URL con extension .html (se elimina), multiplex niveles de path bajo base path.
- **Impacto**: El bug de _generate_index hace que todos los links en _index.md esten rotos. Sin test de regresion, el fix puede ser reintroducido accidentalmente.
- **Fix**: Tests parametrizados para _url_to_filepath (URL base, URL con path, URL con extension). Test para _generate_index: generar indice para 3 URLs y verificar que links contienen slash como separador, no underscore.
---

### FINDING-16-011: Sin tests de integracion end-to-end con FastAPI TestClient
- **Severidad**: Major
- **Archivo**: `tests/` (ausentes directorios api/ e integration/)
- **Descripcion**: Ningun test usa FastAPI TestClient o httpx.AsyncClient para testear el stack completo. La integracion entre routes.py, JobManager, y runner.py nunca se verifica. El sistema usa SSE para comunicacion de progreso -- sin tests de SSE, no se verifica que el stream se genere correctamente.
- **Impacto**: Un cambio en como routes.py serializa JobStatus podria romper la UI sin deteccion en CI. Un cambio en el nombre de un campo de respuesta JSON pasa silenciosamente.
- **Fix**: Crear tests/api/test_routes.py con TestClient de FastAPI. Mockear JobManager.create_job para aislar el test de la orquestacion del job. Verificar: response 200 con JSON valido de JobStatus, response 404 para job inexistente, response 422 para payload invalido.

---

### FINDING-16-012: pytest.ini sin umbral minimo de cobertura -- CI pasa silenciosamente con 0%
- **Severidad**: Major
- **Archivo**: `pytest.ini`
- **Descripcion**: pytest.ini configura --cov=src, --cov-report=term-missing, --cov-report=html, y --cov-branch, pero no configura --cov-fail-under. Sin umbral minimo, el CI siempre pasa independientemente de la cobertura real. El README menciona objetivo de 80%+ code coverage pero nada lo enforcea automaticamente. Con cobertura real actual de ~12-18%, el CI da luz verde silenciosamente en cada commit.
- **Impacto**: El CI no falla cuando se agregan modulos sin tests. La metrica de cobertura existe pero no tiene consecuencias, por lo que es ignorada efectivamente.
- **Fix**: Agregar --cov-fail-under=40 a pytest.ini inmediatamente -- alcanzable con los tests existentes mas los de Prioridad 1. Aumentar progresivamente a 60% tras Prioridad 2, y a 80% como target final alineado con el README.
---

### FINDING-16-013: test_filter.py no cubre rama de _matches_language con base_url que contiene lenguaje
- **Severidad**: Minor
- **Archivo**: `tests/crawler/test_filter.py`, `src/crawler/filter.py` (lineas 135-148)
- **Descripcion**: Todos los tests de _matches_language usan firma de 2 argumentos sin base_url. La rama donde base_url tiene un pattern de lenguaje pero la URL evaluada no lo tiene (retorna False) nunca se ejecuta en tests.
- **Fix**: Agregar tests con tercer argumento base_url: URL sin lenguaje cuando base_url tiene lenguaje (debe retornar False), URL sin lenguaje cuando base_url tampoco tiene lenguaje (debe retornar True, permissive).

---

### FINDING-16-014: Tests de test_robots.py no cubren bug conocido de case-sensitivity
- **Severidad**: Minor
- **Archivo**: `tests/crawler/test_robots.py`, `src/crawler/robots.py`
- **Descripcion**: robots.py lowercasea paths al parsear (line.strip().lower()) almacenando /Private/ como /private/. is_allowed compara con el path real sin lowercase: el path /Private/data no comienza con /private/ -- URL bloqueada incorrectamente permitida. Tests existentes usan solo paths en minusculas, nunca revelando el bug.
- **Impacto**: En sistemas Linux (case-sensitive), paginas bloqueadas en robots.txt con paths en mayusculas seran scrapeadas incorrectamente. Es un problema real de produccion.
- **Fix**: Test con disallowed=[/private/] (post-lowercase del parser), verificar que is_allowed para URL con path en mayusculas retorna el comportamiento esperado (actualmente True -- bug). Documentar si el fix es: no lowercasear en _parse, o lowercasear tambien en is_allowed.

---

### FINDING-16-015: Tests de discovery asumen thresholds numericos que no existen en el codigo
- **Severidad**: Minor
- **Archivo**: `tests/crawler/test_discovery.py` (lineas 117-148)
- **Descripcion**: test_early_exit_with_large_sitemap (500 URLs) y test_skip_nav_if_sitemap_100_plus (100 URLs) asumen thresholds numericos. El codigo usa logica binaria: cualquier URL en all_urls salta la siguiente estrategia -- sin importar el count. Los tests pasan actualmente porque N > 0 pero testean una propiedad incorrecta sobre la implementacion.
- **Fix**: Renombrar tests a test_cascade_skips_nav_if_any_sitemap_url_found. Agregar test explicito: 1 sola URL en sitemap salta nav y crawl.
---

### FINDING-16-016: Sin markers unit e integration en ningun test existente
- **Severidad**: Minor
- **Archivo**: `tests/` (todos los archivos de test)
- **Descripcion**: pytest.ini define markers unit, integration, slow, y asyncio pero ningun test existente usa estos markers. pytest -m unit retorna 0 tests. pytest -m integration retorna 0 tests. Los 95 tests son un mix de unitarios puros, unitarios con mocks HTTP, y unitarios con mocks de funciones internas sin distincion automatizable.
- **Fix**: Marcar los 95 tests existentes: test_filter.py y test_robots.py con @pytest.mark.unit. Tests de discovery con solo mocks con @pytest.mark.unit. Tests futuros de Playwright con @pytest.mark.integration @pytest.mark.slow.

---

### FINDING-16-017: test_markdown_negotiation.py no cubre rama de respuesta proxy con contenido corto
- **Severidad**: Minor
- **Archivo**: `tests/scraper/test_markdown_negotiation.py`
- **Descripcion**: fetch_markdown_proxy en page.py retorna (None, None) si len(resp.text) <= 100. El test existente test_fetch_markdown_proxy_returns_content usa texto de 90+ chars que supera el threshold. No hay test para el caso de respuesta menor a 100 chars.
- **Fix**: Agregar test_fetch_markdown_proxy_returns_none_for_short_response con respuesta de 50 chars -- debe retornar (None, None).

---

### FINDING-16-018: Sin property-based testing con hypothesis para invariantes de funciones puras
- **Severidad**: Suggestion
- **Descripcion**: El proyecto no usa hypothesis. normalize_url, filter_urls, _url_to_filepath tienen invariantes bien definidos: idempotencia de normalize_url (normalize(normalize(url)) == normalize(url)), filter_urls retorna subconjunto del input, _url_to_filepath retorna path hijo de output_path.
- **Fix**: Agregar hypothesis a requirements-dev.txt. Tests @given(st.text()) para normalize_url verificando idempotencia y ausencia de excepciones no capturadas. @given(st.lists(st.text())) para filter_urls verificando que resultado es subconjunto del input.

---

### FINDING-16-019: Sin snapshot testing para verificar calidad del output de markdown
- **Severidad**: Suggestion
- **Descripcion**: Ningun test verifica el output final de markdown para HTMLs de entrada conocidos. Actualizaciones de markdownify o cambios en _pre_clean_markdown pueden silenciosamente degradar la calidad del output sin deteccion en CI.
- **Fix**: Crear directorio tests/fixtures/html/ con HTMLs de ejemplo representativos (pagina de docs con nav, footer, tablas, codigo). Crear tests/fixtures/expected_md/ con markdowns esperados. Tests parametrizados verificando html_to_markdown(fixture) == expected.

---

### FINDING-16-020: CI no cachea browsers de Playwright -- download de ~150MB en cada run
- **Severidad**: Suggestion
- **Archivo**: `.github/workflows/test.yml`
- **Descripcion**: El workflow instala playwright install chromium en cada ejecucion sin cache. Playwright descarga ~150MB de Chromium en cada run. Los tests actuales no requieren Playwright realmente (todo mockeado) pero cuando se agreguen tests de PageScraper o try_nav_parse el tiempo de CI aumentara significativamente.
- **Fix**: actions/cache@v5 para el directorio de cache de Playwright (~/.cache/ms-playwright/) con key basado en la version de playwright. Coordinar con Agente 17 (test-automator) que tiene el mismo finding identificado.

---

### FINDING-16-021: requirements.txt mezcla dependencias de produccion y testing
- **Severidad**: Suggestion
- **Archivo**: `requirements.txt`
- **Descripcion**: pytest>=7.4.0, pytest-asyncio>=0.21.0, y pytest-cov>=4.1.0 estan en el mismo requirements.txt que las dependencias de produccion. La imagen Docker de produccion incluye el framework de testing completo -- superficie de ataque adicional y tamano de imagen innecesario. Hallazgo ya identificado en Wave 2 desde perspectiva de infra.
- **Fix**: Separar en requirements.txt (produccion) y requirements-dev.txt (testing + linting). En CI usar pip install -r requirements-dev.txt. Coordinar con Agente 17 que tiene el mismo finding para alinear la implementacion.

---

### FINDING-16-022: TestIntegrationScenarios en test_discovery.py es nombre enganoso
- **Severidad**: Suggestion
- **Archivo**: `tests/crawler/test_discovery.py` (linea 336)
- **Descripcion**: La clase TestIntegrationScenarios contiene tests como test_nvidia_docs_scenario y test_js_heavy_site_falls_back_to_crawl que estan completamente mockeados -- no hay HTTP, no hay Playwright, no hay I/O real. El nombre Integration es incorrecto.
- **Fix**: Renombrar a TestRealisticScenarios o TestRealWorldPatterns. Reservar el nombre Integration para clases de test que realicen I/O real contra servicios reales o servidores en memoria.
---

## Plan de testing priorizado

El orden de prioridad maximiza la reduccion de riesgo por esfuerzo invertido, atacando primero los modulos criticos de seguridad y los gaps mas grandes.

### Prioridad 1: Semana 1 -- Tests de seguridad y API (maximo impacto, minimo esfuerzo)

**1.1 Tests de _url_to_filepath y _generate_index (FINDING-16-010)**
- Esfuerzo: ~1 hora
- Funciones puras sin dependencias externas, faciles de testear en aislamiento
- Confirma el bug de links rotos y establece test de regresion antes del fix
- Archivo sugerido: tests/jobs/test_runner_utils.py

**1.2 Tests de api/routes.py con FastAPI TestClient (FINDING-16-001)**
- Esfuerzo: ~4-6 horas
- FastAPI TestClient con JobManager mockeado
- Cubrir: 404 para job inexistente, 422 para payload invalido, 200 para job creado, health endpoint con Ollama mockeado
- Archivo sugerido: tests/api/test_routes.py

**1.3 Configurar --cov-fail-under=40 en pytest.ini (FINDING-16-012)**
- Esfuerzo: 5 minutos
- Enforcement inmediato de cobertura minima sin escribir tests adicionales

### Prioridad 2: Semana 2 -- Modulos LLM (FINDING-16-005)

**2.1 Tests de llm/client.py**
- Esfuerzo: ~3 horas
- get_provider_for_model con todos los casos edge incluyendo namespace incorrecto
- generate dispatcher con mock de los tres _generate_* internos
- _get_openrouter_models sincrona: confirmar que bloquea el event loop

**2.2 Tests de llm/cleanup.py**
- Esfuerzo: ~2 horas
- needs_llm_cleanup: 5 ramas bien definidas, funcion pura, sin mocks necesarios
- cleanup_markdown: mockear generate, verificar exactamente 2 intentos antes del fallback (confirmar discrepancia con documentacion que dice max 3 intentos)

**2.3 Tests de llm/filter.py**
- Esfuerzo: ~1.5 horas
- filter_urls_with_llm: respuesta JSON valida, con code blocks markdown, JSON invalido (fallback al original), exception (fallback al original)

### Prioridad 3: Semana 3 -- Jobs y concurrencia

**3.1 Tests de jobs/manager.py (FINDING-16-003)**
- Esfuerzo: ~4 horas
- Job.event_stream: path normal, timeout con task muerto, GeneratorExit
- JobManager.cancel_job: job existente y job inexistente (retorna None)
- Test de cancelacion completo: crear job, cancelar, verificar estado y evento SSE

**3.2 Tests de funciones auxiliares de jobs/runner.py (FINDING-16-002)**
- Esfuerzo: ~3 horas
- validate_models: mockear get_available_models, casos: modelo encontrado, no encontrado, provider sin API key
- _generate_index: confirmar bug de links con test que falla, luego escribir el fix y verificar que el test pasa

### Prioridad 4: Semana 4 -- Scraper y mejoras a discovery

**4.1 Tests de scraper/markdown.py (FINDING-16-007)**
- Esfuerzo: ~3 horas
- _pre_clean_markdown con 5 tipos de noise distintos
- chunk_markdown multi-chunk con heading boundary y medicion de CHUNK_OVERLAP

**4.2 Mejoras a tests de crawler/discovery.py (FINDING-16-006)**
- Esfuerzo: ~4 horas
- try_sitemap con httpx.MockTransport usando fixtures XML de conftest.py
- Correccion de tests con thresholds incorrectos (FINDING-16-015)
---

## Estadisticas

- **Total hallazgos**: 22
- **Critical**: 5 (FINDING-16-001 a 16-005)
- **Major**: 7 (FINDING-16-006 a 16-012)
- **Minor**: 5 (FINDING-16-013 a 16-017)
- **Suggestion**: 5 (FINDING-16-018 a 16-022)

### Distribucion de tests existentes

| Archivo de test | Cantidad de tests | Tipo predominante |
|----------------|-------------------|------------------|
| tests/crawler/test_discovery.py | 27 | Unitario -- coordinator con mocks de estrategias |
| tests/crawler/test_filter.py | 37 | Unitario puro (mejor cobertura del proyecto) |
| tests/crawler/test_robots.py | 26 | Unitario puro (buena calidad) |
| tests/scraper/test_markdown_negotiation.py | 5 | Unitario con mocks HTTP |
| **Total** | **95** | |

### Modulos sin tests ordenados por LOC

| Modulo | LOC | Prioridad de testing |
|--------|-----|---------------------|
| jobs/runner.py | 591 | P1 (utils), P3 (funciones aux), P5 (run_job completo) |
| crawler/discovery.py | 571 | P4 (mejora internals) |
| llm/client.py | 312 | P2 |
| api/routes.py | 230 | P1 |
| scraper/page.py (PageScraper Playwright) | 166 | P4 |
| scraper/markdown.py | 129 | P4 |
| llm/cleanup.py | 124 | P2 |
| jobs/manager.py | 117 | P3 |
| exceptions.py | 88 | P5 (bajo impacto) |
| llm/filter.py | 67 | P2 |
| api/models.py | 41 | P5 (trivial) |
| main.py | 27 | P5 (trivial) |

### Proyeccion de cobertura por prioridad completada

| Estado | Cobertura estimada |
|--------|-------------------|
| Actual | 12-18% |
| P1 completada | 30-35% |
| P2 completada | 50-55% |
| P3 completada | 65-70% |
| P4 completada | 78-82% |

**Esfuerzo total estimado: 32-35 horas de desarrollo de tests para alcanzar el objetivo de 80% de cobertura.**
