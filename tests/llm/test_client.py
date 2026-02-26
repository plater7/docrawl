"""
Unit tests for src/llm/client.py

Tests cover:
- get_provider_for_model() routing logic
- _is_free_model() by provider
- _get_opencode_models() static list
- _get_ollama_models() with mocked httpx — success and failure
- generate() with Ollama — mocked httpx response parsing
- generate() unknown provider (routes to ollama which then fails)
- _generate_openrouter() without API key raises ValueError
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


from src.llm.client import (
    get_provider_for_model,
    _is_free_model,
    _get_opencode_models,
    _get_ollama_models,
    _generate_openrouter,
    generate,
)


class TestGetProviderForModel:
    """Test provider routing based on model name."""

    def test_bare_model_name_returns_ollama(self):
        """Model names without / prefix default to ollama."""
        assert get_provider_for_model("mistral:7b") == "ollama"

    def test_openrouter_prefix_returns_openrouter(self):
        """openrouter/ prefix routes to openrouter."""
        assert get_provider_for_model("openrouter/llama") == "openrouter"

    def test_opencode_prefix_returns_opencode(self):
        """opencode/ prefix routes to opencode."""
        assert get_provider_for_model("opencode/claude") == "opencode"

    def test_unknown_prefix_defaults_to_ollama(self):
        """Unknown slash prefix (e.g. openai/) falls back to ollama."""
        assert get_provider_for_model("openai/gpt-4") == "ollama"

    def test_ollama_model_with_tag(self):
        """Ollama model with colon tag stays as ollama."""
        assert get_provider_for_model("llama3:8b") == "ollama"

    def test_ollama_model_with_namespace_colon(self):
        """Ollama model namespace:tag style stays as ollama."""
        assert get_provider_for_model("qwen3:14b") == "ollama"


class TestIsFreeModel:
    """Test _is_free_model() per provider."""

    def test_ollama_models_always_free(self):
        """All Ollama models are free."""
        assert _is_free_model("mistral:7b", "ollama") is True
        assert _is_free_model("any-model", "ollama") is True

    def test_openrouter_free_model(self):
        """Models with :free suffix on openrouter are free."""
        assert _is_free_model("llama3:free", "openrouter") is True

    def test_openrouter_paid_model(self):
        """Models without :free suffix on openrouter are not free."""
        assert _is_free_model("gpt-4", "openrouter") is False

    def test_opencode_free_model_with_free_suffix(self):
        """opencode models ending in -free are free."""
        assert _is_free_model("opencode/minimax-m2.5-free", "opencode") is True

    def test_opencode_paid_model(self):
        """opencode models without free indicator are not free."""
        assert _is_free_model("opencode/claude-sonnet-4-5", "opencode") is False

    def test_unknown_provider_not_free(self):
        """Unknown provider returns False."""
        assert _is_free_model("somemodel", "unknown-provider") is False


class TestGetOpencodeModels:
    """Test _get_opencode_models() static list."""

    def test_returns_list(self):
        """Should return a non-empty list."""
        models = _get_opencode_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_all_have_opencode_provider(self):
        """Every model in the list should have provider='opencode'."""
        models = _get_opencode_models()
        for model in models:
            assert model["provider"] == "opencode"

    def test_all_have_name_field(self):
        """Every model should have a non-empty 'name' field."""
        models = _get_opencode_models()
        for model in models:
            assert "name" in model
            assert model["name"]

    def test_all_have_is_free_field(self):
        """Every model should have an 'is_free' boolean field."""
        models = _get_opencode_models()
        for model in models:
            assert "is_free" in model
            assert isinstance(model["is_free"], bool)

    def test_free_models_marked_correctly(self):
        """Models with 'free' in their name should be marked is_free=True."""
        models = _get_opencode_models()
        for model in models:
            if "free" in model["name"].lower():
                assert model["is_free"] is True


class TestGetOllamaModels:
    """Test _get_ollama_models() with mocked httpx."""

    async def test_success_parses_model_list(self):
        """Successful response is parsed into model dicts."""
        fake_data = {
            "models": [
                {"name": "mistral:7b", "size": 4_200_000_000},
                {"name": "llama3:8b", "size": 5_100_000_000},
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
            result = await _get_ollama_models()

        assert len(result) == 2
        assert result[0]["name"] == "mistral:7b"
        assert result[0]["provider"] == "ollama"
        assert result[0]["is_free"] is True
        assert result[0]["size"] == 4_200_000_000

    async def test_success_handles_empty_model_list(self):
        """Response with empty models list returns empty list."""
        fake_data = {"models": []}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_data
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_ollama_models()

        assert result == []

    async def test_connection_error_returns_empty_list(self):
        """httpx exception causes _get_ollama_models to return []."""
        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.ConnectError("connection refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_ollama_models()

        assert result == []

    async def test_timeout_error_returns_empty_list(self):
        """Timeout exception causes _get_ollama_models to return []."""
        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_ollama_models()

        assert result == []

    async def test_model_without_size_gets_none(self):
        """Model entry missing 'size' key yields size=None."""
        fake_data = {"models": [{"name": "tiny:model"}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_data
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_ollama_models()

        assert result[0]["size"] is None


class TestGenerateOllama:
    """Test generate() routing to _generate_ollama with mocked httpx."""

    async def test_generate_ollama_returns_response_text(self):
        """generate() with ollama model returns the 'response' field."""
        fake_reply = {"response": "Here is the answer."}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await generate("mistral:7b", "What is 2+2?")

        assert result == "Here is the answer."

    async def test_generate_ollama_sends_correct_payload(self):
        """generate() sends correct JSON payload to Ollama."""
        fake_reply = {"response": "ok"}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            await generate("mistral:7b", "Hello", system="You are helpful.")

        call_args = client_instance.post.call_args
        # Payload is passed as the 'json' keyword argument
        payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert payload["model"] == "mistral:7b"
        assert payload["prompt"] == "Hello"
        assert payload["system"] == "You are helpful."
        assert payload["stream"] is False

    async def test_generate_ollama_timeout_propagates(self):
        """TimeoutException from Ollama propagates out of generate()."""
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            with pytest.raises(httpx.TimeoutException):
                await generate("mistral:7b", "hello")


class TestGenerateOpenrouterNoKey:
    """Test _generate_openrouter raises without API key."""

    async def test_no_api_key_raises_value_error(self):
        """_generate_openrouter() raises ValueError when OPENROUTER_API_KEY is empty."""
        with patch("src.llm.client.OPENROUTER_API_KEY", ""):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                await _generate_openrouter("openrouter/llama", "hello", None, 60, None)
