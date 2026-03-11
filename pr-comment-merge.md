## Conflicts Resolved

Successfully merged PR #157 (retry logic) with PR #160 (custom selectors):

### Resolution:
- **Keep retry logic** from PR #157 with `MAX_SCRAPE_RETRIES`
- **Keep custom selectors** from PR #160 (`content_selectors`, `noise_selectors`)
- Use consistent parameter naming across both features

### Changes:
- `src/jobs/runner.py`: Added retry loop with custom selectors parameter
- `src/scraper/page.py`: Updated `_remove_noise()`, `_extract_content()`, and `get_html()` to accept custom selectors

### Test Results:
✅ All 717 tests pass
✅ Lint checks pass (ruff)
