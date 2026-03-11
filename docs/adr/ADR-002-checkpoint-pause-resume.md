# ADR-002: Checkpoint-Based Pause/Resume

**Status:** Accepted  
**Date:** 2026-01 (retroactive, PR 3.1)  
**Deciders:** plater7

## Context

Crawl jobs can process hundreds of URLs over minutes or hours. Users needed the ability to pause long-running jobs (e.g., to free system resources) and resume them later without re-crawling already-completed pages. Server crashes or restarts should also not lose progress.

## Decision

Implement a checkpoint system (`src/jobs/state.py`) that persists job progress to a JSON state file:

```
{output_path}/.job_state.json
```

**State file contains:**
- Serialized `JobRequest` (original job parameters)
- `completed_urls` — successfully processed
- `failed_urls` — failed after retries
- `pending_urls` — not yet attempted

**Atomic writes:** State is written to `.job_state.json.tmp` first, then moved via `os.replace()` to the final path. This ensures the state file is never partially written (crash-safe).

**Resume flow:**
1. `POST /api/jobs/resume-from-state` with the state file path
2. Load state, reconstruct `JobRequest`, extract `pending_urls`
3. Create a **new** job that processes only the pending URLs
4. Discovery and filtering phases are skipped entirely

**In-memory pause:**
- `POST /api/jobs/{id}/pause` sets a flag; the runner suspends via `job.wait_if_paused()` (asyncio.Event)
- `POST /api/jobs/{id}/resume` clears the flag; processing continues
- State is checkpointed when pausing

## Consequences

**Positive:**
- Zero progress loss on pause or crash (state saved after each page)
- Resume creates a fresh job — no complex state restoration needed
- State file is human-readable JSON — debuggable
- Works across process restarts (state file persists on disk)

**Negative:**
- Resume-from-state creates a new job ID — no continuity in SSE event stream
- Sites may change between pause and resume (pages may 404, new pages won't be discovered)
- State file grows linearly with URL count (not a concern at current scale of ~1000 URLs max)
- No automatic resume on server restart — user must explicitly call resume endpoint

**Alternatives considered:**
- Database-backed state: rejected as over-engineering for a single-user tool
- In-memory checkpointing only: rejected because it doesn't survive process restarts