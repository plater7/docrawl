"""LLM client supporting multiple providers: Ollama, OpenRouter, OpenCode."""

import os
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Environment variables
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENCODE_API_KEY = os.environ.get("OPENCODE_API_KEY", "")

# Provider configurations
PROVIDERS = {
    "ollama": {
        "base_url": OLLAMA_URL,
        "requires_api_key": False,
        "model_format": "model",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "requires_api_key": True,
        "model_format": "model",
    },
    "opencode": {
        "base_url": "https://api.opencode.ai/v1",
        "requires_api_key": True,
        "model_format": "model",
    },
}

# Known models by provider (for UI selectors)
# These are used to filter/populate the model selectors based on provider
PROVIDER_MODELS = {
    "ollama": [],  # Dynamic - fetched from Ollama API
    "openrouter": [
        # Free tier models
        "openai/gpt-oss-120b:free",
        "openai/gpt-oss-20b:free",
        "qwen/qwen3-coder:free",
        "qwen/qwen3-4b:free",
        "qwen/qwen3-8b:free",
        "qwen/qwen3-14b:free",
        "qwen/qwen3-32b:free",
        "google/gemma-3-27b:free",
        "google/gemma-3-12b:free",
        "meta-llama/llama-3.3-70b:free",
        "meta-llama/llama-3.1-8b:free",
        "deepseek/deepseek-r1:free",
        "deepseek/deepseek-r1-67b:free",
        "nvidia/llama-3.1-nemotron-70b:free",
        "anthropic/claude-3.5-sonnet:free",
        "anthropic/claude-3-haiku:free",
        "moonshotai/kimi-k2.5:free",
        "stepfun/step-3.5-flash:free",
        "z-ai/glm-4.5-air:free",
        "minimax/minimax-text-01:free",
    ],
    "opencode": [
        # OpenCode models
        "opencode/claude-sonnet-4-5",
        "opencode/claude-haiku-4-5",
        "opencode/gpt-5-nano",
        "opencode/minimax-m2.5-free",
        "opencode/kimi-k2.5-free",
        "opencode/glm-4.7-free",
    ],
}


async def get_available_models(provider: str = "ollama") -> list[dict[str, Any]]:
    """Get list of available models for a provider."""
    if provider == "ollama":
        return await _get_ollama_models()
    elif provider == "openrouter":
        return _get_openrouter_models()
    elif provider == "opencode":
        return _get_opencode_models()
    else:
        return []


async def _get_ollama_models() -> list[dict[str, Any]]:
    """Get list of available Ollama models."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return [{"name": m["name"], "size": m.get("size"), "provider": "ollama"} for m in data.get("models", [])]
    except Exception as e:
        logger.error(f"Failed to get Ollama models: {e}")
        return []


def _get_openrouter_models() -> list[dict[str, Any]]:
    """Get list of OpenRouter models (from known free tier)."""
    return [{"name": m, "size": None, "provider": "openrouter"} for m in PROVIDER_MODELS["openrouter"]]


def _get_opencode_models() -> list[dict[str, Any]]:
    """Get list of OpenCode models."""
    return [{"name": m, "size": None, "provider": "opencode"} for m in PROVIDER_MODELS["opencode"]]


def get_provider_for_model(model: str) -> str:
    """Determine provider based on model name."""
    if "/" in model:
        # Models with namespace (e.g., openai/gpt-4, qwen/qwen3-14b)
        provider_prefix = model.split("/")[0]
        if provider_prefix in PROVIDERS:
            return provider_prefix
    # Default to ollama for bare model names
    return "ollama"


async def generate(
    model: str,
    prompt: str,
    system: str | None = None,
    timeout: int = 120,
    options: dict[str, Any] | None = None,
) -> str:
    """Generate text using the appropriate provider."""
    provider = get_provider_for_model(model)
    
    if provider == "ollama":
        return await _generate_ollama(model, prompt, system, timeout, options)
    elif provider == "openrouter":
        return await _generate_openrouter(model, prompt, system, timeout, options)
    elif provider == "opencode":
        return await _generate_opencode(model, prompt, system, timeout, options)
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def _generate_ollama(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using Ollama."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    if options:
        payload["options"] = options

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


async def _generate_openrouter(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using OpenRouter."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not configured")
    
    payload: dict[str, Any] = {
        "model": model,
        "messages": [],
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROVIDERS['openrouter']['base_url']}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"OpenRouter request failed: {e}")
        raise


async def _generate_opencode(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using OpenCode."""
    if not OPENCODE_API_KEY:
        raise ValueError("OPENCODE_API_KEY not configured")
    
    payload: dict[str, Any] = {
        "model": model,
        "messages": [],
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {OPENCODE_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROVIDERS['opencode']['base_url']}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"OpenCode request failed: {e}")
        raise


# Legacy functions for backwards compatibility
async def get_available_models_legacy() -> list[dict[str, Any]]:
    """Legacy: Get list of available Ollama models."""
    return await get_available_models("ollama")


async def generate_legacy(
    model: str,
    prompt: str,
    system: str | None = None,
    timeout: int = 120,
    options: dict[str, Any] | None = None,
) -> str:
    """Legacy: Generate text using Ollama."""
    return await generate(model, prompt, system, timeout, options)
