"""MarkdownConverter Protocol (PR 3.4).

All converters must implement this Protocol to be usable via the registry.
Uses @runtime_checkable for isinstance() checks.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class MarkdownConverter(Protocol):
    """Protocol for HTML → Markdown converters.

    Implementing this protocol is sufficient — no base class required.
    """

    def convert(self, html: str) -> str:
        """Convert HTML string to Markdown string."""
        ...

    def supports_tables(self) -> bool:
        """Return True if this converter renders HTML tables as Markdown tables."""
        ...

    def supports_code_blocks(self) -> bool:
        """Return True if this converter preserves fenced code block syntax."""
        ...
