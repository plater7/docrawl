# Security Audit Report: Docrawl

**Date:** 2026-03-11  
**Project:** Docrawl (v0.9.9)  
**Auditor:** Security Review

---

## Executive Summary

This report documents the findings of a comprehensive security audit of the Docrawl codebase. The application implements several security controls including SSRF protection, path traversal prevention, XXE protection, and security headers. However, several areas require attention, notably an IDOR vulnerability in job access endpoints and a timing attack vulnerability in API key comparison.

---

## 1. SECRETS & CONFIGURATION

### 1.1 Hardcoded Secrets - ✅ GOOD
No hardcoded API keys, tokens, or secrets found. All secrets are loaded from environment variables via `os.environ.get()`.

### 1.2 Environment Files in Git - ✅ GOOD
- `.env.example` - Template only (non-sensitive)
- `.gitignore` - Properly excludes `.env` files
- `.dockerignore` - Excludes `.env.*` files

### 1.3 CORS Configuration - ⚠️ MEDIUM RISK
**Location:** `src/main.py:133-143`

```python
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Api-Key"],
)
```

**Finding:** 
- If `CORS_ORIGINS` is empty (default), CORS allows no origins
- `allow_credentials=True` with empty origins can cause browser issues
- Risk: If `CORS_ORIGINS=*` is mistakenly set with credentials, browser will reject

### 1.4 Debug Mode - ✅ GOOD
No `DEBUG=True` found in codebase. Production defaults are secure.

### 1.5 Default Credentials - ✅ GOOD
No default passwords found. API key is optional (empty by default for dev mode).

### 1.6 Dependencies - ✅ GOOD
All dependencies use version constraints with `>=`:
- `defusedxml` included for XXE protection
- No known vulnerable dependencies detected

---

## 2. ACCESS & API SECURITY

### 2.1 Authentication - ⚠️ MEDIUM RISK

**Timing Attack Vulnerability**  
**Location:** `src/main.py:179`

```python
if key != _API_KEY:  # Direct string comparison - vulnerable to timing attacks
```

**Risk:** An attacker could use timing analysis to deduce the API key character by character.

**Recommendation:** Use `secrets.compare_digest()` for constant-time comparison:
```python
import secrets
if not secrets.compare_digest(key, _API_KEY):
```

**Auth Disabled When API_KEY Empty**  
**Location:** `src/main.py:174-175`

```python
if not _API_KEY:
    return await call_next(request)  # All routes publicly accessible
```

**Risk:** When `API_KEY` is not set, ALL routes are publicly accessible (intended for dev mode only). Ensure `API_KEY` is set in production.

### 2.2 Missing Rate Limiting - ✅ MOSTLY GOOD

Rate limiting is implemented on critical endpoints:
- `/jobs`: `@limiter.limit("10/minute")` ✅
- `/jobs/resume-from-state`: `@limiter.limit("10/minute")` ✅
- `/converters`: `@limiter.limit("60/minute")` ✅

**Minor Issue:** Some endpoints lack rate limiting:
- `/jobs/{job_id}/cancel`
- `/jobs/{job_id}/pause`  
- `/jobs/{job_id}/resume`
- `/jobs/{job_id}/status`
- `/jobs/{job_id}/events`

### 2.3 Error Response Disclosure - ⚠️ MEDIUM RISK

**Internal URLs Exposed**  
**Location:** `src/api/routes.py:176-188`

```python
except httpx.ConnectError:
    checks["ollama"] = {"status": "unreachable", "url": OLLAMA_URL}
    issues.append(f"Cannot connect to Ollama at {OLLAMA_URL}...")
```

**Risk:** Internal URLs like `localhost:11434` are exposed in error messages, revealing infrastructure details.

### 2.4 IDOR Vulnerability - ❌ HIGH RISK

**No Authorization on Job Access**  
**Location:** `src/api/routes.py:104-143`

```python
@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> EventSourceResponse:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # No ownership check - any user can access any job by guessing UUID
    return EventSourceResponse(job.event_stream(), ping=15)
```

**Affected Endpoints:**
- `GET /api/jobs/{job_id}/events`
- `GET /api/jobs/{job_id}/status`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/pause`
- `POST /api/jobs/{job_id}/resume`

**Risk:** Any user can access, cancel, pause, or resume ANY job by guessing a UUID. While UUIDs are hard to guess, job enumeration is possible.

**Recommendation:** Implement ownership verification or session-based authorization.

---

## 3. USER INPUT SECURITY

### 3.1 SQL Injection - ✅ N/A
No database usage found - uses in-memory job storage only.

### 3.2 XSS Protection - ✅ GOOD (with note)

**Good Practice:**  
**Location:** `src/ui/index.html:1606`
```javascript
// Build DOM nodes directly — no innerHTML with untrusted data
```

**Note:** Review `src/ui/index.html:1394` where innerHTML is used with job data:
```javascript
jobHistoryList.innerHTML = jobHistory.map(job => `...`)
```
Ensure job properties are properly escaped.

### 3.3 Path Traversal - ✅ GOOD
**Location:** `src/api/models.py:39-46, 82-89`

```python
@field_validator("output_path")
@classmethod
def validate_output_path(cls, v: str) -> str:
    """Prevent path traversal — closes CONS-001 / issue #47."""
    resolved = Path("/data").joinpath(v.lstrip("/")).resolve()
    if not str(resolved).startswith("/data"):
        raise ValueError("output_path must be under /data")
    return str(resolved)
```

Properly blocks path traversal by:
- Removing leading slashes with `lstrip("/")`
- Resolving path and validating it starts with `/data`

### 3.4 SSRF Protection - ✅ EXCELLENT
**Location:** `src/utils/security.py:1-32`

```python
PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

def validate_url_not_ssrf(url: str) -> None:
    """Raise ValueError if URL resolves to private/internal address."""
    host = urlparse(url).hostname
    addr = ipaddress.ip_address(socket.gethostbyname(host))
    if any(addr in net for net in PRIVATE_NETS):
        raise ValueError(f"URL targets private/internal address: {url}")
```

Used in:
- `src/scraper/page.py:25, 58, 85, 223`
- `src/crawler/discovery.py:271, 539`
- `src/api/models.py:57` (markdown_proxy_url validation)

Blocks: localhost, private networks, link-local (169.254), cloud metadata endpoints, IPv6 private ranges.

### 3.5 File Upload - ✅ N/A
No file upload functionality in the codebase.

---

## 4. ADDITIONAL SECURITY CONTROLS

### 4.1 XXE Protection - ✅ GOOD
**Location:** `src/crawler/discovery.py:8`

```python
import defusedxml.ElementTree as ET  # XXE-safe replacement
```

Uses `defusedxml` instead of standard `xml.etree.ElementTree`.

### 4.2 Security Headers - ✅ GOOD
**Location:** `src/main.py:146-163`

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self';"
        )
```

**Note:** `unsafe-inline` in CSP may be a concern for stricter security requirements.

### 4.3 Global Error Handling - ✅ GOOD
**Location:** `src/main.py:192-208`

```python
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a sanitized error response; never expose internal details."""
    logger.error("unhandled_exception", extra={...})
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
```

Tracebacks are logged but not exposed to users.

---

## 5. SUMMARY

| Category | Status | Risk Level |
|----------|--------|------------|
| Secrets/Config | ✅ GOOD | - |
| Authentication | ⚠️ MEDIUM | Timing attack, auth disabled when key empty |
| Rate Limiting | ✅ GOOD | Minor gaps on some endpoints |
| Error Handling | ⚠️ MEDIUM | Internal URLs exposed |
| IDOR | ❌ HIGH | No authorization on job access |
| SQL Injection | ✅ N/A | No database |
| XSS | ✅ GOOD | DOM-based, minor review needed |
| Path Traversal | ✅ GOOD | Properly validated |
| SSRF | ✅ EXCELLENT | Comprehensive protection |
| File Upload | ✅ N/A | Not applicable |
| Security Headers | ✅ GOOD | Properly implemented |
| XXE | ✅ GOOD | defusedxml used |

---

## 6. RECOMMENDATIONS

### Critical (Fix Immediately)
1. **IDOR** - Add ownership/authorization checks to job endpoints
2. **Timing Attack** - Use `secrets.compare_digest()` for API key comparison

### Medium Priority
3. Sanitize internal URLs from health check error responses
4. Review innerHTML usage in UI for potential XSS
5. Add rate limiting to remaining job endpoints

### Low Priority
6. Consider removing `unsafe-inline` from CSP for stricter security

---

## 7. AUTHENTICATION API DETAILS

**Authentication Endpoint:** None (uses API key header)

**Request Format:**
```
GET /api/<endpoint>
Header: X-Api-Key: <API_KEY>
```

**Login Request Body:** N/A - This is not a user authentication system; it uses API key authentication.

---

*End of Report*
