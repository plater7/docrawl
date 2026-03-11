## Summary

Add rate limiting to job management endpoints that were previously unprotected.

## Problem

Several job management endpoints lack rate limiting, potentially allowing attackers to:
- Enumerate job IDs by repeatedly querying status
- Abuse cancel/pause/resume operations
- Perform denial of service attacks

## Solution

Add `@limiter.limit()` decorators to all job management endpoints.

## Changes

- `src/api/routes.py`: Add rate limiting to:
  - `GET /api/jobs/{job_id}/status` - 30/minute
  - `GET /api/jobs/{job_id}/events` - 30/minute
  - `POST /api/jobs/{job_id}/cancel` - 10/minute
  - `POST /api/jobs/{job_id}/pause` - 10/minute
  - `POST /api/jobs/{job_id}/resume` - 10/minute

## Testing

- [ ] Verify rate limiting works correctly on each endpoint
- [ ] Confirm proper error responses when limit exceeded

## Security Impact

**Risk Level:** Medium

Prevents abuse and enumeration of job endpoints.

## References

- Related to: Rate limiting, CONS-005
