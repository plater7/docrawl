"""Converter registry for HTML -> Markdown backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MarkdownConverter(Protocol):
    def supports_tables(self) -> bool: ...
    def supports_code_blocks(self) -> bool: ...
    def convert(self, html: str) -> str: ...


_REGISTRY: dict[str, type] = {}


def register_converter(name: str, cls: type) -> None:
    _REGISTRY[name] = cls


def get_converter(name: str | None = None) -> MarkdownConverter:
    key = name or "markdownify"
    if key not in _REGISTRY:
        raise ValueError(f"Unknown converter: {key!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[key]()


def available_converters() -> list[str]:
    return list(_REGISTRY.keys())


# --- built-in registrations ---
from .markdownify_converter import MarkdownifyConverter  # noqa: E402

register_converter("markdownify", MarkdownifyConverter)

from .readerlm_converter import ReaderLMConverter  # noqa: E402

register_converter("readerlm", ReaderLMConverter)
register_converter(
    "readerlm-v1",
    type(
        "ReaderLMV1",
        (ReaderLMConverter,),
        {
            "__init__": lambda self, **kw: ReaderLMConverter.__init__(
                self, model="milkey/reader-lm:latest", **kw
            )
        },
    ),
)
