## Coverage & Lint Update

### Coverage
Added 8 tests in `tests/api/test_models.py` for the new `content_selectors` and `noise_selectors` validation:

- `test_content_selectors_none_default`
- `test_noise_selectors_none_default`  
- `test_content_selectors_valid_list`
- `test_noise_selectors_valid_list`
- `test_content_selectors_max_20_items`
- `test_noise_selectors_max_20_items`
- `test_content_selector_max_200_chars`
- `test_noise_selector_max_200_chars`

### Lint
All lint checks pass with ruff. No issues found.

### Test Results
All 669 tests pass.
