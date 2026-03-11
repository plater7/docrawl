"""ReaderLMConverter: HTML -> Markdown via ReaderLM-v2/v1 (Ollama).

Drop-in replacement for MarkdownifyConverter. Uses Ollama's /api/chat
endpoint to call a locally-hosted ReaderLM model trained specifically
for HTML-to-Markdown translation — no markdownify + LLM cleanup needed.

Usage (via registry)::

    converter = get_converter("readerlm")      # v2 (1.5B, default)
    converter = get_converter("readerlm-v1")   # v1 (0.5B, CPU-friendly)
    md = converter.convert(html)
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Convert the following HTML to clean, well-formatted Markdown. "
    "Remove all navigation menus, footers, cookie banners, sidebars, and ads. "
    "Preserve code blocks with correct fencing, tables, nested lists, "
    "and inline formatting exactly. "
    "Return only the Markdown — no explanation, no preamble."
)

# Adaptive context window: ~3 chars per token for HTML, plus headroom
_CHARS_PER_TOKEN = 3
_CTX_HEADROOM = 2048
_CTX_MAX = 131072  # ReaderLM-v2 supports 512K but Ollama caps at 131072


class ReaderLMConverter:
    """HTML -> Markdown converter backed by ReaderLM via Ollama.

    Implements the MarkdownConverter Protocol (base.py):
      - convert(html: str) -> str
      - supports_tables() -> bool
      - supports_code_blocks() -> bool

    The sync ``convert()`` method wraps an async Ollama call so this
    converter fits the existing synchronous Protocol without requiring
    changes to the runner or registry.
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
    # MarkdownConverter Protocol
    # ------------------------------------------------------------------

    def convert(self, html: str) -> str:
        """Convert HTML to clean Markdown using ReaderLM.

        Schedules the async implementation on the running event loop.
        Raises on HTTP or model errors so the runner can degrade gracefully.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context (the runner) — use run_coroutine_threadsafe
            import concurrent.futures
            import threading

            result_holder: list[str] = []
            exc_holder: list[BaseException] = []

            def _thread_target() -> None:
                new_loop = asyncio.new_event_loop()
                try:
                    result_holder.append(
                        new_loop.run_until_complete(self._convert_async(html))
                    )
                except Exception as exc:  # noqa: BLE001
                    exc_holder.append(exc)
                finally:
                    new_loop.close()

            t = threading.Thread(target=_thread_target, daemon=True)
            t.start()
            t.join(timeout=self.timeout + 5)
            if exc_holder:
                raise exc_holder[0]
            return result_holder[0] if result_holder else ""
        else:
            return loop.run_until_complete(self._convert_async(html))

    def supports_tables(self) -> bool:
        return True

    def supports_code_blocks(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _convert_async(self, html: str) -> str:
        """POST to Ollama /api/chat and return the model's response."""
        num_ctx = min(
            len(html) // _CHARS_PER_TOKEN + _CTX_HEADROOM,
            _CTX_MAX,
        )
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
