"""ReaderLMConverter: HTML -> Markdown via ReaderLM-v2/v1 (Ollama).

Drop-in replacement for MarkdownifyConverter. Uses Ollama's /api/chat
endpoint to call a locally-hosted ReaderLM model trained specifically
for HTML-to-Markdown translation.

Usage (via registry)::

    converter = get_converter("readerlm")    # v2 (1.5B, default)
    converter = get_converter("readerlm-v1") # v1 (0.5B, CPU-friendly)

Or directly::

    from src.scraper.converters.readerlm_converter import ReaderLMConverter
    md = ReaderLMConverter().convert(html_string)
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Convert the following HTML to clean, well-formatted Markdown. "
    "Remove all navigation menus, footers, cookie banners, and ads. "
    "Preserve code blocks, tables, lists, and inline formatting exactly."
)

# Token-budget heuristic: HTML compresses ~3:1 to tokens; add 2 K headroom.
# Cap at 131 072 (ReaderLM-v2 max context).
_CTX_HEADROOM = 2048
_CTX_MAX = 131_072


class ReaderLMConverter:
    """Markdown converter that delegates HTML->MD to a local ReaderLM model.

    Implements the MarkdownConverter protocol expected by the converter
    registry (supports_tables, supports_code_blocks, convert).
    """

    def __init__(
        self,
        model: str = "milkey/reader-lm-v2:latest",
        ollama_base_url: str = "http://localhost:11434",
        timeout: float = 90.0,
    ) -> None:
        self.model = model
        self.base_url = ollama_base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # MarkdownConverter protocol
    # ------------------------------------------------------------------

    def supports_tables(self) -> bool:
        return True

    def supports_code_blocks(self) -> bool:
        return True

    def convert(self, html: str) -> str:
        """Convert *html* to Markdown synchronously (blocking)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an async context (e.g. pytest-asyncio).
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(asyncio.run, self._convert_async(html))
                return future.result()
        else:
            return asyncio.run(self._convert_async(html))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _convert_async(self, html: str) -> str:
        num_ctx = min(len(html) // 3 + _CTX_HEADROOM, _CTX_MAX)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": html},
            ],
            "stream": False,
            "options": {"num_ctx": num_ctx},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
