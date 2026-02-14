# DocRawl Tests

Comprehensive unit and integration tests for the DocRawl crawler.

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/crawler/test_discovery.py
```

### Run tests with coverage
```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html to view coverage report
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only async tests
```bash
pytest -m asyncio
```

### Run with verbose output
```bash
pytest -vv
```

### Run specific test class or method
```bash
pytest tests/crawler/test_discovery.py::TestNormalizeUrl
pytest tests/crawler/test_discovery.py::TestNormalizeUrl::test_removes_fragment
```

## Test Organization

- `tests/crawler/test_discovery.py` - Discovery module tests
  - `TestNormalizeUrl` - URL normalization edge cases
  - `TestSitemapParsing` - Sitemap parsing with various XML formats
  - `TestRecursiveCrawl` - BFS crawl with depth, deduplication, 404s
  - `TestStrategySelection` - Discovery strategy selection logic
  - `TestEdgeCases` - Additional edge cases and error scenarios
  - `TestIntegrationScenarios` - Real-world scenario tests

## Test Coverage Goals

- **Target**: 80%+ code coverage
- **Critical paths**: 100% coverage for discovery strategies
- **Edge cases**: All error handlers must be tested

## Writing New Tests

1. Add test file in appropriate directory
2. Use descriptive test names: `test_<what>_<scenario>`
3. Include docstrings explaining what is tested
4. Use fixtures from `conftest.py` for common test data
5. Mark async tests with `@pytest.mark.asyncio`
6. Mock external dependencies (httpx, Playwright)

## Continuous Integration

Tests run automatically on:
- Pull requests
- Pushes to main
- Manual workflow dispatch

See `.github/workflows/test.yml` for CI configuration.
