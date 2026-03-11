## Summary

Comprehensive audit and rate limiting implementation for all API endpoints.

## Problem

After initial rate limiting implementation, several endpoints were identified as lacking protection:
- Job status and events endpoints
- Job management operations
- Provider and model listing

## Solution

Perform comprehensive audit and add appropriate rate limits to all endpoints based on their sensitivity and expected usage patterns.

## Changes

- `src/api/routes.py`: Add/adjust rate limits:
  - High sensitivity: `10/minute` - Job creation, state resume
  - Medium sensitivity: `30/minute` - Job status, events
  - Low sensitivity: `60/minute` - Model listing, providers

## Testing

- [ ] Verify all endpoints have appropriate rate limits
- [ ] Test rate limit exceeded scenarios
- [ ] Confirm legitimate usage is not impacted

## Security Impact

**Risk Level:** Low (Enhancement)

Improves overall API security posture.

## References

- Related to: Rate limiting, CONS-005, CONS-007
