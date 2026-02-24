# Contributing to Docrawl

Thanks for your interest in contributing to Docrawl!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/<your-user>/docrawl.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Install dependencies: `pip install -r requirements.txt`
5. Install Playwright browsers: `playwright install chromium`

## Development Setup

```bash
# Run locally
uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload

# Run with Docker
docker compose up --build

# Run tests
pytest --cov=src --cov-report=term-missing
```

## Code Standards

- **Python 3.12** with type hints
- **async/await** for all I/O operations
- **Pydantic** for data validation
- Use `logging` module, never `print()`
- Keep it simple: no unnecessary abstractions

## Pull Request Process

1. Ensure tests pass: `pytest`
2. Check linting: `ruff check src/ tests/`
3. Check formatting: `ruff format --check src/ tests/`
4. Update documentation if needed
5. Fill out the PR template completely
6. Request review from `@plater7`

## Reporting Issues

- **Bugs**: Use the Bug Report template
- **Features**: Use the Feature Request template
- **Security**: See [SECURITY.md](SECURITY.md) for responsible disclosure

## Code of Conduct

Be respectful. Write clear commit messages. Keep PRs focused and small.
