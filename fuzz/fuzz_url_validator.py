#!/usr/bin/env python3
"""Fuzzer for validate_url_not_ssrf — targets SSRF validation logic."""
import sys
import atheris

with atheris.instrument_imports():
    from src.utils.security import validate_url_not_ssrf


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    url = fdp.ConsumeUnicodeNoSurrogates(256)
    try:
        validate_url_not_ssrf(url)
    except ValueError:
        pass  # expected for invalid URLs
    except Exception:
        pass  # DNS errors, etc — not crashes


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
