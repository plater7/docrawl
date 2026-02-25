# Wave 4 — Agente 17: Test Automator

## Resumen ejecutivo

La infraestructura de testing de Docrawl está en un estado **críticamente insuficiente** para producción. Existen 95 tests que pasan correctamente, pero cubren únicamente el **20% del código total** (medido en ejecución real). Los módulos más críticos para la seguridad — `runner.py`, `manager.py`, `llm/client.py`, `api/routes.py` — tienen **0% de cobertura**. Los security gates (Bandit, pip-audit) corren con `|| true`, haciendo que fallen silenciosamente sin bloquear el pipeline. No hay paralelización de tests, no hay threshold de coverage, no hay mocking de Ollama ni Playwright a nivel de integración, y no hay tests de API, jobs, ni LLM.

El riesgo principal no es que los tests fallen — es que la suite actual da una **falsa sensación de seguridad**: 95 tests verdes con 20% de cobertura real, mientras que los flujos de producción más complejos (orquestación de jobs, paths de seguridad SSRF/path traversal confirmados en Wave 1) no tienen ningún test.

---

## Estado del CI/CD pipeline

### Workflows activos

| Workflow | Trigger | Estado |
|----------|---------|--------|
| `test.yml` | push/PR a main | Activo, matrix Python 3.11+3.12 |
| `lint.yml` | push/PR a main | Activo, ruff + mypy |
| `security.yml` | push/PR + semanal | Activo pero gates inoperantes |
| `docker-build.yml` | push/PR a main | Activo, solo build sin smoke test |
| `release.yml` | push de tags v* | Activo |

### Problemas principales identificados

1. **Security gates con `|| true`**: Bandit y pip-audit no pueden fallar el pipeline en ningún caso. Los findings críticos de Wave 1 (CVSS 9.1) no serían detectados por CI aunque Bandit los marque.

2. **Playwright instalado pero subutilizado**: El workflow instala Chromium en CI (sin caché de browsers), lo que tarda 3-5 minutos adicionales por run, pero no hay un solo test que use Playwright real. Todo está mockeado — la instalación es innecesaria hasta que se escriban integration tests con browser.

3. **Sin cobertura mínima**: No hay `--cov-fail-under` en `pytest.ini` ni en el workflow. Un PR puede bajar la cobertura del 20% al 0% sin que CI falle.

4. **Sin test del container Docker**: `docker-build.yml` solo hace `docker build` sin ejecutar ningún smoke test dentro del container. El `HEALTHCHECK` del Dockerfile apunta a `/api/health/ready` pero nunca se verifica en CI.

5. **Codecov configurado con `fail_ci_if_error: false`**: Si Codecov falla (token ausente, servicio caído), el pipeline continúa sin reportar cobertura. El token `CODECOV_TOKEN` puede no estar configurado en el repo.

---

## Hallazgos

### FINDING-17-001: Cobertura total del 20% — módulos críticos al 0%
- **Severidad**: Critical
- **Archivo**: Medición global via `pytest --cov=src`
- **Descripción**: La cobertura real de la suite es 20% (964 líneas sin cubrir de 1209 totales). Los módulos con 0% de cobertura incluyen exactamente los que contienen las vulnerabilidades críticas confirmadas en Wave 1:
  - `src/jobs/runner.py` — 0% (234 líneas) — orquestación completa del job, path traversal via `output_path`, `_url_to_filepath`
  - `src/jobs/manager.py` — 0% (67 líneas) — gestión de estado de jobs
  - `src/llm/client.py` — 0% (128 líneas) — cliente HTTP a Ollama/OpenRouter, SSRF potencial
  - `src/llm/cleanup.py` — 0% (49 líneas)
  - `src/llm/filter.py` — 0% (26 líneas)
  - `src/api/routes.py` — 0% (105 líneas) — todos los endpoints REST
  - `src/api/models.py` — 0% (27 líneas) — validación Pydantic
  - `src/main.py` — 0% (12 líneas)
  - `src/exceptions.py` — 0% (34 líneas)
- **Impacto**: La vulnerabilidad de path traversal en `runner.py:_url_to_filepath` (CVSS 9.1, confirmada en Wave 1) no tiene ningún test. Un fix incorrecto de esa función no sería detectado por la suite. El flujo completo de un job de producción no tiene cobertura.
- **Fix**:
  ```ini
  # pytest.ini — agregar threshold
  addopts =
      --verbose
      --color=yes
      --cov=src
      --cov-report=term-missing
      --cov-report=html
      --cov-branch
      --cov-fail-under=60
      -ra
  ```
  Y priorizar tests para `runner.py`, `manager.py`, `api/routes.py`, `llm/client.py`.

---

### FINDING-17-002: Security gates con `|| true` — falla silenciosa garantizada
- **Severidad**: Critical
- **Archivo**: `.github/workflows/security.yml:29,33,36`
- **Descripción**: Las tres invocaciones de herramientas de seguridad terminan con `|| true`, lo que garantiza que el step siempre reportará éxito independientemente del resultado:
  ```yaml
  # Línea 29 — genera el report pero nunca falla
  - name: Bandit security scan
    run: bandit -r src/ -f json -o bandit-report.json || true

  # Línea 33 — muestra en pantalla pero nunca falla
  - name: Bandit summary
    if: always()
    run: bandit -r src/ -f screen || true

  # Línea 36 — pip-audit nunca puede bloquear el pipeline
  - name: pip-audit dependency check
    run: pip-audit --strict || true
  ```
- **Impacto**: Los hallazgos críticos de seguridad identificados en Wave 1 (path traversal CVSS 9.1, SSRF CVSS 9.1) que Bandit puede detectar parcialmente (B602, B603, B310 para subprocess/requests a URLs arbitrarias) nunca bloquearán un PR. Un atacante que logre un PR malicioso con vulnerabilidades nuevas no será detenido por el security workflow. pip-audit podría detectar dependencias con CVEs conocidos y tampoco bloquearía el pipeline.
- **Fix**:
  ```yaml
  # Enfoque recomendado: separar severity levels
  - name: Bandit security scan (high severity — blocks pipeline)
    run: bandit -r src/ -f json -o bandit-report.json --severity-level high --exit-zero

  - name: Bandit fail on critical
    run: |
      HIGH=$(python -c "import json; d=json.load(open('bandit-report.json')); print(len([r for r in d['results'] if r['issue_severity'] == 'HIGH']))")
      if [ "$HIGH" -gt "0" ]; then
        echo "Found $HIGH HIGH severity issues — blocking pipeline"
        bandit -r src/ -f screen --severity-level high
        exit 1
      fi

  - name: pip-audit dependency check
    run: pip-audit --strict
    # Remover || true — las vulnerabilidades en dependencias deben bloquear
  ```

---

### FINDING-17-003: Playwright instalado en CI sin ningún test que lo use
- **Severidad**: Major
- **Archivo**: `.github/workflows/test.yml:39-41`
- **Descripción**: El workflow instala Playwright y Chromium en cada run:
  ```yaml
  - name: Install Playwright browsers
    run: |
      playwright install chromium
      playwright install-deps chromium
  ```
  Sin embargo, ningún test en la suite usa Playwright real. `PageScraper` está completamente sin tests (`src/scraper/page.py` tiene 43% de cobertura solo por los tests de `fetch_markdown_native` y `fetch_markdown_proxy` que mockean `httpx.AsyncClient`, no Playwright). Chromium pesa aproximadamente 150 MB y su instalación tarda 3-5 minutos en runners Ubuntu sin caché.
- **Impacto**: Cada run del test workflow desperdicia 3-5 minutos y consume bandwidth/storage de GitHub Actions sin aportar valor de testing. Con matrix de 2 versiones Python, son 6-10 minutos desperdiciados por run. Adicionalmente, los browsers de Playwright no están cacheados (no hay step de caché para `~/.cache/ms-playwright`), por lo que se reinstalan íntegramente en cada run.
- **Fix**:
  ```yaml
  # Opción A: Eliminar instalación hasta que existan integration tests con browser
  # Comentar o eliminar el step "Install Playwright browsers"

  # Opción B: Si se agregan tests con browser, cachear correctamente
  - name: Cache Playwright browsers
    uses: actions/cache@v5
    with:
      path: ~/.cache/ms-playwright
      key: ${{ runner.os }}-playwright-${{ hashFiles('requirements.txt') }}
      restore-keys: |
        ${{ runner.os }}-playwright-

  - name: Install Playwright browsers
    run: playwright install chromium
    # Solo si el cache no fue hit
  ```

---

### FINDING-17-004: Sin threshold de cobertura — regresión silenciosa posible
- **Severidad**: Major
- **Archivo**: `pytest.ini:9-16`
- **Descripción**: `pytest.ini` genera reportes de cobertura (`--cov-report=term-missing`, `--cov-report=html`, `--cov-branch`) pero no define `--cov-fail-under`. Un PR puede eliminar tests existentes o agregar código sin tests y el pipeline seguirá verde. El README menciona "Target: 80%+ code coverage" pero esto no está enforcement de ninguna manera. La cobertura actual es 20%, significativamente por debajo del objetivo declarado.
- **Impacto**: La cobertura puede degradarse progresivamente sin que ningún sistema lo detecte. El objetivo del 80% documentado en `tests/README.md` es meramente aspiracional y no tiene mecanismo de enforcement.
- **Fix**:
  ```ini
  # pytest.ini
  addopts =
      --verbose
      --color=yes
      --cov=src
      --cov-report=term-missing
      --cov-report=html
      --cov-report=xml
      --cov-branch
      --cov-fail-under=60
      -ra
  ```
  Nota: El threshold recomendado de 60% es alcanzable en el corto plazo dado el estado actual. Subir a 80% conforme se agregan tests.

---

### FINDING-17-005: Sin tests de API — todos los endpoints sin cobertura
- **Severidad**: Major
- **Archivo**: `src/api/routes.py` — 0% cobertura
- **Descripción**: No existe ningún test para los endpoints FastAPI:
  - `POST /api/jobs` — sin test de validación de payload, sin test de path traversal via `output_path`
  - `GET /api/jobs/{id}/events` — sin test del SSE stream
  - `POST /api/jobs/{id}/cancel` — sin test
  - `GET /api/jobs/{id}/status` — sin test
  - `GET /api/models` — sin test
  - `GET /api/health/ready` — sin test (crítico: es el HEALTHCHECK del container)

  FastAPI provee `TestClient` y `httpx.AsyncClient` para testing in-process que no requieren servidor real.
- **Impacto**: Ningún cambio en los endpoints es verificado. La validación de `output_path` en `JobRequest` (punto de entrada del path traversal confirmado en Wave 1) no tiene test. El endpoint de health que el Dockerfile usa como HEALTHCHECK no está verificado. Si una refactorización rompe la API, los tests actuales no lo detectarán.
- **Fix**:
  ```python
  # tests/api/test_routes.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from unittest.mock import patch, AsyncMock
  from src.main import app

  @pytest.mark.asyncio
  async def test_create_job_rejects_path_traversal():
      """output_path with path traversal should be rejected."""
      async with AsyncClient(
          transport=ASGITransport(app=app), base_url="http://test"
      ) as client:
          response = await client.post("/api/jobs", json={
              "url": "https://docs.example.com",
              "crawl_model": "mistral:7b",
              "pipeline_model": "qwen3:14b",
              "reasoning_model": "deepseek-r1:32b",
              "output_path": "/data/../../../etc/passwd",
              "delay_ms": 500,
              "max_concurrent": 3,
          })
          assert response.status_code == 422  # Validation error

  @pytest.mark.asyncio
  async def test_health_ready_endpoint():
      """Health endpoint should return ready status."""
      async with AsyncClient(
          transport=ASGITransport(app=app), base_url="http://test"
      ) as client:
          response = await client.get("/api/health/ready")
          assert response.status_code == 200
          data = response.json()
          assert "ready" in data
          assert "checks" in data
  ```

---

### FINDING-17-006: Sin mocking de Ollama — tests de LLM hacen requests reales o no existen
- **Severidad**: Major
- **Archivo**: `src/llm/` — 0% cobertura total
- **Descripción**: No existe ningún test para `src/llm/client.py`, `src/llm/cleanup.py`, ni `src/llm/filter.py`. Estos módulos contienen la lógica de comunicación con Ollama/OpenRouter/OpenCode. No hay:
  - Tests para `generate()` con mocking de httpx
  - Tests para `cleanup_markdown()` — comportamiento con timeout, retry, contexto excedido
  - Tests para `filter_urls_with_llm()` — parsing de respuesta LLM, fallback cuando falla
  - Tests para `get_available_models()` con diferentes providers
  - Tests para `needs_llm_cleanup()` — función de decisión crítica para el pipeline

  `httpx` ya está instalado como dependencia, y `respx` (o `unittest.mock`) sería suficiente para mockear las respuestas HTTP.
- **Impacto**: Cambios en los prompts o en el parsing de respuestas LLM no tienen tests de regresión. El comportamiento de fallback cuando Ollama falla (documentado en CLAUDE.md: "Si un chunk falla: retry con backoff exponencial, max 3 intentos") no está verificado.
- **Fix**:
  ```python
  # tests/llm/test_client.py
  import pytest
  from unittest.mock import patch, AsyncMock
  import httpx
  from src.llm.client import generate, get_available_models

  @pytest.mark.asyncio
  async def test_generate_ollama_success():
      mock_response = AsyncMock()
      mock_response.status_code = 200
      mock_response.json.return_value = {"response": "cleaned markdown"}
      mock_response.raise_for_status = lambda: None

      with patch("src.llm.client.httpx.AsyncClient") as MockClient:
          client_inst = AsyncMock()
          client_inst.post.return_value = mock_response
          client_inst.__aenter__ = AsyncMock(return_value=client_inst)
          client_inst.__aexit__ = AsyncMock(return_value=False)
          MockClient.return_value = client_inst

          result = await generate("mistral:7b", "test prompt")
          assert result == "cleaned markdown"

  @pytest.mark.asyncio
  async def test_generate_ollama_timeout_raises():
      with patch("src.llm.client.httpx.AsyncClient") as MockClient:
          client_inst = AsyncMock()
          client_inst.post.side_effect = httpx.TimeoutException("timeout")
          client_inst.__aenter__ = AsyncMock(return_value=client_inst)
          client_inst.__aexit__ = AsyncMock(return_value=False)
          MockClient.return_value = client_inst

          with pytest.raises(httpx.TimeoutException):
              await generate("mistral:7b", "test prompt", timeout=5)
  ```

---

### FINDING-17-007: `conftest.py` con `event_loop` deprecado — compatibilidad rota en pytest-asyncio >= 0.21
- **Severidad**: Major
- **Archivo**: `tests/conftest.py:10-15`
- **Descripción**: El fixture `event_loop` en `conftest.py` usa el patrón deprecado:
  ```python
  @pytest.fixture(scope="session")
  def event_loop() -> Generator:
      """Create an instance of the default event loop for the test session."""
      loop = asyncio.get_event_loop_policy().new_event_loop()
      yield loop
      loop.close()
  ```
  En pytest-asyncio >= 0.21, override del `event_loop` fixture con scope `session` genera un `DeprecationWarning` que en versiones futuras será un error. La forma correcta desde pytest-asyncio 0.23+ es usar `@pytest_asyncio.fixture` o configurar `asyncio_mode = auto` con `asyncio_default_fixture_loop_scope`. Adicionalmente, el `return type` está anotado como `Generator` cuando debería ser `Generator[asyncio.AbstractEventLoop, None, None]`.

  En la ejecución actual, pytest reporta: `asyncio_default_fixture_loop_scope=None` (warning en la salida de test collection).
- **Impacto**: En versiones futuras de pytest-asyncio, el fixture romperá. Los tests que dependen del event loop de sesión pueden tener comportamiento no determinístico cuando se ejecuten en paralelo.
- **Fix**:
  ```python
  # tests/conftest.py — reemplazar el fixture deprecado
  # Con asyncio_mode = auto en pytest.ini, no se necesita override manual
  # Eliminar el fixture event_loop completo, o usar:

  import pytest_asyncio

  @pytest_asyncio.fixture(scope="session")
  async def shared_session_resource():
      """Example: shared async resource for session scope."""
      # Solo si se necesita algo session-scoped real
      yield

  # Agregar a pytest.ini:
  # asyncio_default_fixture_loop_scope = session
  ```

---

### FINDING-17-008: Sin paralelización de tests — tiempo de CI no optimizado
- **Severidad**: Minor
- **Archivo**: `requirements.txt`, `pytest.ini`
- **Descripción**: `pytest-xdist` no está instalado ni en `requirements.txt` ni en ningún requirements-dev separado. Los 95 tests actuales son todos unitarios con mocks y corren en 1.06 segundos en total (verificado), por lo que la paralelización no es crítica hoy. Sin embargo, conforme se agreguen integration tests (que incluyan setup/teardown de browser, llamadas mockeadas más complejas), el tiempo crecerá. No hay `requirements-dev.txt` separado de `requirements.txt` — las dependencias de test (`pytest`, `pytest-asyncio`, `pytest-cov`) están mezcladas con dependencias de producción.
- **Impacto**: Las dependencias de test se instalan en la imagen Docker de producción (actualmente `requirements.txt` incluye `pytest`, `pytest-asyncio`, `pytest-cov`). Esto aumenta el tamaño de la imagen y la superficie de ataque.
- **Fix**:
  ```
  # requirements.txt (solo producción)
  fastapi>=0.109.0
  uvicorn[standard]>=0.27.0
  playwright>=1.41.0
  markdownify>=0.11.6
  httpx>=0.26.0
  pydantic>=2.5.0
  sse-starlette>=1.8.0
  beautifulsoup4>=4.12.0

  # requirements-dev.txt (testing y desarrollo)
  -r requirements.txt
  pytest>=7.4.0
  pytest-asyncio>=0.21.0
  pytest-cov>=4.1.0
  pytest-xdist>=3.5.0
  pytest-timeout>=2.2.0
  respx>=0.21.0
  hypothesis>=6.100.0
  ```

  Y en el Dockerfile:
  ```dockerfile
  # Solo instalar requirements.txt (sin -dev)
  RUN pip install --no-cache-dir -r requirements.txt
  ```

---

### FINDING-17-009: Sin pytest-timeout — tests async pueden colgarse indefinidamente
- **Severidad**: Minor
- **Archivo**: `pytest.ini`, `requirements.txt`
- **Descripción**: No hay `pytest-timeout` instalado ni configurado. Los tests async que mockean incorrectamente un `AsyncMock` pueden colgar indefinidamente si el mock no cierra correctamente un `async with` o si el event loop queda esperando. Sin timeout global, un test colgado bloqueará el CI runner hasta que GitHub Actions lo mate por timeout de job (6 horas por defecto), desperdiciando todos los minutos de Actions.

  En el contexto actual, los tests de robots (`test_load_timeout`) simulan timeouts de httpx pero no tienen un timeout de pytest que garantice que el test mismo no se cuelgue si el mock falla.
- **Impacto**: Un test mal escrito puede bloquear el CI por horas. En particular, futuros tests que usen Playwright real son especialmente susceptibles a colgarse.
- **Fix**:
  ```ini
  # pytest.ini
  [pytest]
  timeout = 30
  timeout_method = thread

  addopts =
      --verbose
      --color=yes
      --cov=src
      --cov-report=term-missing
      --cov-report=html
      --cov-branch
      --cov-fail-under=60
      --timeout=30
      -ra
  ```

---

### FINDING-17-010: Sin tests de `_url_to_filepath` — función con path traversal no testeada
- **Severidad**: Critical
- **Archivo**: `src/jobs/runner.py:557-576`
- **Descripción**: La función `_url_to_filepath` convierte una URL a un path de archivo en disco y es el vector del path traversal confirmado en Wave 1 (CVSS 9.1). La función no tiene ningún test:
  ```python
  def _url_to_filepath(url: str, base_url: str, output_path: Path) -> Path:
      """Convert URL to file path, preserving structure."""
      parsed = urlparse(url)
      base_parsed = urlparse(base_url)
      path = parsed.path
      base_path = base_parsed.path.rstrip("/")
      if path.startswith(base_path):
          path = path[len(base_path):]
      path = path.strip("/")
      if not path:
          path = "index"
      if "." in path.split("/")[-1]:
          path = path.rsplit(".", 1)[0]
      return output_path / f"{path}.md"
  ```
  Esta función no verifica que el path resultante permanezca dentro de `output_path`. Una URL como `https://example.com/../../../etc/passwd` podría generar un path fuera del directorio de output.
- **Impacto**: Sin tests, cualquier fix de seguridad para el path traversal no tiene test de regresión. El fix podría ser incorrecto o podría romperse en un refactor futuro sin que la suite lo detecte.
- **Fix**:
  ```python
  # tests/jobs/test_runner.py
  import pytest
  from pathlib import Path
  from src.jobs.runner import _url_to_filepath

  class TestUrlToFilepath:
      def test_basic_url_to_path(self, tmp_path):
          result = _url_to_filepath(
              "https://docs.example.com/guide/install",
              "https://docs.example.com/",
              tmp_path
          )
          assert result == tmp_path / "guide/install.md"
          # Verify path stays within output_path
          assert tmp_path in result.parents

      def test_path_traversal_via_url_is_contained(self, tmp_path):
          """URL with path traversal segments must not escape output_path."""
          result = _url_to_filepath(
              "https://example.com/../../../etc/passwd",
              "https://example.com/",
              tmp_path
          )
          # Result must be inside tmp_path
          assert str(result).startswith(str(tmp_path))

      def test_root_url_becomes_index(self, tmp_path):
          result = _url_to_filepath(
              "https://example.com/",
              "https://example.com/",
              tmp_path
          )
          assert result == tmp_path / "index.md"

      def test_url_with_extension_strips_it(self, tmp_path):
          result = _url_to_filepath(
              "https://example.com/page.html",
              "https://example.com/",
              tmp_path
          )
          assert result == tmp_path / "page.md"
  ```

---

### FINDING-17-011: Sin tests de `chunk_markdown` con casos límite críticos
- **Severidad**: Minor
- **Archivo**: `src/scraper/markdown.py` — 40% cobertura
- **Descripción**: `test_markdown_negotiation.py` incluye un solo test de `chunk_markdown` (`test_chunk_markdown_uses_native_token_count`) que solo verifica el path trivial (texto pequeño con token count). No hay tests para:
  - Texto exactamente igual a `DEFAULT_CHUNK_SIZE` (16000 chars) — boundary condition
  - Texto que requiere split por heading boundary
  - Texto que requiere split por paragraph boundary
  - Texto con `CHUNK_OVERLAP = 200` — verificar que chunks se solapan correctamente
  - Texto inferior a 50 chars — verificar que retorna lista vacía o el texto
  - `_pre_clean_markdown` — 0% cobertura de la función de limpieza
  - Bloques CSS/JS con `{` y `}` — lógica `in_noise_block`

  `_pre_clean_markdown` está completamente sin tests a pesar de tener lógica de estado (`in_noise_block`) que es propensa a bugs.
- **Impacto**: Cambios en la lógica de chunking o limpieza no tienen regresión. Un bug en `_pre_clean_markdown` que elimine contenido válido no sería detectado.
- **Fix**: Agregar tests paramétricos para los casos límite de chunking y tests dedicados para `_pre_clean_markdown` con muestras de HTML real de frameworks como Next.js.

---

### FINDING-17-012: Markers declarados pero no usados en ningún test
- **Severidad**: Minor
- **Archivo**: `pytest.ini:19-23`, todos los archivos de test
- **Descripción**: `pytest.ini` declara los markers `unit`, `integration`, `slow`, `asyncio`. Sin embargo, ningún test en la suite usa `@pytest.mark.unit`, `@pytest.mark.integration`, ni `@pytest.mark.slow`. Los tests async sí tienen `@pytest.mark.asyncio` en muchos casos (aunque con `asyncio_mode = auto` no es estrictamente necesario). Los markers no usados:
  - Imposibilitan ejecutar `pytest -m unit` (retorna 0 tests)
  - Imposibilitan excluir `pytest -m "not slow"` en pipelines de fast-feedback
  - La documentación en `tests/README.md` menciona `pytest -m unit` como un comando válido, pero no funciona
- **Impacto**: Los markers son infraestructura muerta. Cuando se agreguen integration tests lentos (con Playwright real, o con Docker), no habrá forma de separarlos de los unit tests rápidos sin refactoring adicional.
- **Fix**: Aplicar markers inmediatamente a los tests existentes:
  ```python
  # tests/crawler/test_filter.py
  @pytest.mark.unit
  class TestFilterUrls:
      ...

  # tests/crawler/test_discovery.py — tests con mocks son unit
  @pytest.mark.unit
  class TestNormalizeUrl:
      ...

  # Futuros integration tests
  @pytest.mark.integration
  @pytest.mark.slow
  class TestWithRealBrowser:
      ...
  ```

---

### FINDING-17-013: Sin tests de `jobs/manager.py` — estado de jobs sin verificación
- **Severidad**: Major
- **Archivo**: `src/jobs/manager.py` — 0% cobertura
- **Descripción**: `JobManager` gestiona el ciclo de vida de todos los jobs (creación, cancelación, lookup por ID, event streaming). Tiene 0% de cobertura. No hay tests para:
  - Creación de job y asignación de UUID
  - Lookup de job inexistente (retorna `None`)
  - Cancelación de job en estado `running` vs `completed`
  - `event_stream()` — el generador async que alimenta el SSE endpoint
  - Múltiples jobs concurrentes
  - Job con ID duplicado (si es posible)
- **Impacto**: El sistema de gestión de estado de jobs es untested. Una regresión en `cancel_job` podría dejar jobs corriendo indefinidamente sin que los tests lo detecten.

---

### FINDING-17-014: Docker build sin smoke test del container
- **Severidad**: Minor
- **Archivo**: `.github/workflows/docker-build.yml`
- **Descripción**: El workflow solo ejecuta `docker build` sin verificar que el container arranca correctamente ni que la API responde. El Dockerfile tiene un `HEALTHCHECK` que apunta a `/api/health/ready`, pero nunca se verifica en CI:
  ```yaml
  - name: Build Docker image (no push)
    uses: docker/build-push-action@v6
    with:
      context: .
      file: docker/Dockerfile
      push: false
      tags: docrawl:test
      cache-from: type=gha
      cache-to: type=gha,mode=max
      # No hay step de smoke test después
  ```
- **Impacto**: Un cambio que rompe el startup de la aplicación (import error, puerto incorrecto, missing env var) no sería detectado por CI hasta que se deploye el container.
- **Fix**:
  ```yaml
  - name: Smoke test Docker container
    run: |
      docker run -d --name docrawl-test -p 8002:8002 \
        -e OLLAMA_URL=http://localhost:11434 \
        docrawl:test
      # Esperar startup
      sleep 10
      # Verificar que la API responde (health no depende de Ollama estar up)
      curl -f http://localhost:8002/ || exit 1
      docker stop docrawl-test
      docker rm docrawl-test
  ```

---

### FINDING-17-015: Sin property-based testing — hypothesis ausente
- **Severidad**: Suggestion
- **Archivo**: `requirements.txt`
- **Descripción**: `hypothesis` no está instalado. Las funciones candidatas para property-based testing en este codebase son exactamente las que tienen más bugs potenciales:
  - `normalize_url(url)` — debe ser idempotente: `normalize_url(normalize_url(url)) == normalize_url(url)`. Con Hypothesis, se pueden generar miles de URLs aleatorias para verificar esta propiedad.
  - `chunk_markdown(text, chunk_size)` — las invariantes son: la concatenación de chunks debe recuperar el texto original (modulo overlap), ningún chunk debe exceder `chunk_size`, los chunks no deben estar vacíos.
  - `filter_urls(urls, base_url)` — debe ser idempotente aplicado dos veces: `filter_urls(filter_urls(urls, base), base) == filter_urls(urls, base)`.
  - `_url_to_filepath(url, base_url, output_path)` — la invariante de seguridad crítica: el resultado siempre debe estar dentro de `output_path`.
- **Fix**:
  ```python
  # tests/crawler/test_discovery_property.py
  from hypothesis import given, strategies as st
  from src.crawler.discovery import normalize_url

  @given(st.from_regex(
      r"https?://[a-z0-9\-\.]+/[a-zA-Z0-9/\-_\.]*(\?[^#]*)?(#.*)?",
      fullmatch=True
  ))
  def test_normalize_url_is_idempotent(url):
      """normalize_url applied twice must equal applied once."""
      once = normalize_url(url)
      twice = normalize_url(once)
      assert once == twice

  # tests/jobs/test_runner_property.py
  from hypothesis import given, settings, strategies as st
  from pathlib import Path
  from src.jobs.runner import _url_to_filepath

  @given(
      path_segment=st.text(
          alphabet="abcdefghijklmnopqrstuvwxyz/._-",
          min_size=1, max_size=100
      )
  )
  def test_url_to_filepath_never_escapes_output_path(tmp_path, path_segment):
      """Generated filepath must always be inside output_path."""
      url = f"https://example.com/{path_segment}"
      result = _url_to_filepath(url, "https://example.com/", tmp_path)
      assert str(result).startswith(str(tmp_path))
  ```

---

## Configuración recomendada

### pytest.ini mejorado

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function

# Timeout global para prevenir tests colgados
timeout = 30
timeout_method = thread

# Coverage settings con threshold
addopts =
    --verbose
    --color=yes
    --cov=src
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
    --cov-branch
    --cov-fail-under=60
    --timeout=30
    -ra

# Markers
markers =
    unit: Fast unit tests with no external dependencies (mocked)
    integration: Integration tests that may use browser or real services
    slow: Tests that take more than 5 seconds to run
    security: Tests that verify security properties (path traversal, SSRF, etc.)

# Ignore patterns
norecursedirs = .git .cache __pycache__ data docker htmlcov
```

### requirements-dev.txt recomendado

```
# Install with: pip install -r requirements-dev.txt
-r requirements.txt

# Testing framework
pytest>=7.4.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
pytest-timeout>=2.2.0
pytest-xdist>=3.5.0

# HTTP mocking (para LLM client y robots parser)
respx>=0.21.0

# Property-based testing
hypothesis>=6.100.0

# Security testing tools
bandit>=1.7.0
pip-audit>=2.7.0
```

### .github/workflows/test.yml mejorado

```yaml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v6
      with:
        python-version: ${{ matrix.python-version }}

    - name: Cache pip packages
      uses: actions/cache@v5
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-dev-${{ hashFiles('requirements-dev.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-dev-
          ${{ runner.os }}-pip-

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt

    # Solo instalar Playwright si hay tests que lo necesiten
    # (Actualmente no hay, comentar hasta que se agreguen integration tests)
    # - name: Cache Playwright browsers
    #   uses: actions/cache@v5
    #   with:
    #     path: ~/.cache/ms-playwright
    #     key: ${{ runner.os }}-playwright-${{ hashFiles('requirements.txt') }}
    # - name: Install Playwright browsers
    #   run: playwright install chromium

    - name: Run unit tests with coverage
      run: |
        pytest -m "not slow and not integration" \
          --cov=src \
          --cov-report=xml \
          --cov-report=term-missing \
          --cov-fail-under=60

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        token: ${{ secrets.CODECOV_TOKEN }}
        file: ./coverage.xml
        fail_ci_if_error: true  # Cambiar a true — si Codecov falla, quiero saberlo
        verbose: true

    - name: Test Summary
      if: always()
      run: |
        echo "## Test Results" >> $GITHUB_STEP_SUMMARY
        echo "Python version: ${{ matrix.python-version }}" >> $GITHUB_STEP_SUMMARY
        echo "Tests completed. See logs for details." >> $GITHUB_STEP_SUMMARY
```

### .github/workflows/security.yml corregido

```yaml
name: Security

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install security tools
        run: |
          python -m pip install --upgrade pip
          pip install bandit pip-audit
          pip install -r requirements.txt

      - name: Bandit security scan (generate report)
        run: bandit -r src/ -f json -o bandit-report.json -l -i || true
        # -l: low severity only en report, -i: info level
        # || true: para que genere el artifact aunque haya findings

      - name: Bandit summary to screen
        if: always()
        run: bandit -r src/ -f screen || true

      - name: Bandit fail on HIGH severity
        # Este step SÍ puede fallar — bloquea el pipeline en HIGH+
        run: |
          HIGH_COUNT=$(python -c "
          import json, sys
          try:
              with open('bandit-report.json') as f:
                  data = json.load(f)
              high = [r for r in data.get('results', []) if r['issue_severity'] == 'HIGH']
              print(len(high))
          except Exception:
              print(0)
          ")
          echo "HIGH severity findings: $HIGH_COUNT"
          if [ "$HIGH_COUNT" -gt "0" ]; then
            echo "Pipeline blocked: $HIGH_COUNT HIGH severity security findings"
            exit 1
          fi

      - name: pip-audit dependency check
        # Este step SÍ puede fallar — las CVEs en dependencias son bloqueantes
        run: pip-audit --strict

      - name: Upload Bandit report
        if: always()
        uses: actions/upload-artifact@v6
        with:
          name: bandit-report
          path: bandit-report.json
```

---

## Módulos sin tests — prioridad de implementación

| Módulo | Líneas | Cobertura | Prioridad | Razón |
|--------|--------|-----------|-----------|-------|
| `jobs/runner.py` | 234 | 0% | P0 | Path traversal confirmado (CVSS 9.1) |
| `api/routes.py` | 105 | 0% | P0 | Todos los endpoints sin test |
| `api/models.py` | 27 | 0% | P0 | Validación Pydantic sin test |
| `llm/client.py` | 128 | 0% | P1 | SSRF potencial, lógica de retry |
| `jobs/manager.py` | 67 | 0% | P1 | Estado de jobs sin test |
| `llm/cleanup.py` | 49 | 0% | P1 | Retry logic sin test |
| `llm/filter.py` | 26 | 0% | P1 | Parsing de respuesta LLM sin test |
| `exceptions.py` | 34 | 0% | P2 | Exception handlers sin test |
| `main.py` | 12 | 0% | P2 | App startup sin test |
| `scraper/markdown.py` | 57 | 40% | P2 | `_pre_clean_markdown` sin test |

---

## Estadísticas

- **Total hallazgos**: 15
- **Critical**: 3 (FINDING-17-001, FINDING-17-002, FINDING-17-010)
- **Major**: 7 (FINDING-17-003, FINDING-17-004, FINDING-17-005, FINDING-17-006, FINDING-17-007, FINDING-17-008, FINDING-17-013)
- **Minor**: 4 (FINDING-17-009, FINDING-17-011, FINDING-17-012, FINDING-17-014)
- **Suggestion**: 1 (FINDING-17-015)

### Métricas actuales vs objetivo

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Tests totales | 95 | >200 |
| Cobertura total | 20% | 80% |
| Cobertura runner.py | 0% | 90% |
| Cobertura api/routes.py | 0% | 90% |
| Security gates activos | 0/3 | 3/3 |
| Tiempo de CI (estimado) | ~10 min | <5 min |
| Flaky tests | 0% | <1% |
| Threshold enforcement | Ninguno | 60% mínimo |
