"""
Unit tests for llama.cpp LLM provider in src/llm/client.py

Tests cover:
- _get_llamacpp_models() with mocked httpx — success, empty data, and failure
- get_provider_for_model() routing for llamacpp/ prefix
- _generate_llamacpp() with mocked httpx — success and failure cases
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.client import (
    get_provider_for_model,
    get_available_models,
    _get_llamacpp_models,
    _generate_llamacpp,
    _is_free_model,
)


class TestGetProviderForModel:
    """Test provider routing based on model name."""

    def test_llamacpp_prefix_returns_llamacpp(self):
        """llamacpp/ prefix routes to llamacpp."""
        assert get_provider_for_model("llamacpp/mistral") == "llamacpp"

    def test_llamacpp_model_with_tag(self):
        """llamacpp model with colon tag stays as llamacpp."""
        assert get_provider_for_model("llamacpp/llama3:8b") == "llamacpp"


class TestGetLlamaCppModels:
    """Test _get_llamacpp_models() with mocked httpx."""

    async def test_success_parses_model_list(self):
        """Successful response is parsed into model dicts."""
        fake_data = {
            "data": [
                {"id": "mistral-7b-instruct"},
                {"id": "llama-3-8b"},
            ]
        }
        mock_response = MagicMock()
        mock_response.json.return_value = fake_data
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_llamacpp_models()

        assert len(result) == 2
        assert result[0]["name"] == "llamacpp/mistral-7b-instruct"
        assert result[0]["provider"] == "llamacpp"
        assert result[0]["is_free"] is True
        assert result[0]["size"] is None

    async def test_success_handles_empty_data_list(self):
        """Response with empty data list returns empty list."""
        fake_data = {"data": []}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_data
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_llamacpp_models()

        assert result == []

    async def test_connection_error_returns_empty_list(self):
        """httpx ConnectError causes _get_llamacpp_models to return []."""
        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.ConnectError("connection refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_llamacpp_models()

        assert result == []

    async def test_timeout_error_returns_empty_list(self):
        """TimeoutException causes _get_llamacpp_models to return []."""
        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_llamacpp_models()

        assert result == []


class TestGenerateLlamaCpp:
    """Test _generate_llamacpp() with mocked httpx."""

    async def test_success_no_key(self):
        """Successful response is parsed and content returned."""
        fake_reply = {"choices": [{"message": {"content": "Hello from llama.cpp"}}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with patch("src.llm.client.LLAMACPP_API_KEY", ""):
                result = await _generate_llamacpp(
                    "llamacpp/mistral", "Hi", None, 60, None
                )

        assert result == "Hello from llama.cpp"

    async def test_with_api_key_sends_auth_header(self):
        """Authorization header is sent when LLAMACPP_API_KEY is set."""
        fake_reply = {"choices": [{"message": {"content": "ok"}}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with patch("src.llm.client.LLAMACPP_API_KEY", "test-key"):
                await _generate_llamacpp("llamacpp/llama3", "Hi", None, 60, None)

        call_kwargs = client_instance.post.call_args.kwargs
        assert call_kwargs["headers"].get("Authorization") == "Bearer test-key"

    async def test_timeout_propagates(self):
        """TimeoutException from llama.cpp is wrapped as LLMTimeoutError."""
        from src.exceptions import LLMTimeoutError

        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with pytest.raises(LLMTimeoutError):
                await _generate_llamacpp("llamacpp/llama3", "hi", None, 60, None)


class TestGetAvailableModelsLlamaCpp:
    """Test get_available_models for llamacpp provider."""

    async def test_get_available_models_llamacpp(self):
        """get_available_models routes to _get_llamacpp_models for llamacpp."""
        fake_data = {"data": [{"id": "model1"}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_data
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await get_available_models("llamacpp")

        assert len(result) == 1
        assert result[0]["name"] == "llamacpp/model1"
        assert result[0]["provider"] == "llamacpp"


class TestIsFreeModelLlamaCpp:
    """Test _is_free_model for llamacpp provider."""

    def test_llamacpp_always_free(self):
        """llamacpp models are always free."""
        assert _is_free_model("llamacpp/any-model", "llamacpp") is True
        assert _is_free_model("llamacpp/llama3:8b", "llamacpp") is True
        assert _is_free_model("llamacpp/test", "llamacpp") is True
