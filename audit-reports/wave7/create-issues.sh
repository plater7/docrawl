#!/bin/bash
# Script to create GitHub issues for all P0 and P1 findings
# Run from the docrawl repo root

REPO="plater7/docrawl"

echo "=== Checking existing labels ==="
gh label list --repo "$REPO" --limit 50

echo ""
echo "=== Checking existing milestones ==="
gh milestone list --repo "$REPO"

echo ""
echo "=== Creating missing labels if needed ==="
gh label create "P0" --repo "$REPO" --color "B60205" --description "Bloqueante de produccion" 2>/dev/null || echo "P0 already exists"
gh label create "P1" --repo "$REPO" --color "D93F0B" --description "Alta prioridad" 2>/dev/null || echo "P1 already exists"
gh label create "security" --repo "$REPO" --color "E4E669" --description "Security vulnerability" 2>/dev/null || echo "security already exists"
gh label create "bug" --repo "$REPO" --color "D73A4A" --description "Something isn't working" 2>/dev/null || echo "bug already exists"
gh label create "performance" --repo "$REPO" --color "0E8A16" --description "Performance improvement" 2>/dev/null || echo "performance already exists"
gh label create "refactor" --repo "$REPO" --color "C5DEF5" --description "Code refactoring" 2>/dev/null || echo "refactor already exists"
gh label create "testing" --repo "$REPO" --color "BFD4F2" --description "Testing improvements" 2>/dev/null || echo "testing already exists"
gh label create "ci-cd" --repo "$REPO" --color "F9D0C4" --description "CI/CD pipeline" 2>/dev/null || echo "ci-cd already exists"
gh label create "dx" --repo "$REPO" --color "D4C5F9" --description "Developer experience" 2>/dev/null || echo "dx already exists"
gh label create "docs" --repo "$REPO" --color "0075CA" --description "Documentation" 2>/dev/null || echo "docs already exists"

echo ""
echo "=== Creating P0 Issues ==="

# CONS-001
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-001: Path Traversal via output_path -- escritura arbitraria en filesystem" \
  --label "P0" --label "security" \
  --body "## Descripcion
El campo \`output_path\` del payload POST /api/jobs no tiene validacion. Un atacante puede enviar \`\"output_path\": \"/etc/cron.d\"\` o \`\"../../root/.ssh\"\` para escribir archivos en cualquier ubicacion del sistema. \`_url_to_filepath\` tambien es vulnerable via paths maliciosos en URLs scrapeadas.

## Impacto
Escritura arbitraria de archivos en el filesystem del container; escalada a RCE via cron o SSH authorized_keys.

## CVSS: 9.1

## Archivos afectados
- \`src/api/models.py:13\`
- \`src/jobs/runner.py:285\`
- \`src/crawler/discovery.py\` (\`_url_to_filepath\`)

## Fix sugerido
Pydantic \`field_validator\` que enforce prefijo \`/data/\` + \`Path.resolve()\` para verificar que el path resuelto siga bajo \`/data/\`. Mismo patron en \`_url_to_filepath\`.

## Referencias
Reportado en: Wave 1 (agent2, agent4, agent5), Wave 2 (agent9), Wave 4 (agent14, agent17), Wave 6 (agent21)"

# CONS-002
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-002: Sin autenticacion en ningun endpoint de la API" \
  --label "P0" --label "security" \
  --body "## Descripcion
Ningun endpoint de FastAPI tiene autenticacion. El diseno asume que el Cloudflare Worker es el unico punto de entrada, pero el puerto 8002 tambien esta expuesto en 0.0.0.0 (ver CONS-003). Cualquier persona con acceso de red puede crear jobs, cancelarlos o leer su output.

## Impacto
Acceso total no autorizado a toda la API; combinado con CONS-001 resulta en RCE.

## CVSS: 9.8

## Archivos afectados
- \`src/api/routes.py\` (todos los endpoints)
- \`src/main.py\`

## Fix sugerido
API key middleware en FastAPI que valide \`X-API-Key\` header contra variable de entorno. Debe cubrir todos los endpoints incluyendo SSE.

## Referencias
Reportado en: Wave 1 (agent2, agent4), Wave 2 (agent8, agent9), Wave 6 (agent21)"

# CONS-003
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-003: Puerto 8002 en 0.0.0.0 -- bypass del perimetro Cloudflare" \
  --label "P0" --label "security" \
  --body "## Descripcion
El servicio bindea en \`0.0.0.0:8002\`, exponiendo la API directamente en todas las interfaces de red del host. El Cloudflare Worker se vuelve decorativo -- cualquier cliente que alcance la IP del servidor accede a la API sin pasar por el Worker.

## Impacto
El perimetro de seguridad del Worker (unica capa de control de acceso) queda completamente anulado.

## CVSS: 9.8 (combinado con CONS-002)

## Archivos afectados
- \`docker-compose.yml\` (ports binding)
- \`src/main.py\` (uvicorn host)

## Fix sugerido
Cambiar binding a \`127.0.0.1:8002\` en uvicorn/docker-compose. \`cloudflared\` accede a \`localhost\` de todos modos.

## Referencias
Reportado en: Wave 2 (agent8), Wave 6 (agent21)"

# CONS-004
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-004: Cloudflare Worker sin autenticacion -- proxy abierto" \
  --label "P0" --label "security" \
  --body "## Descripcion
El Worker tiene 17 lineas de codigo y 0 validacion de autenticacion. Hace proxy de todas las requests verbatim, incluyendo todos los headers (Cookie, Authorization, X-Forwarded-For). Cualquier persona con la URL \`*.workers.dev\` tiene acceso total a la API.

## Impacto
Puerta de entrada publica completamente desprotegida; Host header poisoning posible via forward de headers verbatim.

## CVSS: 9.8

## Archivos afectados
- \`worker/src/index.js\`

## Fix sugerido
Validar \`X-API-Key\` header en el Worker antes de hacer fetch al servicio privado. Filtrar headers sensibles antes del forward.

## Referencias
Reportado en: Wave 2 (agent8, agent9), Wave 6 (agent21)"

# CONS-005
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-005: SSRF via Playwright -- acceso a servicios internos y metadata de cloud" \
  --label "P0" --label "security" \
  --body "## Descripcion
Playwright navega URLs proporcionadas por el usuario sin validacion de destino. Un atacante puede pasar \`url: \"http://169.254.169.254/latest/meta-data\"\` para exfiltrar credenciales de instancias cloud, o \`http://localhost:11434\` para interactuar con Ollama directamente.

## Impacto
Exfiltracion de credenciales cloud, acceso a servicios internos, pivoting dentro de la red privada.

## CVSS: 9.1

## Archivos afectados
- \`src/scraper/page.py\`
- \`src/crawler/discovery.py\`

## Fix sugerido
Resolver el hostname antes de navegar y rechazar IPs privadas (RFC 1918), link-local (169.254.x.x), loopback. Allowlist de esquemas (solo \`https://\` salvo configuracion explicita).

## Referencias
Reportado en: Wave 2 (agent9), Wave 4 (agent14), Wave 6 (agent21)"

# CONS-006
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-006: XSS via innerHTML con datos SSE no sanitizados" \
  --label "P0" --label "security" \
  --body "## Descripcion
Los mensajes SSE recibidos del servidor se interpolan directamente en \`innerHTML\` sin ningun tipo de sanitizacion. Un sitio malicioso puede incluir HTML/JS en su contenido que llegue al cliente via el stream SSE y se ejecute en el navegador del usuario.

## Impacto
XSS almacenado efectivo: cualquier sitio scrapeado puede inyectar JS arbitrario en el navegador del operador.

## CVSS: 7.5

## Archivos afectados
- \`src/ui/index.html:1273-1274, 1330-1334\`

## Fix sugerido
Reemplazar toda interpolacion \`innerHTML\` con \`textContent\` o \`createElement\`/\`appendChild\`. Nunca construir HTML via concatenacion de strings con datos externos.

## Referencias
Reportado en: Wave 1 (agent3), Wave 5 (agent20), Wave 6 (agent21)"

# CONS-007
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-007: Sin rate limiting ni cap de jobs concurrentes -- DoS" \
  --label "P0" --label "security" \
  --body "## Descripcion
Cualquier cliente puede crear jobs ilimitados via POST /api/jobs. Cada job crea instancias Playwright (Chromium headless). Sin limite, el servidor se queda sin memoria RAM o descriptores de archivo.

## Impacto
DoS completo de la aplicacion por agotamiento de recursos del sistema.

## CVSS: 7.5

## Archivos afectados
- \`src/api/routes.py\`
- \`src/jobs/manager.py\`

## Fix sugerido
\`slowapi\` para rate limiting por IP en \`POST /api/jobs\`. \`MAX_CONCURRENT_JOBS\` en JobManager que rechace con 429 cuando se supera. Validar bounds en \`max_concurrent\`, \`max_depth\`, \`delay_ms\`.

## Referencias
Reportado en: Wave 1 (agent2, agent4), Wave 4 (agent14), Wave 6 (agent21)"

# CONS-008
gh issue create --repo "$REPO" \
  --title "[P0][ci-cd] CONS-008: Security CI gates desactivados con || true" \
  --label "P0" --label "ci-cd" \
  --body "## Descripcion
Los steps de \`bandit\` (analisis estatico de seguridad Python) y \`pip-audit\` (escaneo de dependencias con CVEs) siempre terminan con exit code 0 por el \`|| true\`. Ningun PR puede ser bloqueado por una vulnerabilidad de seguridad detectada.

## Impacto
Fixes de CVSS 9.1/9.8 pueden revertirse silenciosamente sin que el CI lo detecte. Los CI security gates son puro teatro.

## Archivos afectados
- \`.github/workflows/security.yml:29,33,36\`

## Fix sugerido
Eliminar \`|| true\` de los steps de bandit y pip-audit. Agregar \`continue-on-error: false\` explicito. Configurar bandit con severity level \`HIGH\` minimo.

## Referencias
Reportado en: Wave 2 (agent7, agent8), Wave 4 (agent16, agent17), Wave 5 (agent19), Wave 6 (agent21)"

# CONS-009
gh issue create --repo "$REPO" \
  --title "[P0][testing] CONS-009: Cobertura de tests en 20% -- 9 de 14 modulos sin test" \
  --label "P0" --label "testing" \
  --body "## Descripcion
La cobertura medida es 20% (964/1209 lineas sin cubrir). Los modulos con mayor riesgo tienen 0% de cobertura: runner.py (591 LOC con el flujo completo del job), manager.py (event_stream), llm/ (503 LOC), API layer (path traversal sin test).

## Impacto
Cualquier fix de seguridad puede revertirse sin deteccion. Bugs de correctness en produccion sin regresiones. El vector de path traversal CVSS 9.1 no tiene ni un solo test.

## Archivos afectados
- \`src/jobs/runner.py\`
- \`src/jobs/manager.py\`
- \`src/llm/\` (todos)
- \`src/api/routes.py\`
- \`src/api/models.py\`
- \`src/scraper/\`

## Fix sugerido
Priorizar tests de seguridad (validacion de path traversal, SSRF) antes del deploy. Luego tests de runner.py con mocks de Playwright/Ollama. Target minimo: 60% cobertura en modulos criticos.

## Referencias
Reportado en: Wave 4 (agent16, agent17), Wave 2 (agent7)"

# CONS-010
gh issue create --repo "$REPO" \
  --title "[P0][bug] CONS-010: max_concurrent aceptado por API pero ignorado en runner" \
  --label "P0" --label "bug" \
  --body "## Descripcion
La API acepta y valida el parametro \`max_concurrent\` en el payload, y la UI lo presenta al usuario como opcion funcional. En \`runner.py\` el scraping siempre se ejecuta de forma secuencial. El parametro se lee pero nunca se usa.

## Impacto
El throughput prometido (3x-6x) nunca se alcanza. Un job de 50 paginas tarda 35-90 minutos en vez de 12-30 minutos. El usuario cree que esta usando concurrencia cuando no es asi.

## Archivos afectados
- \`src/jobs/runner.py:295\`
- \`src/api/models.py\`

## Fix sugerido
Implementar \`asyncio.Semaphore(max_concurrent)\` en runner.py para controlar el pool de coroutines de scraping.

## Referencias
Reportado en: Wave 1 (agent4, agent5), Wave 3 (agent10), Wave 4 (agent15, agent16), Wave 5 (agent20), Wave 6 (agent21)"

# CONS-011
gh issue create --repo "$REPO" \
  --title "[P0][bug] CONS-011: Truncamiento silencioso del LLM -- chunks 16K chars vs 8192 tokens" \
  --label "P0" --label "bug" \
  --body "## Descripcion
Los chunks para cleanup tienen 16,000 caracteres pero \`num_ctx\` esta hardcodeado en 8192 tokens. Ollama trunca silenciosamente el input. El LLM limpia solo la primera mitad y devuelve un resultado aparentemente valido. Para filtrado de URLs, \`num_ctx: 4096\` con sitios de 100+ URLs tambien desborda el contexto.

## Impacto
El usuario recibe markdown truncado/incompleto creyendo que esta limpio. El crawl de sitios grandes queda incompleto sin ninguna advertencia. Corrupcion silenciosa de datos.

## Archivos afectados
- \`src/llm/cleanup.py:74-85\`
- \`src/scraper/markdown.py:11\`
- \`src/llm/filter.py:26-31\`

## Fix sugerido
Reducir chunk size a ~6,000 chars. Leer \`prompt_eval_count\` de las respuestas Ollama y loguear advertencia. Hacer \`num_ctx\` configurable por modelo.

## Referencias
Reportado en: Wave 1 (agent5), Wave 3 (agent10, agent11), Wave 4 (agent15), Wave 6 (agent21)"

# CONS-012
gh issue create --repo "$REPO" \
  --title "[P0][security] CONS-012: Prompt injection via contenido scrapeado" \
  --label "P0" --label "security" \
  --body "## Descripcion
Los prompts usan \`.format(markdown=markdown)\` y \`\"\\n\".join(urls)\` sin delimitadores de separacion entre las instrucciones del sistema y el contenido externo. Un sitio malicioso puede incluir instrucciones en su HTML para manipular el comportamiento del LLM.

## Impacto
Un sitio scrapeado puede hacer que el LLM omita URLs relevantes, produzca output malformado, o filtre datos sensibles del prompt del sistema.

## CVSS: 8.0

## Archivos afectados
- \`src/llm/cleanup.py:15-19,101\`
- \`src/llm/filter.py:15-23,43\`

## Fix sugerido
Envolver el contenido externo en delimitadores XML explicitos (\`<document>...</document>\`, \`<urls>...</urls>\`) en todos los prompts.

## Referencias
Reportado en: Wave 2 (agent9), Wave 3 (agent12), Wave 4 (agent14)"

# CONS-013
gh issue create --repo "$REPO" \
  --title "[P0][bug] CONS-013: Sync HTTP bloquea event loop de asyncio hasta 10 segundos" \
  --label "P0" --label "bug" \
  --body "## Descripcion
\`_get_openrouter_models()\` usa \`httpx.get()\` sincrono dentro de una funcion invocada desde contexto async. Esto bloquea todo el event loop durante la duracion del request HTTP (hasta timeout de 10s), congelando todos los SSE streams activos.

## Impacto
Todos los usuarios activos ven sus SSE streams congelados cuando cualquier request a la lista de modelos esta en vuelo. La UI parece colgada.

## Archivos afectados
- \`src/llm/client.py:97-135\` (\`_get_openrouter_models\`)

## Fix sugerido
Convertir \`_get_openrouter_models()\` a \`async def\` usando \`httpx.AsyncClient\`.

## Referencias
Reportado en: Wave 1 (agent1, agent2, agent4, agent5), Wave 3 (agent10, agent11), Wave 4 (agent15), Wave 5 (agent20)"

# CONS-014
gh issue create --repo "$REPO" \
  --title "[P0][bug] CONS-014: create_task fire-and-forget sin manejo de errores ni shutdown" \
  --label "P0" --label "bug" \
  --body "## Descripcion
Los jobs se lanzan con \`asyncio.create_task()\` sin guardar la referencia de la task ni registrar un \`add_done_callback\`. Las excepciones no capturadas son silenciadas. Al apagar el servidor, las tasks huerfanas no son canceladas, dejando browsers Playwright abiertos.

## Impacto
Errores en jobs desaparecen silenciosamente. El apagado del servidor deja recursos sin liberar. Posible corrupcion del estado de jobs.

## Archivos afectados
- \`src/jobs/manager.py:94\`

## Fix sugerido
Guardar referencia de la task. Registrar \`done_callback\` que loguee excepciones y actualice el estado del job. En el lifespan shutdown de FastAPI, cancelar todas las tasks pendientes.

## Referencias
Reportado en: Wave 1 (agent2), Wave 4 (agent13)"

echo ""
echo "=== Creating P1 Issues ==="

# CONS-015
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-015: Memory leak -- jobs completados nunca se eliminan del dict" \
  --label "P1" --label "bug" \
  --body "## Descripcion
Los jobs se acumulan en \`self._jobs\` (dict en memoria) indefinidamente sin mecanismo de eviccion. En deployment de larga duracion, el proceso Python crece sin limite hasta causar OOM.

## Impacto
Memory leak que eventualmente derriba la aplicacion.

## Archivos afectados
- \`src/jobs/manager.py:83-89\`

## Fix sugerido
TTL-based eviction: jobs en estado terminal se eliminan despues de N horas (configurable, default 24h).

## Referencias
Reportado en: Wave 1 (agent1, agent2, agent4), Wave 4 (agent13), Wave 6 (agent21)"

# CONS-016
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-016: Race condition en JobManager._jobs -- dict sin asyncio.Lock" \
  --label "P1" --label "bug" \
  --body "## Descripcion
El dict \`_jobs\` es accedido concurrentemente desde multiples coroutines sin ningun \`asyncio.Lock\`. Las operaciones compuestas (check-then-set) no son atomicas y pueden producir race conditions.

## Impacto
Estado inconsistente de jobs; posible corrupcion de datos de estado.

## Archivos afectados
- \`src/jobs/manager.py\`

## Fix sugerido
Proteger operaciones de lectura-escritura sobre \`_jobs\` con \`asyncio.Lock\`.

## Referencias
Reportado en: Wave 4 (agent13)"

# CONS-017
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-017: Resource leak Playwright -- browsers no cerrados en error" \
  --label "P1" --label "bug" \
  --body "## Descripcion
En \`page.py\`, la instancia de Playwright no se guarda en la clase, imposibilitando limpieza en el destructor. En \`discovery.py\`, \`try_nav_parse\` crea una segunda instancia completa de Playwright. Si hay timeout o excepcion antes del \`finally\`, el browser queda abierto indefinidamente.

## Impacto
Cada error de scraping deja un proceso Chromium huerfano. En jobs grandes, agota RAM y procesos.

## Archivos afectados
- \`src/scraper/page.py:109-113\`
- \`src/crawler/discovery.py:237-296\`

## Fix sugerido
Usar context managers (\`async with\`) en todos los puntos de creacion de browsers. Reusar el browser dentro de un job.

## Referencias
Reportado en: Wave 1 (agent1, agent5), Wave 4 (agent15)"

# CONS-018
gh issue create --repo "$REPO" \
  --title "[P1][security] CONS-018: XXE en sitemap parser -- xml.etree sin defusedxml" \
  --label "P1" --label "security" \
  --body "## Descripcion
El parser de sitemap.xml usa \`xml.etree.ElementTree\` de stdlib, vulnerable a ataques XXE (XML External Entity). Un sitemap malicioso puede incluir entidades XML que lean archivos locales o realicen requests de red.

## Impacto
LFI (Local File Inclusion) y SSRF a traves del contenido XML del sitemap.

## CVSS: 8.6

## Archivos afectados
- \`src/crawler/discovery.py:369\`

## Fix sugerido
Reemplazar con \`defusedxml.ElementTree\` (drop-in replacement).

## Referencias
Reportado en: Wave 2 (agent9), Wave 4 (agent14)"

# CONS-019
gh issue create --repo "$REPO" \
  --title "[P1][security] CONS-019: SSRF via markdown_proxy_url -- URL sin validacion" \
  --label "P1" --label "security" \
  --body "## Descripcion
El campo \`markdown_proxy_url\` acepta cualquier URL sin validacion de destino. Vector SSRF secundario independiente del Playwright SSRF.

## Impacto
SSRF a servicios internos a traves de un vector diferente a Playwright.

## CVSS: 8.1

## Archivos afectados
- \`src/api/models.py:20\`

## Fix sugerido
Validar hostname publico (misma logica de SSRF blocklist que CONS-005). Si el campo no tiene caso de uso activo, eliminarlo.

## Referencias
Reportado en: Wave 2 (agent9), Wave 4 (agent14)"

# CONS-020
gh issue create --repo "$REPO" \
  --title "[P1][security] CONS-020: Parametros API sin limites numericos -- DoS por valores extremos" \
  --label "P1" --label "security" \
  --body "## Descripcion
Los campos \`delay_ms\`, \`max_concurrent\`, \`max_depth\` no tienen restricciones \`ge\`/\`le\` en los modelos Pydantic. Un usuario puede pasar \`max_depth: 999999\` o \`delay_ms: 0\`.

## Impacto
DoS por agotamiento de recursos del sistema con un solo request bien construido.

## CVSS: 7.5

## Archivos afectados
- \`src/api/models.py\`

## Fix sugerido
Agregar validadores Pydantic: \`delay_ms: int = Field(ge=0, le=60000)\`, \`max_concurrent: int = Field(ge=1, le=10)\`, \`max_depth: int = Field(ge=1, le=20)\`.

## Referencias
Reportado en: Wave 4 (agent14)"

# CONS-021
gh issue create --repo "$REPO" \
  --title "[P1][security] CONS-021: Data exfiltration -- contenido enviado a APIs externas sin consentimiento" \
  --label "P1" --label "security" \
  --body "## Descripcion
Cuando se configura un modelo de OpenRouter o OpenCode, el contenido completo de las paginas scrapeadas se envia a APIs externas de terceros. No hay advertencia al usuario ni forma de deshabilitar esto.

## Impacto
Datos confidenciales de documentacion interna pueden ser exfiltrados a terceros. Violacion de GDPR/privacidad.

## Archivos afectados
- \`src/llm/client.py:218-295\`

## Fix sugerido
Advertencia explicita en la UI cuando se seleccione un modelo no-Ollama. Agregar opcion para deshabilitar providers externos.

## Referencias
Reportado en: Wave 2 (agent9), Wave 4 (agent14)"

# CONS-022
gh issue create --repo "$REPO" \
  --title "[P1][security] CONS-022: Sin security headers HTTP -- CSP, X-Frame-Options, HSTS ausentes" \
  --label "P1" --label "security" \
  --body "## Descripcion
La aplicacion FastAPI no configura ningun security header HTTP estandar: sin CSP (agrava el XSS), sin X-Frame-Options (clickjacking), sin X-Content-Type-Options, sin HSTS.

## Impacto
Amplifica la severidad de otras vulnerabilidades (XSS, clickjacking).

## Archivos afectados
- \`src/main.py\`

## Fix sugerido
Agregar middleware de security headers en FastAPI. CSP restrictiva que deshabilite inline scripts.

## Referencias
Reportado en: Wave 4 (agent14)"

# CONS-023
gh issue create --repo "$REPO" \
  --title "[P1][performance] CONS-023: Sin connection pooling en cliente LLM -- 150+ TCP connections por job" \
  --label "P1" --label "performance" \
  --body "## Descripcion
Cada llamada al LLM crea y destruye un \`httpx.AsyncClient\` nuevo. Un job de 50 paginas con 3 chunks genera 150+ conexiones TCP efimeras.

## Impacto
Latencia adicional significativa por job. Carga innecesaria en Ollama. Riesgo de agotamiento de puertos efimeros.

## Archivos afectados
- \`src/llm/client.py:68,201,243,283\`

## Fix sugerido
Instanciar \`httpx.AsyncClient\` una vez como singleton, reutilizarlo en todas las llamadas, cerrarlo en shutdown.

## Referencias
Reportado en: Wave 3 (agent10, agent11), Wave 4 (agent15)"

# CONS-024
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-024: _generate_index produce links rotos -- separador _ en vez de /" \
  --label "P1" --label "bug" \
  --body "## Descripcion
La funcion \`_generate_index\` usa \`_\` como separador de paths en lugar de \`/\`. Los links relativos en el index no corresponden a la estructura real de directorios.

## Impacto
El output principal (\`_index.md\`) tiene todos sus links rotos por diseno. El archivo de indice no sirve para navegar la documentacion.

## Archivos afectados
- \`src/jobs/runner.py\`

## Fix sugerido
Corregir la logica de generacion de paths en \`_generate_index\` para usar \`/\` como separador.

## Referencias
Reportado en: Wave 1 (agent5), Wave 4 (agent13), Wave 5 (agent20)"

# CONS-025
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-025: reasoning_model validado pero nunca invocado en runner" \
  --label "P1" --label "bug" \
  --body "## Descripcion
El payload acepta \`reasoning_model\`. La UI lo presenta como funcional con ejemplos recomendados. En \`runner.py\`, el modelo se recibe pero nunca se llama. Si el modelo no existe en Ollama, el job falla con error confuso.

## Impacto
El usuario configura un modelo de razonamiento creyendo que esta siendo usado, cuando no lo esta.

## Archivos afectados
- \`src/jobs/runner.py\`
- \`src/api/models.py\`

## Fix sugerido
Marcar como \`Optional\` con warning en la UI indicando \"reservado para uso futuro\".

## Referencias
Reportado en: Wave 3 (agent10), Wave 4 (agent16), Wave 5 (agent20)"

# CONS-026
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-026: Parser JSON fragil para output del LLM -- falla >30% con modelos 7B" \
  --label "P1" --label "bug" \
  --body "## Descripcion
El parser de respuestas JSON del LLM falla silenciosamente con: bloques de codigo \`\`\`json\`\`\`, texto introductorio antes del JSON, objetos \`{}\` en vez de arrays \`[]\`, y whitespace no estandar. Tasa de fallo >30% en modelos 7B-14B.

## Impacto
El filtrado de URLs cae al fallback frecuentemente, aumentando paginas scrapeadas innecesariamente.

## Archivos afectados
- \`src/llm/filter.py\`
- \`src/llm/cleanup.py\`

## Fix sugerido
Parser robusto que extraiga el primer bloque JSON valido via regex. Validar schema esperado. Agregar few-shot examples.

## Referencias
Reportado en: Wave 3 (agent11, agent12), Wave 4 (agent16)"

# CONS-027
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-027: Exception handler de cleanup es dead code -- pages_partial siempre 0" \
  --label "P1" --label "bug" \
  --body "## Descripcion
El bloque \`except\` del cleanup LLM por chunks esta mal estructurado -- nunca se ejecuta para los casos de error que deberia capturar. \`pages_partial\` siempre reporta 0 en el resumen final.

## Impacto
El usuario no sabe cuantas paginas fallaron el cleanup y recibio markdown crudo. Estadisticas enganiosas.

## Archivos afectados
- \`src/jobs/runner.py\`

## Fix sugerido
Revisar estructura de try/except para que el handler de cleanup fallido se ejecute correctamente.

## Referencias
Reportado en: Wave 3 (agent10), Wave 4 (agent13)"

# CONS-028
gh issue create --repo "$REPO" \
  --title "[P1][bug] CONS-028: Sin crash recovery -- restart pierde todos los jobs activos" \
  --label "P1" --label "bug" \
  --body "## Descripcion
Todo el estado de jobs esta en memoria pura. Un crash del proceso Python, OOM kill, o restart manual pierden todos los jobs activos sin recuperacion posible. No hay checkpoint entre fases.

## Impacto
Jobs de larga duracion (1-2 horas) se pierden sin posibilidad de reanudarlos.

## Archivos afectados
- \`src/jobs/manager.py\`
- \`src/jobs/runner.py\`

## Fix sugerido
Journal de estado en SQLite o archivo JSON. Checkpoint del progreso entre fases principales. Recuperacion automatica al startup.

## Referencias
Reportado en: Wave 2 (agent8), Wave 6 (agent21)"

# CONS-029
gh issue create --repo "$REPO" \
  --title "[P1][refactor] CONS-029: __import__('os') inline en routes.py -- anti-patron critico" \
  --label "P1" --label "refactor" \
  --body "## Descripcion
Import dinamico de \`os\` en el cuerpo de una funcion con \`__import__('os')\`. Anti-patron que hace el codigo incomprensible. Bandit lo marca como hallazgo de seguridad.

## Impacto
Code review dificil. Bandit emite falsos positivos.

## Archivos afectados
- \`src/api/routes.py:62-63\`

## Fix sugerido
Mover \`import os\` al top-level del modulo.

## Referencias
Reportado en: Wave 1 (agent1, agent2, agent4)"

# CONS-030
gh issue create --repo "$REPO" \
  --title "[P1][performance] CONS-030: Sync file writes en event loop async -- bloqueo en Docker volumes" \
  --label "P1" --label "performance" \
  --body "## Descripcion
Las escrituras de archivos Markdown usan \`Path.write_text()\` sincrono dentro de funciones async. En Docker con bind mounts, las operaciones de filesystem pueden ser lentas, bloqueando el event loop.

## Impacto
Event loop queda bloqueado durante las escrituras, congela SSE streams activos.

## Archivos afectados
- \`src/jobs/runner.py\`

## Fix sugerido
Usar \`asyncio.to_thread(path.write_text, content)\` o \`aiofiles\`.

## Referencias
Reportado en: Wave 1 (agent1, agent5), Wave 4 (agent15)"

# CONS-031
gh issue create --repo "$REPO" \
  --title "[P1][ci-cd] CONS-031: Sin .dockerignore -- secrets y archivos dev copiados al image" \
  --label "P1" --label "ci-cd" \
  --body "## Descripcion
Sin \`.dockerignore\`, el build context incluye: \`.git/\` (historial completo), \`.env\` (tokens), \`data/\` (output de crawls previos). Aumenta tamano del image y puede exponer secrets.

## Impacto
Leakage de secrets en el Docker image si se publica a un registry. Image sobrepesado.

## Archivos afectados
- \`docker/Dockerfile\`
- Raiz del proyecto

## Fix sugerido
Crear \`.dockerignore\` excluyendo: \`.git\`, \`.env\`, \`data/\`, \`audit-reports/\`, \`tests/\`, \`*.md\`, \`worker/\`.

## Referencias
Reportado en: Wave 2 (agent6)"

# CONS-032
gh issue create --repo "$REPO" \
  --title "[P1][ci-cd] CONS-032: Test deps en imagen de produccion -- pytest en runtime container" \
  --label "P1" --label "ci-cd" \
  --body "## Descripcion
Las dependencias de testing (pytest, pytest-cov, pytest-asyncio) estan mezcladas en \`requirements.txt\` y se instalan en el image de produccion.

## Impacto
Image mas grande. Superficie de ataque aumentada.

## Archivos afectados
- \`docker/Dockerfile\`
- \`requirements.txt\`

## Fix sugerido
Separar en \`requirements.txt\` (produccion) y \`requirements-dev.txt\` (testing/dev).

## Referencias
Reportado en: Wave 2 (agent6, agent7)"

# CONS-033
gh issue create --repo "$REPO" \
  --title "[P1][ci-cd] CONS-033: cloudflared:latest unpinned -- puede romperse silenciosamente" \
  --label "P1" --label "ci-cd" \
  --body "## Descripcion
El servicio sidecar usa \`image: cloudflare/cloudflared:latest\`, un tag flotante. Un update del upstream puede introducir breaking changes.

## Impacto
Deployment puede dejar de funcionar tras un pull automatico.

## Archivos afectados
- \`docker-compose.yml\`

## Fix sugerido
Pinear a un digest especifico: \`image: cloudflare/cloudflared:2024.x.x\`.

## Referencias
Reportado en: Wave 2 (agent6, agent8)"

# CONS-034
gh issue create --repo "$REPO" \
  --title "[P1][security] CONS-034: Sin CORS configuration -- CORSMiddleware ausente" \
  --label "P1" --label "security" \
  --body "## Descripcion
FastAPI no configura ningun middleware CORS. El servidor puede aceptar requests cross-origin de cualquier dominio.

## Impacto
Comportamiento indefinido con requests cross-origin. Potencial vector para CSRF.

## Archivos afectados
- \`src/main.py\`

## Fix sugerido
Configurar \`CORSMiddleware\` con allowlist explicita de origenes.

## Referencias
Reportado en: Wave 1 (agent2, agent4)"

# CONS-035
gh issue create --repo "$REPO" \
  --title "[P1][ci-cd] CONS-035: Sin coverage threshold -- cobertura puede caer a 0% sin romper CI" \
  --label "P1" --label "ci-cd" \
  --body "## Descripcion
Codecov tiene \`fail_ci_if_error: false\` y no hay \`--cov-fail-under\` en pytest. La cobertura puede caer sin bloqueo.

## Impacto
Degeneracion progresiva de cobertura sin mecanismo de deteccion.

## Archivos afectados
- \`.github/workflows/test.yml\`

## Fix sugerido
Agregar \`--cov-fail-under=20\` a pytest. Cambiar \`fail_ci_if_error: true\` en Codecov.

## Referencias
Reportado en: Wave 2 (agent7), Wave 5 (agent19)"

echo ""
echo "=== All issues created ==="
echo ""
echo "=== Listing all issues ==="
gh issue list --repo "$REPO" --limit 50
