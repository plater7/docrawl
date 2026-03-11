## Summary

Fix timing attack vulnerability in API key comparison by using `secrets.compare_digest()` for constant-time string comparison.

## Problem

The current implementation uses direct string comparison (`key != _API_KEY`) which is vulnerable to timing attacks. An attacker could use timing analysis to deduce the API key character by character by measuring response times.

## Solution

Replace direct string comparison with `secrets.compare_digest()` which performs constant-time comparison regardless of where the difference occurs in the strings.

## Changes

- `src/main.py`: Replace `if key != _API_KEY:` with `if not secrets.compare_digest(key, _API_KEY):`

## Testing

- [ ] Verify API key validation works correctly
- [ ] Confirm timing is constant regardless of key match/mismatch

## Security Impact

**Risk Level:** Medium

Prevents timing attack vectors that could lead to API key disclosure.

## References

- Related to: Timing attack vulnerabilities
- OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#timing-attacks
