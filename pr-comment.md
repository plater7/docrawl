## Code Review - Fix Applied

### Critical Bug Found (Now Fixed)

The PR passes `content_selectors` and `noise_selectors` to `scraper.get_html()`, but the original `PageScraper.get_html()` method didn't accept these parameters, causing a **TypeError** at runtime.

### Fix Applied

Updated `src/scraper/page.py`:

1. **`_remove_noise()`** - Now accepts optional `noise_selectors` parameter:
   - User selectors are prepended to default `NOISE_SELECTORS`
   - Custom noise elements are removed before content extraction

2. **`_extract_content()`** - Now accepts optional `content_selectors` parameter:
   - User selectors are prepended to default `CONTENT_SELECTORS`
   - Custom content selectors are tried before falling back to defaults

3. **`get_html()`** - Updated signature to accept both parameters

The fix has been committed to the branch as `41d28d3`.
