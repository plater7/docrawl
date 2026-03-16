# Fuzz Tests

Fuzzing targets for Docrawl's critical input-handling logic.
Uses [atheris](https://github.com/google/atheris) (Python coverage-guided fuzzer).

## Targets

| File | Target | Why |
|------|--------|-----|
| `fuzz_url_validator.py` | `validate_url_not_ssrf` | SSRF prevention |
| `fuzz_url_filter.py` | `filter_urls` | URL filtering/language detection |
| `fuzz_css_selectors.py` | `validate_selectors` (JobRequest) | CSS injection guard |

## Running locally

```bash
pip install atheris
# Run each fuzzer for 30 seconds
python fuzz/fuzz_url_validator.py -atheris_runs=10000
python fuzz/fuzz_url_filter.py -atheris_runs=10000
python fuzz/fuzz_css_selectors.py -atheris_runs=10000
```
