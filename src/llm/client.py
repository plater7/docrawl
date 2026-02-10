"""Ollama API client."""

import os
import time
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


async def get_available_models() -> list[dict[str, Any]]:
    """Get list of available Ollama models."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        return []


async def generate(
    model: str,
    prompt: str,
    system: str | None = None,
    timeout: int = 120,
) -> str:
    """Generate text using Ollama."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    logger.debug(f"Ollama request: model={model}, prompt_len={len(prompt)} chars")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("response", "")

        duration_ms = (time.monotonic() - start) * 1000

        if not result:
            logger.warning(f"Ollama returned empty response for model={model}")
        else:
            logger.info(f"Ollama responded in {duration_ms:.0f}ms, response_len={len(result)} chars")
            logger.debug(f"Ollama response preview: {result[:200]}")

        return result
    except httpx.TimeoutException:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error(f"Ollama request timed out after {duration_ms:.0f}ms (limit {timeout}s)")
        raise
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error(f"Ollama request failed after {duration_ms:.0f}ms: {e}")
        raise
