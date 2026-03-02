"""Default MarkdownConverter using markdownify (PR 3.4).

This wraps the existing markdownify call used throughout the codebase.
Output is identical to the pre-converter-plugin behaviour.
"""

from markdownify import markdownify as _md


class MarkdownifyConverter:
    """Default HTML → Markdown converter using markdownify.

    Wraps the existing ``markdownify(html, heading_style="ATX", strip=[...])``
    call so it can be swapped out via the converter registry.
    """

    def convert(self, html: str) -> str:
        return _md(html, heading_style="ATX", strip=["script", "style", "nav", "footer"])

    def supports_tables(self) -> bool:
        return True

    def supports_code_blocks(self) -> bool:
        return True
