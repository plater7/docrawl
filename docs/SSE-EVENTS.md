# SSE Event Schema

DocRawl streams job progress via Server-Sent Events (SSE) at `GET /api/jobs/{id}/events`.

Connect with: `curl -N http://localhost:8002/api/jobs/{id}/events`

---

## Event Types

### `phase_change`
Emitted when the job transitions between pipeline phases or updates progress within a phase.

**Common Fields:**
- `phase` — current phase name (`init`, `discovery`, `filtering`, `scraping`, `cleanup`, `output`, or `failed`)
- `message` — human-readable description of what is happening
- `progress` — optional, progress indicator in format like `"3/47"` (current/total)
- `url` — optional, the URL currently being processed (in scraping phase)
- `active_model` — optional, the LLM model currently in use

**Examples:**

Initialization:
```json
{
  "event": "phase_change",
  "data": "{\"phase\": \"init\", \"message\": \"Validating models...\"}"
}
```

Discovery phase:
```json
{
  "event": "phase_change",
  "data": "{\"phase\": \"discovery\", \"message\": \"Discovered 47 URLs\"}"
}
```

Scraping with progress:
```json
{
  "event": "phase_change",
  "data": "{\"phase\": \"scraping\", \"message\": \"Loading page...\", \"progress\": \"15/47\", \"url\": \"https://example.com/page\"}"
}
```

### `log`
General informational or error message from the runner.

**Fields:**
- `message` — log text
- `level` — `"info"`, `"warning"`, or `"error"`
- `phase` — optional, phase where the message originated
- `active_model` — optional, LLM model in use when error occurred

**Example:**
```json
{
  "event": "log",
  "data": "{\"phase\": \"init\", \"message\": \"Model validation failed: invalid API key\", \"level\": \"error\"}"
}
```

### `job_done`
Terminal event. Emitted exactly once when the job finishes (success, failure, or cancellation).

**Fields (on success):**
- `status` — `"completed"`, `"failed"`, or `"cancelled"`
- `pages_ok` — pages that produced clean output
- `pages_partial` — pages with partial content (some extraction errors)
- `pages_failed` — pages that errored and produced no output
- `pages_retried` — number of pages retried due to transient errors
- `pages_native_md` — pages fetched via native markdown (Accept: text/markdown)
- `pages_proxy_md` — pages fetched via markdown proxy
- `pages_http_fast` — pages fetched via HTTP fast-path
- `pages_playwright` — pages rendered via browser/Playwright
- `pages_skipped` — pages skipped (duplicate content hash or cache hit)
- `pages_blocked` — pages blocked by robots.txt or domain filter
- `cache_hits` — number of cache hits (if `use_cache: true`)
- `cache_misses` — number of cache misses
- `output_path` — absolute path where output files were written
- `message` — summary message like `"Done: 44 ok, 2 partial, 1 failed"`

**Fields (on failure):**
- `status` — `"failed"`
- `error` — error message explaining why the job failed

**Fields (on cancellation):**
- `status` — `"cancelled"`
- `pages_completed` — number of pages processed before cancellation
- `pages_total` — total pages in the job
- `output_path` — path where partial output was written

**Success Example:**
```json
{
  "event": "job_done",
  "data": "{\"status\": \"completed\", \"pages_ok\": 44, \"pages_partial\": 2, \"pages_failed\": 1, \"pages_retried\": 3, \"pages_native_md\": 12, \"pages_proxy_md\": 3, \"pages_http_fast\": 25, \"pages_playwright\": 6, \"pages_skipped\": 4, \"pages_blocked\": 1, \"cache_hits\": 8, \"cache_misses\": 39, \"output_path\": \"/tmp/output\", \"message\": \"Done: 44 ok, 2 partial, 1 failed\"}"
}
```

**Failure Example:**
```json
{
  "event": "job_done",
  "data": "{\"status\": \"failed\", \"error\": \"Model validation failed: invalid API key\"}"
}
```

**Cancellation Example:**
```json
{
  "event": "job_done",
  "data": "{\"status\": \"cancelled\", \"pages_completed\": 15, \"pages_total\": 47, \"output_path\": \"/tmp/output\"}"
}
```

### `job_cancelled`
Terminal event when a cancellation is requested via `DELETE /api/jobs/{id}`.

**Fields:**
- `pages_completed` — number of pages processed before cancellation
- `pages_total` — total pages in the job
- `output_path` — path where partial output was written

**Example:**
```json
{
  "event": "job_cancelled",
  "data": "{\"pages_completed\": 15, \"pages_total\": 47, \"output_path\": \"/tmp/output\"}"
}
```

### `keepalive`
Sent every ~20 seconds to prevent proxy/browser timeouts. Data is always `{}`.

**Example:**
```json
{
  "event": "keepalive",
  "data": "{}"
}
```

---

## Event Stream Behavior

- **Terminal Events:** `job_done`, `job_cancelled`, and `job_error` (if runner crashes) end the event stream.
- **Auto-Keepalive:** If the job is idle for 20 seconds without emitting any event, a `keepalive` is sent.
- **No Event Replay:** The backend does not replay missed events. If the client disconnects and reconnects, it will only receive new events.
- **One-Time Consumption:** Each SSE stream is consumed once per client. Multiple browser tabs connected to the same job stream each receive events independently.

---

## Status Endpoint

**`GET /api/jobs/{id}/status`** returns the job status snapshot but does NOT include page counters:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "pages_total": 47,
  "pages_completed": 15,
  "current_url": "https://example.com/page-15"
}
```

Use the `job_done` SSE event (not this endpoint) to get final page statistics and fetch method breakdowns.

---

## Pause and Resume

- **No SSE Event on Pause/Resume:** Pausing or resuming a job does NOT emit an SSE event.
- **Poll for State Changes:** Use `GET /api/jobs/{id}/status` to check if a job is `paused` or `running` after calling `PATCH /api/jobs/{id}/pause` or `PATCH /api/jobs/{id}/resume`.
- **Progress Resumes:** After resume, scraping continues and `phase_change` events resume with updated progress.

---

## Error Recovery

If the runner task ends unexpectedly without emitting a terminal event:
- The `event_stream` generator detects this after the 20-second keepalive timeout.
- A synthetic `job_done` event is emitted: `{"event": "job_done", "data": "{\"status\": \"failed\", \"error\": \"Runner task ended unexpectedly\"}"}`

This ensures the client always receives a terminal event.

---

## Implementation Notes

- **JSON Parsing:** All `data` fields are JSON strings (not objects). Parse them with `JSON.parse()` in JavaScript or equivalent in other languages.
- **SSE Format:** Each event follows the standard SSE format: `event: {type}\ndata: {json_string}\n\n`
- **Concurrency:** Jobs run sequentially (one at a time per server instance due to browser resource constraints).
