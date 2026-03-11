## Tests Added for Coverage

Added 6 new tests in `tests/scraper/test_page.py` to cover the custom selectors functionality:

1. **`test_remove_noise_with_custom_selectors`** - Verifies custom noise selectors are used
2. **`test_remove_noise_without_custom_selectors`** - Verifies default selectors work
3. **`test_extract_content_with_custom_selectors`** - Verifies custom content selectors are tried first
4. **`test_extract_content_falls_back_to_body`** - Verifies body fallback
5. **`test_get_html_accepts_custom_selectors`** - Verifies get_html accepts both parameters
6. **`test_get_html_with_pool_uses_custom_selectors`** - Verifies pool usage with custom selectors

All tests pass. Coverage for the new parameters has been added.
