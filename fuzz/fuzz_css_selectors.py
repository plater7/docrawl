#!/usr/bin/env python3
"""Fuzzer for CSS selector validation — targets backtick/brace injection guard."""
import sys
import atheris

with atheris.instrument_imports():
    from pydantic import ValidationError
    from src.api.models import JobRequest


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    num_selectors = fdp.ConsumeIntInRange(0, 5)
    selectors = [fdp.ConsumeUnicodeNoSurrogates(64) for _ in range(num_selectors)]
    try:
        JobRequest(
            url="https://example.com",
            pipeline_model="m",
            content_selectors=selectors,
        )
    except (ValidationError, ValueError):
        pass  # expected for invalid selectors
    except Exception:
        pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
