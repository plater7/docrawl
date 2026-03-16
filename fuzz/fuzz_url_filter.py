#!/usr/bin/env python3
"""Fuzzer for filter_urls — targets URL filtering and language detection."""
import sys
import atheris

with atheris.instrument_imports():
    from src.crawler.filter import filter_urls


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    base_url = fdp.ConsumeUnicodeNoSurrogates(128)
    num_urls = fdp.ConsumeIntInRange(0, 10)
    urls = [fdp.ConsumeUnicodeNoSurrogates(128) for _ in range(num_urls)]
    language = fdp.ConsumeUnicodeNoSurrogates(8)
    try:
        filter_urls(urls, base_url, language)
    except Exception:
        pass  # invalid inputs are expected


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
