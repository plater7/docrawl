## Summary

Sanitize internal URLs from health check error responses to prevent information disclosure.

## Problem

The health check endpoint (`/api/health/ready`) exposes internal infrastructure details like `OLLAMA_URL` (e.g., `http://localhost:11434`) in error messages. This could reveal:
- Internal service URLs
- Network topology
- Potential attack vectors

## Solution

Replace internal URLs with generic descriptions in error messages while still providing useful diagnostic information.

## Changes

- `src/api/routes.py`: Modify health check error messages to not include actual URLs
  - Before: `"Cannot connect to Ollama at http://localhost:11434"`
  - After: `"Cannot connect to Ollama service"`

## Testing

- [ ] Verify health check still returns useful diagnostic information
- [ ] Confirm internal URLs are not exposed in responses

## Security Impact

**Risk Level:** Medium

Prevents information disclosure about internal infrastructure.

## References

- Related to: Information disclosure, CONS-034
