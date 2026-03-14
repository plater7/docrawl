"""Tests for unified LLM provider error hierarchy (issue #165)."""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMProviderError,
)
from src.llm.client import generate


class TestProviderErrorHierarchy:
    """LLMProviderError subclasses should be proper exceptions."""

    def test_llm_connection_error_is_provider_error(self):
        err = LLMConnectionError("ollama", "connection refused")
        assert isinstance(err, LLMProviderError)

    def test_llm_timeout_error_is_provider_error(self):
        err = LLMTimeoutError("openrouter", 30)
        assert isinstance(err, LLMProviderError)

    def test_llm_rate_limit_error_is_provider_error(self):
        err = LLMRateLimitError("openrouter", retry_after=60)
        assert isinstance(err, LLMProviderError)

    def test_llm_connection_error_str_has_provider(self):
        err = LLMConnectionError("ollama", "refused")
        assert "ollama" in str(err)

    def test_llm_timeout_error_str_has_timeout(self):
        err = LLMTimeoutError("lmstudio", 120)
        assert "120" in str(err)

    def test_llm_rate_limit_error_stores_retry_after(self):
        err = LLMRateLimitError("openrouter", retry_after=30)
        assert err.retry_after == 30

    def test_llm_rate_limit_error_retry_after_none_ok(self):
        err = LLMRateLimitError("openrouter")
        assert err.retry_after is None


class TestOllamaWrapsErrors:
    """_generate_ollama wraps httpx errors in LLMProviderError subclasses."""

    async def test_connect_error_raises_llm_connection_error(self):
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.ConnectError("refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with pytest.raises(LLMConnectionError) as exc_info:
                await generate("mistral:7b", "hello")
        assert exc_info.value.provider == "ollama"

    async def test_timeout_raises_llm_timeout_error(self):
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with pytest.raises(LLMTimeoutError) as exc_info:
                await generate("mistral:7b", "hello")
        assert exc_info.value.provider == "ollama"


class TestOpenRouterWrapsErrors:
    """_generate_openrouter wraps httpx errors in LLMProviderError subclasses."""

    async def test_connect_error_raises_llm_connection_error(self):
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.ConnectError("refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with patch("src.llm.client.OPENROUTER_API_KEY", "key"):
                with pytest.raises(LLMConnectionError):
                    await generate("openrouter/llama", "hello")

    async def test_timeout_raises_llm_timeout_error(self):
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with patch("src.llm.client.OPENROUTER_API_KEY", "key"):
                with pytest.raises(LLMTimeoutError):
                    await generate("openrouter/llama", "hello")

    async def test_429_raises_llm_rate_limit_error(self):
        """HTTP 429 from OpenRouter wraps in LLMRateLimitError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "30"}

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with patch("src.llm.client.OPENROUTER_API_KEY", "key"):
                with pytest.raises(LLMRateLimitError) as exc_info:
                    await generate("openrouter/llama", "hello")
        assert exc_info.value.retry_after == 30


class TestLMStudioWrapsErrors:
    """_generate_lmstudio wraps httpx errors in LLMProviderError subclasses."""

    async def test_connect_error_raises_llm_connection_error(self):
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.ConnectError("refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with pytest.raises(LLMConnectionError):
                await generate("lmstudio/llama", "hello")

    async def test_timeout_raises_llm_timeout_error(self):
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with pytest.raises(LLMTimeoutError):
                await generate("lmstudio/llama", "hello")
