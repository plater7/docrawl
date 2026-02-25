# Wave 4 — Agente 14: Security Auditor (OWASP & Business Logic)

## Resumen ejecutivo

20 nuevos findings (no duplicados de waves anteriores): 3 Critical, 5 Major, 8 Minor, 3 Suggestion. Temas principales: XXE en sitemap, SSRF via markdown_proxy_url, parámetros sin límites (DoS/DDoS), sin security headers, memory leak de jobs, data exfiltration a LLMs externos.

## Hallazgos

### FINDING-14-001: XXE Injection en parser de sitemap
- **Severidad**: Critical | **OWASP**: A03 | **CVSS**: 8.6
- **Archivo**: `src/crawler/discovery.py:6,369`
- `xml.etree.ElementTree.fromstring()` sin defusedxml — sitemap malicioso puede leer `/etc/passwd`, SSRF, billion laughs DoS
- **Fix**: Reemplazar con `defusedxml.ElementTree`

### FINDING-14-002: SSRF via markdown_proxy_url controlado por usuario
- **Severidad**: Critical | **OWASP**: A03/A10 | **CVSS**: 8.1
- **Archivo**: `src/api/models.py:20`, `src/scraper/page.py:35-52`
- `markdown_proxy_url` sin validación — puede apuntar a `169.254.169.254` o `host.docker.internal`
- **Fix**: Allowlist de proxy conocidos + rechazar IPs privadas

### FINDING-14-003: Parámetros sin límites — DoS y DDoS
- **Severidad**: Critical | **OWASP**: A04 | **CVSS**: 7.5
- **Archivo**: `src/api/models.py:6-22`
- `delay_ms`, `max_concurrent`, `max_depth` sin `ge`/`le`. Permite `delay_ms:0`, `max_concurrent:999999`, `max_depth:1000`
- **Fix**: `Field(ge=100, le=60000)` etc.

### FINDING-14-004: Memory leak — jobs nunca se evictan
- **Severidad**: Major | **OWASP**: A04 | **CVSS**: 6.5
- **Archivo**: `src/jobs/manager.py:83-84`
- `_jobs` dict crece sin límite → OOM eventual
- **Fix**: TTL de evicción (1h), max jobs limit

### FINDING-14-005: Sin security headers en ninguna respuesta HTTP
- **Severidad**: Major | **OWASP**: A05 | **CVSS**: 5.8
- **Archivo**: `src/main.py:17-27`
- Faltan: CSP, X-Content-Type-Options, X-Frame-Options, HSTS, Referrer-Policy
- Agrava el XSS innerHTML ya conocido

### FINDING-14-006: Sin CORS explícito
- **Severidad**: Major | **OWASP**: A05 | **CVSS**: 5.4
- **Archivo**: `src/main.py:17`
- Política CORS dependiente del Worker, no de FastAPI — riesgo de misconfiguration futura

### FINDING-14-007: Worker forward todos los headers verbatim
- **Severidad**: Major | **OWASP**: A05 | **CVSS**: 5.3
- **Archivo**: `worker/src/index.js:9-13`
- Host header poisoning, IP spoofing en logs, headers internos CF expuestos al backend

### FINDING-14-008: Data exfiltration a LLM externos sin consentimiento
- **Severidad**: Major | **OWASP**: A04 | **CVSS**: 6.8
- **Archivo**: `src/llm/client.py:218-295`
- Al elegir OpenRouter/OpenCode, TODO el contenido scrapeado va a APIs externas — sin warning, sin consent

### FINDING-14-009: Playwright sin BrowserContext isolation
- **Severidad**: Minor | **OWASP**: A05 | **CVSS**: 4.7
- **Archivo**: `src/scraper/page.py:112`
- `browser.new_page()` directo — cookies/localStorage comparten contexto entre páginas de distintos sitios

### FINDING-14-010: Sin control de acceso a jobs entre usuarios
- **Severidad**: Minor | **OWASP**: A01 | **CVSS**: 4.3
- Cualquier cliente que sepa el job UUID puede ver eventos SSE o cancelar el job

### FINDING-14-011: model name permite XSS amplification via SSE
- **Severidad**: Minor | **OWASP**: A03 | **CVSS**: 3.8
- **Archivo**: `src/api/models.py:10-12`
- `crawl_model` sin validación de caracteres → fluye a `active_model` en SSE → innerHTML en UI (línea 1332)

### FINDING-14-012: Datos sensibles en logs cleartext
- **Severidad**: Minor | **OWASP**: A09 | **CVSS**: 3.5
- OLLAMA_URL en logs, health endpoint expone URL interna, stack traces en SSE

### FINDING-14-013: output_path sin validación de longitud/caracteres especiales
- **Severidad**: Minor | **OWASP**: A03 | **CVSS**: 3.7
- Además del path traversal conocido: sin max length, sin rechazo de caracteres especiales, sin resolución de symlinks

### FINDING-14-014: Dependencies sin pinning exacto ni hash verification
- **Severidad**: Minor | **OWASP**: A06/A08 | **CVSS**: 4.1
- **Archivo**: `requirements.txt`
- Solo `>=` — supply chain attack posible, builds no reproducibles, test deps en imagen de producción

### FINDING-14-015: Health endpoint expone topología interna
- **Severidad**: Minor | **OWASP**: A05 | **CVSS**: 3.1
- **Archivo**: `src/api/routes.py:130-230`
- Retorna OLLAMA_URL completo, disk space, data dir path sin autenticación

### FINDING-14-016: robots.py case-sensitivity bypass
- **Severidad**: Minor | **OWASP**: A04 | **CVSS**: 2.8
- Lowercasea paths en parse pero compara sin lowercase en is_allowed → falsos negativos

### FINDING-14-017: Sitemap recursivo sin depth limit
- **Severidad**: Minor | **OWASP**: A04 | **CVSS**: 4.0
- **Archivo**: `src/crawler/discovery.py:379-389`
- Sitemap index que se referencia a sí mismo → RecursionError

### FINDING-14-018: Contenido scrapeado sin límite de tamaño
- **Severidad**: Suggestion | **CVSS**: 3.0
- Página de 500MB → markdownify en memoria → OOM o disk exhaustion

### FINDING-14-019: /api/providers expone qué keys externas están configuradas
- **Severidad**: Suggestion | **CVSS**: 2.3
- Revela `{"configured": true}` para OpenRouter sin autenticación

### FINDING-14-020: Sin audit trail para eventos de seguridad
- **Severidad**: Suggestion | **CVSS**: 3.0
- No se loguean creaciones/cancelaciones de jobs, accesos a health, selección de provider externo

## Estadísticas
- Total: 20 | Critical: 3 | Major: 5 | Minor: 8 | Suggestion: 3

## Quick wins (30-60 min cada uno)
1. `defusedxml` en sitemap parser — elimina FINDING-14-001
2. `Field(ge=..., le=...)` en modelos Pydantic — elimina FINDING-14-003
3. Security headers middleware — mitiga FINDING-14-005
4. Validación regex en model name — mitiga FINDING-14-011
