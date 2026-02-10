"""Ollama API client."""

import os
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

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    except httpx.TimeoutException:
        logger.error(f"Ollama request timed out after {timeout}s")
        raise
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise
