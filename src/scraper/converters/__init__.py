"""Converter plugin registry (PR 3.4).

Usage::

    from src.scraper.converters import get_converter, register_converter, available_converters

    converter = get_converter()          # default "markdownify"
    converter = get_converter("markdownify")
    md = converter.convert(html)

    # Register a custom converter
    register_converter("my_converter", MyConverter())

    # List all registered converters
    names = available_converters()  # ["markdownify"]
"""

import logging
from typing import TYPE_CHECKING

from src.scraper.converters.base import MarkdownConverter
from src.scraper.converters.markdownify_converter import MarkdownifyConverter

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Static registry — dynamic loading deferred to a future PR
_REGISTRY: dict[str, MarkdownConverter] = {
    "markdownify": MarkdownifyConverter(),
}

_DEFAULT_CONVERTER = "markdownify"


def get_converter(name: str | None = None) -> MarkdownConverter:
    """Return a converter by name, or the default if name is None.

    Raises KeyError if the named converter is not registered.
    """
    key = name or _DEFAULT_CONVERTER
    if key not in _REGISTRY:
        raise KeyError(
            f"Converter '{key}' not found. Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[key]


def register_converter(name: str, converter: MarkdownConverter) -> None:
    """Register a converter instance under a name.

    The converter must implement the MarkdownConverter Protocol.
    Raises TypeError if the protocol is not satisfied.

    Note: Not thread-safe. Concurrent registration during tests should be
    guarded externally. In production, converters are registered at startup
    (before async event loop), so this is not a runtime concern.
    """
    if not isinstance(converter, MarkdownConverter):
        raise TypeError(
            f"'{type(converter).__name__}' does not implement the MarkdownConverter protocol."
        )
    _REGISTRY[name] = converter
    logger.info(f"Registered converter: {name}")


def available_converters() -> list[str]:
    """Return names of all registered converters."""
    return list(_REGISTRY.keys())
