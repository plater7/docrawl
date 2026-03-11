# PR Commands for Security Fixes

## PR #1: Fix Timing Attack Vulnerability in API Key Comparison

### Branch Name
`fix/timing-attack-api-key`

### Git Commands
```bash
# Create branch
git checkout -b fix/timing-attack-api-key

# Make changes to src/main.py
# Replace line 179: if key != _API_KEY:
# With: if not secrets.compare_digest(key, _API_KEY):

# Add and commit
git add src/main.py
git commit -m "fix: prevent timing attack in API key comparison

Use secrets.compare_digest() for constant-time string comparison
to prevent timing attacks when validating API keys.

Closes: [ISSUE_NUMBER]"

# Push branch
git push -u origin fix/timing-attack-api-key

# Create PR (use pr-body-timing-attack.md)
gh pr create --title "fix: prevent timing attack in API key comparison" --body-file pr-body-timing-attack.md --base main
```

---

## PR #2: Add Rate Limiting to Job Endpoints

### Branch Name
`fix/add-rate-limiting-job-endpoints`

### Git Commands
```bash
# Create branch
git checkout -b fix/add-rate-limiting-job-endpoints

# Make changes to src/api/routes.py
# Add @limiter.limit() decorators to:
# - /jobs/{job_id}/cancel
# - /jobs/{job_id}/pause
# - /jobs/{job_id}/resume
# - /jobs/{job_id}/status
# - /jobs/{job_id}/events

# Add and commit
git add src/api/routes.py
git commit -m "fix: add rate limiting to job management endpoints

Add @limiter.limit() decorators to prevent abuse of:
- GET /jobs/{job_id}/status
- GET /jobs/{job_id}/events
- POST /jobs/{job_id}/cancel
- POST /jobs/{job_id}/pause
- POST /jobs/{job_id}/resume

Closes: [ISSUE_NUMBER]"

# Push branch
git push -u origin fix/add-rate-limiting-job-endpoints

# Create PR (use pr-body-rate-limiting.md)
gh pr create --title "fix: add rate limiting to job management endpoints" --body-file pr-body-rate-limiting.md --base main
```

---

## PR #3: Sanitize Internal URLs from Health Check Error Responses

### Branch Name
`fix/sanitize-health-check-errors`

### Git Commands
```bash
# Create branch
git checkout -b fix/sanitize-health-check-errors

# Make changes to src/api/routes.py
# In health_ready() function, sanitize OLLAMA_URL from error messages
# Replace direct URL exposure with generic messages

# Add and commit
git add src/api/routes.py
git commit -m "fix: sanitize internal URLs from health check errors

Prevent exposure of internal infrastructure details (OLLAMA_URL)
in error messages returned by the health check endpoint.

Closes: [ISSUE_NUMBER]"

# Push branch
git push -u origin fix/sanitize-health-check-errors

# Create PR (use pr-body-sanitize-errors.md)
gh pr create --title "fix: sanitize internal URLs from health check errors" --body-file pr-body-sanitize-errors.md --base main
```

---

## PR #4: Add Rate Limiting to All API Endpoints (Bonus)

### Branch Name
`feat/comprehensive-rate-limiting`

### Git Commands
```bash
# Create branch
git checkout -b feat/comprehensive-rate-limiting

# Review all endpoints in src/api/routes.py
# Add appropriate rate limits to any endpoints missing them

# Add and commit
git add src/api/routes.py
git commit -m "feat: add comprehensive rate limiting to all API endpoints

Audit and add rate limiting to all endpoints to prevent abuse.

Closes: [ISSUE_NUMBER]"

# Push branch
git push -u origin feat/comprehensive-rate-limiting

# Create PR
gh pr create --title "feat: comprehensive rate limiting for all API endpoints" --body-file pr-body-rate-limiting-comprehensive.md --base main
```
