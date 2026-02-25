# Wave 4 -- Agente 13: Code Reviewer

## Resumen ejecutivo

This audit reviewed six core modules (`runner.py`, `manager.py`, `discovery.py`, `filter.py`, `robots.py`, `client.py`) with a specific focus on race conditions, correctness bugs, type safety, error handling, and logic flaws. The review excludes findings already documented in Waves 1-2 (path traversal, SSRF, auth, XSS, sync HTTP in async, connection pooling, prompt injection, max_concurrent not implemented, sync write_text, dead code).

The most significant new findings are: (1) a race condition in `JobManager._jobs` dict where concurrent HTTP requests and background tasks mutate shared state without synchronization, (2) the `robots.py` parser lowercasing paths causing case-sensitive match failures on Linux, (3) `filter.py` unconditionally stripping all query strings which destroys stateful documentation URLs, (4) a retry count mismatch in `cleanup.py` where the code claims "max 3 retries" (per CLAUDE.md) but actually performs only 2 attempts, and (5) unbounded job accumulation in `JobManager` constituting a memory leak.

Additional correctness issues include the `_generate_index` function producing broken relative links, the `_url_to_filepath` function generating colliding file paths for URLs that differ only by query string, an unprotected `_task.exception()` call that can raise `CancelledError`, and silent exception swallowing in multiple modules. Overall, 17 findings were identified: 0 critical (security issues already documented), 7 major, 7 minor, and 3 suggestions.

## Hallazgos

### FINDING-13-001: Race condition on `JobManager._jobs` dict -- no synchronization
- **Severidad**: Major
- **Archivo**: `src/jobs/manager.py:83-101`
- **Descripcion**: `JobManager._jobs` is a plain `dict` mutated by both HTTP request handlers (`create_job`, `cancel_job`, `get_job`) and background `asyncio.Task`s (the runner modifies `job.status`, `job.pages_completed`, etc.). While Python's GIL prevents data corruption from true parallelism, `asyncio` cooperative multitasking means any `await` in the runner yields control, allowing an HTTP handler to read a `Job` object in a partially-updated state (e.g., `pages_completed` incremented but `status` not yet set to "completed"). More importantly, there is no lock protecting the `_jobs` dict itself -- if `create_job` is called concurrently with iteration over jobs (hypothetical future endpoint), the dict could raise `RuntimeError: dictionary changed size during iteration`.
```python
# manager.py:83
class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}  # No lock, no asyncio.Lock

    async def create_job(self, request: JobRequest) -> Job:
        # ...
        self._jobs[job_id] = job  # Concurrent mutation
```
- **Impacto**: Stale or inconsistent job status returned to UI. In the current single-endpoint design the risk is moderate, but any future multi-endpoint access or periodic cleanup task would be unsafe.
- **Fix**: Use an `asyncio.Lock` to protect `_jobs` mutations, or at minimum document that the manager is only safe within a single asyncio event loop with no concurrent dict iteration.

### FINDING-13-002: `robots.py` lowercases paths -- case-sensitive mismatch on Linux
- **Severidad**: Major
- **Archivo**: `src/crawler/robots.py:40-49`
- **Descripcion**: The `_parse` method lowercases the entire line (`line = line.strip().lower()`) including Disallow paths. Per RFC 9309 (robots.txt), path matching MUST be case-sensitive. On Linux servers (the majority), `/Admin/` and `/admin/` are different paths. By lowercasing the stored disallow paths but comparing against the original-case URL path in `is_allowed`, the parser will fail to block URLs that use uppercase characters matching the original robots.txt directive.
```python
# robots.py:40
line = line.strip().lower()  # Lowercases everything
# ...
if line.startswith("disallow:"):
    path = line.split(":", 1)[1].strip()  # path is now lowercase
    if path:
        self.disallowed.append(path)  # "/Admin/" stored as "/admin/"

# robots.py:58 -- comparison uses original case
def is_allowed(self, url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path  # Case preserved: "/Admin/secret"
    for disallowed in self.disallowed:
        if path.startswith(disallowed):  # "/Admin/secret".startswith("/admin/") = False!
            return False
```
- **Impacto**: URLs that should be blocked by robots.txt may be crawled, violating site owner directives. Could cause the crawler to be blocked by the target server. Conversely, if the URL is lowercase but the robots.txt uses uppercase, it would falsely block.
- **Fix**: Only lowercase the directive name (e.g., `user-agent`, `disallow`) for matching, but preserve the original case of the path value.

### FINDING-13-003: `filter.py` strips ALL query strings -- data loss for stateful doc URLs
- **Severidad**: Major
- **Archivo**: `src/crawler/filter.py:95`
- **Descripcion**: The deduplication normalization unconditionally removes query parameters by reconstructing the URL from only scheme + netloc + path. Many documentation sites use query strings for meaningful content routing (e.g., `?version=2`, `?tab=python`, `?lang=en`). The `normalize_url` function in `discovery.py` explicitly preserves query params, but `filter.py` silently discards them.
```python
# filter.py:95
normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
# No parsed.query -- ALL query strings stripped
```
- **Impacto**: Documentation pages that differ only by query string are collapsed into one URL, losing content. Pages that require query strings to render properly will 404 or show wrong content when scraped.
- **Fix**: Preserve query strings: `normalized = f"{parsed.scheme}://{parsed.netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")`.

### FINDING-13-004: Retry count mismatch -- 2 attempts, not 3 as documented
- **Severidad**: Major
- **Archivo**: `src/llm/cleanup.py:21-22,105`
- **Descripcion**: CLAUDE.md states "retry con backoff exponencial (max 3 intentos)". The code sets `MAX_RETRIES = 2` and loops `for attempt in range(MAX_RETRIES)`, yielding exactly 2 attempts (not 3). The `RETRY_BACKOFF` list has 2 elements `[1, 3]` which is consistent with `MAX_RETRIES = 2` but inconsistent with the documented "3 retries". Furthermore, the backoff is linear `[1, 3]`, not exponential as documented.
```python
MAX_RETRIES = 2
RETRY_BACKOFF = [1, 3]  # seconds

async def cleanup_markdown(markdown: str, model: str) -> str:
    for attempt in range(MAX_RETRIES):  # range(2) = [0, 1] -- only 2 attempts
        try:
            cleaned = await generate(...)
            if cleaned.strip():
                return cleaned.strip()
        except Exception as e:
            if attempt < MAX_RETRIES - 1:  # Only sleeps on attempt 0
                await asyncio.sleep(RETRY_BACKOFF[attempt])
```
- **Impacto**: Less resilience than documented. Users/operators expecting 3 attempts with exponential backoff get 2 attempts with linear backoff. The discrepancy between documentation and code can mislead debugging efforts.
- **Fix**: Either update `MAX_RETRIES = 3` and `RETRY_BACKOFF = [1, 2, 4]` (true exponential, 3 attempts), or update CLAUDE.md to reflect the actual behavior.

### FINDING-13-005: Memory leak -- completed jobs never cleaned from `JobManager._jobs`
- **Severidad**: Major
- **Archivo**: `src/jobs/manager.py:83-89`
- **Descripcion**: Every call to `create_job` adds a `Job` to `self._jobs` but nothing ever removes it. Each `Job` holds a reference to its `JobRequest`, the `asyncio.Queue` of events, the `asyncio.Task`, and all associated state. Over time (particularly for a long-running server), this dict grows without bound.
```python
async def create_job(self, request: JobRequest) -> Job:
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, request=request)
    self._jobs[job_id] = job  # Added here
    # ... never removed anywhere in the codebase
```
- **Impacto**: Memory consumption grows linearly with total jobs created. In a Docker container with limited memory, this will eventually cause OOM. The `asyncio.Task` reference also prevents garbage collection of the task's coroutine frame.
- **Fix**: Implement TTL-based cleanup (e.g., remove completed/failed jobs after 1 hour), or add a max jobs limit with LRU eviction. At minimum, clear the `_events` queue and nullify `_task` reference after job completion.

### FINDING-13-006: `_generate_index` produces broken relative links
- **Severidad**: Major
- **Archivo**: `src/jobs/runner.py:579-591`
- **Descripcion**: The index generation function constructs relative paths by replacing `/` with `_` in the URL path, but `_url_to_filepath` preserves the directory structure (using `/` as directory separators). This mismatch means the links in `_index.md` point to nonexistent flat files.
```python
# _generate_index at line 587:
rel_path = path.replace("/", "_") or "index"
lines.append(f"- [{name}]({rel_path}.md)")
# Produces: "- [install](guide_install.md)"

# But _url_to_filepath at line 576 produces:
# output_path / "guide/install.md"  (nested directory)
```
- **Impacto**: Every link in the generated `_index.md` table of contents is broken. Users opening the index file will get 404s for all documentation links.
- **Fix**: Use the same path derivation logic as `_url_to_filepath`, or generate relative paths that match the actual directory structure (e.g., `guide/install.md`).

### FINDING-13-007: `_url_to_filepath` collides on URLs differing only by query string
- **Severidad**: Major
- **Archivo**: `src/jobs/runner.py:557-576`
- **Descripcion**: The function only uses `parsed.path` to construct the file path, ignoring query strings entirely. Combined with FINDING-13-003 (filter.py stripping queries), if query strings do survive, two URLs like `/api?version=1` and `/api?version=2` would write to the same file, with the second overwriting the first.
```python
def _url_to_filepath(url: str, base_url: str, output_path: Path) -> Path:
    parsed = urlparse(url)
    path = parsed.path  # query string ignored
    # ...
    return output_path / f"{path}.md"
```
- **Impacto**: Silent data loss -- later pages overwrite earlier ones for URLs with same path but different query strings.
- **Fix**: Incorporate a sanitized query string into the filename (e.g., append `_q={hash}` or encode key query params into the path).

### FINDING-13-008: `event_stream` calls `_task.exception()` which re-raises `CancelledError`
- **Severidad**: Minor
- **Archivo**: `src/jobs/manager.py:54-56`
- **Descripcion**: When checking if the runner task died, the code calls `self._task.exception()`. Per Python docs, if the task was cancelled, calling `.exception()` raises `CancelledError` rather than returning it. The code guards with `if not self._task.cancelled()` but there is a TOCTOU window -- the task could be cancelled between the check and the `.exception()` call.
```python
exc = (
    self._task.exception()       # Raises CancelledError if task was cancelled
    if not self._task.cancelled() # Check happens before, but state can change
    else None
)
```
- **Impacto**: Unhandled `CancelledError` could propagate out of the generator, breaking the SSE stream with a 500 error.
- **Fix**: Wrap in try/except: `try: exc = self._task.exception() except (asyncio.CancelledError, asyncio.InvalidStateError): exc = None`.

### FINDING-13-009: `runner.py` cancellation leaves job in "cancelled" without `job_done` event
- **Severidad**: Minor
- **Archivo**: `src/jobs/runner.py:211-213, 281-282, 296-297`
- **Descripcion**: When `job.is_cancelled` is True, the runner `return`s or `break`s early. The `cancel_job` method in manager.py emits `job_cancelled` but the runner's finally block only checks for `status == "running"` to emit a safety-net `job_done`. Since `cancel()` sets status to "cancelled", the safety net does not fire. This is mostly correct, but if the `cancel_job` emit fails (network issue, queue full), no terminal event is ever sent and `event_stream` will hang until its 20s timeout detects the dead task.
```python
# runner.py finally block:
if job.status == "running":  # cancel() sets it to "cancelled", so this is skipped
    job.status = "failed"
    await job.emit_event("job_done", ...)
```
- **Impacto**: SSE clients may hang for up to 20 seconds after a cancellation if the cancel event emission fails.
- **Fix**: In the finally block, also check for cancelled status and ensure a terminal event was sent (e.g., check if queue has a terminal event, or add a `_terminal_sent` flag).

### FINDING-13-010: `cleanup_markdown` returns original on empty LLM response without logging
- **Severidad**: Minor
- **Archivo**: `src/llm/cleanup.py:114-115`
- **Descripcion**: If the LLM returns a non-empty response that becomes empty after `.strip()`, the code silently falls through to the next attempt without logging. If both attempts return whitespace-only, the function falls through to "All cleanup attempts failed" but the actual cause (empty response) is not logged.
```python
cleaned = await generate(...)
if cleaned.strip():          # Empty/whitespace response
    return cleaned.strip()
# Silently falls through to next attempt -- no log
```
- **Impacto**: Debugging LLM quality issues is harder because empty responses are not distinguished from exceptions. Operators may not realize their model is returning garbage.
- **Fix**: Log a warning when the response is empty: `else: logger.warning(f"Cleanup attempt {attempt + 1} returned empty response")`.

### FINDING-13-011: `discovery.py` sitemap parser vulnerable to XML bomb (billion laughs)
- **Severidad**: Minor
- **Archivo**: `src/crawler/discovery.py:369`
- **Descripcion**: `ET.fromstring(content)` uses the standard `xml.etree.ElementTree` parser which is vulnerable to entity expansion attacks (XML bombs / billion laughs). A malicious sitemap.xml could cause extreme memory consumption.
```python
root = ET.fromstring(content)  # No defused XML parsing
```
- **Impacto**: A malicious target site could craft a sitemap that causes OOM in the crawler container. This is lower severity than SSRF (already documented) since it requires the crawler to actively fetch a malicious sitemap.
- **Fix**: Use `defusedxml.ElementTree.fromstring()` instead, or set `xml.etree.ElementTree.XMLParser` with entity expansion limits.

### FINDING-13-012: `recursive_crawl` skips `#`-containing hrefs too aggressively
- **Severidad**: Minor
- **Archivo**: `src/crawler/discovery.py:161-165`
- **Descripcion**: The link filtering skips any href containing `#` anywhere in the string (not just fragment-only links). A link like `/docs/c#-guide` or `/docs/section#overview` would be skipped entirely rather than having its fragment stripped.
```python
if any(
    skip in href.lower()
    for skip in ["#", "javascript:", "mailto:", "tel:"]
):
    continue  # Skips "/docs/c#-guide" because "#" is in href
```
- **Impacto**: Legitimate documentation URLs containing `#` in their path segment (like C# guides) are silently excluded from discovery.
- **Fix**: Only skip hrefs that start with `#` (pure fragment links). For others, strip the fragment after `urljoin`.

### FINDING-13-013: `robots.py` only checks `User-agent: *`, ignores bot-specific rules
- **Severidad**: Minor
- **Archivo**: `src/crawler/robots.py:42-44`
- **Descripcion**: The parser only reads rules under `User-agent: *`. If a site has specific rules for `DocRawl` or more restrictive rules for other user agents, they are ignored. More importantly, if a site only has rules for specific bots and no `*` block, all Disallow rules are ignored.
```python
in_user_agent_all = agent == "*"  # Only matches wildcard
```
- **Impacto**: The crawler may violate robots.txt rules that are not under the wildcard user-agent. Low severity since most sites use `*`.
- **Fix**: Also look for the crawler's own User-Agent string (`docrawl`), with specific rules taking precedence over `*`.

### FINDING-13-014: `_get_openrouter_models` uses synchronous `httpx.get` in async context
- **Severidad**: Minor
- **Archivo**: `src/llm/client.py:97-103`
- **Descripcion**: `_get_openrouter_models()` is a sync function that makes a blocking `httpx.get()` call. It is called from `get_available_models()` which is async. This blocks the event loop during the HTTP request, stalling all concurrent coroutines.
```python
def _get_openrouter_models() -> list[dict[str, Any]]:  # Not async
    response = httpx.get(                                # Blocking call
        "https://openrouter.ai/api/v1/models",
        timeout=10,
    )
```
Note: This is related to the "sync HTTP in async" finding from Wave 1, but is a distinct instance in `client.py` that was not previously documented as the Wave 1 finding referenced other files.
- **Impacto**: Event loop blocked for up to 10 seconds during OpenRouter model listing, affecting all concurrent requests.
- **Fix**: Make the function async and use `httpx.AsyncClient`.

### FINDING-13-015: `try_sitemap` has unbounded recursion for nested sitemap indexes
- **Severidad**: Minor
- **Archivo**: `src/crawler/discovery.py:379-389`
- **Descripcion**: The `parse_sitemap_xml` inner function recursively calls itself for nested sitemaps with no depth limit. A malicious or misconfigured sitemap index that references itself (directly or via a chain) would cause infinite recursion until Python's stack limit is hit.
```python
for sitemap_elem in root.findall(".//ns:sitemap/ns:loc", namespace):
    nested_url = sitemap_elem.text
    if nested_url:
        nested_urls = await parse_sitemap_xml(nested_url, client)  # No depth limit
```
- **Impacto**: Stack overflow crash from a circular sitemap reference. The Python default recursion limit (1000) would eventually stop it with a `RecursionError`, but this is an unclean failure.
- **Fix**: Add a `depth` parameter with a max (e.g., 3 levels), or track visited sitemap URLs.

### FINDING-13-016: `runner.py` increments `pages_completed` even on cancellation mid-page
- **Severidad**: Suggestion
- **Archivo**: `src/jobs/runner.py:489`
- **Descripcion**: `job.pages_completed = i + 1` is set unconditionally after each URL iteration, even if the page processing was interrupted by cancellation (the `break` at line 296-297 exits the chunks loop but execution continues to line 489). A page that was cancelled mid-cleanup gets counted as "completed".
```python
for i, url in enumerate(urls):
    if job.is_cancelled:
        break
    # ... processing ...
    job.pages_completed = i + 1  # Set even if chunks loop was broken by cancel
    await asyncio.sleep(delay_s)
```
- **Impacto**: Minor inaccuracy in reported progress. The `job_cancelled` event may report one more page completed than was actually fully processed.
- **Fix**: Only increment if the page was fully processed (move inside the try block after save, or check `is_cancelled` before incrementing).

### FINDING-13-017: `validate_models` silently skips validation for unknown providers
- **Severidad**: Suggestion
- **Archivo**: `src/jobs/runner.py:46-63`
- **Descripcion**: For Ollama, the code validates model existence. For `openrouter`/`opencode`, it only checks connectivity. For any other provider (e.g., a typo like `openroouter`), `get_provider_for_model` defaults to `ollama`, and `get_available_models` returns `[]`. The check `if not available and provider in ["openrouter", "opencode"]` explicitly excludes unknown providers, so validation silently passes.
```python
elif not available and provider in ["openrouter", "opencode"]:
    errors.append(...)
# If provider is "ollama" (default for unknown) and available is [] (Ollama down),
# the "if not found and model_names" guard means no error is added when model_names is empty
```
- **Impacto**: A misspelled model name like `opnrouter/gpt-4` would be treated as an Ollama model, fail validation only if Ollama is reachable, and then fail at generation time with an unhelpful error.
- **Fix**: Add a catch-all else clause, or validate that the detected provider matches user intent.

### FINDING-13-018: `filter_urls_with_llm` does O(n*m) containment check with `in` on list
- **Severidad**: Suggestion
- **Archivo**: `src/llm/filter.py:60`
- **Descripcion**: The validation `[url for url in filtered if url in urls]` performs a linear scan of `urls` for each element in `filtered`. For large URL lists (up to 1000 from discovery), this is O(n*m).
```python
valid = [url for url in filtered if url in urls]  # urls is a list, not a set
```
- **Impacto**: Negligible for typical list sizes (< 1000), but technically quadratic.
- **Fix**: Convert `urls` to a `set` before the comprehension: `url_set = set(urls); valid = [url for url in filtered if url in url_set]`.

## Estadisticas
- Total: 18 | Critical: 0 | Major: 7 | Minor: 7 | Suggestion: 3

Note: Critical security issues (path traversal, SSRF, no auth, XSS) were already documented in Waves 1-2 and are intentionally not duplicated here. This review focused on correctness, race conditions, logic bugs, and code quality issues that were not previously identified.
