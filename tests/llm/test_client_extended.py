"""Extended tests for src/llm/client.py.

Covers:
- get_available_models() caching behaviour
- get_available_models() for openrouter / opencode / unknown provider
- _get_openrouter_models() success and failure
- _generate_openrouter() with API key set
- _generate_opencode() with and without API key
- generate() routing to openrouter / opencode / unknown provider
- get_available_models_legacy() / generate_legacy() compatibility wrappers
"""

import time
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.client import (
    _get_openrouter_models,
    _generate_opencode,
    _generate_openrouter,
    generate,
    get_available_models,
    get_available_models_legacy,
    generate_legacy,
    get_provider_for_model,
    _model_cache,
)


# ---------------------------------------------------------------------------
# TestGetAvailableModelsCache
# ---------------------------------------------------------------------------


class TestGetAvailableModelsCache:
    """Test model list caching behaviour in get_available_models()."""

    async def test_opencode_returns_list(self):
        """get_available_models('opencode') returns the static opencode model list."""
        result = await get_available_models("opencode")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(m["provider"] == "opencode" for m in result)

    async def test_unknown_provider_returns_empty_list(self):
        """get_available_models() for an unknown provider returns []."""
        result = await get_available_models("nonexistent_provider_xyz")
        assert result == []

    async def test_cache_hit_avoids_refetch(self):
        """Second call within TTL returns cached result without HTTP call."""
        fake_models = [{"name": "cached:model", "provider": "ollama", "is_free": True}]
        # Manually seed the cache with a fresh entry
        _model_cache["ollama"] = (fake_models, time.monotonic())

        # Should return the cached list without hitting the network
        result = await get_available_models("ollama")
        assert result == fake_models

    async def test_openrouter_on_error_returns_empty(self):
        """get_available_models('openrouter') returns [] when the API errors."""
        # Clear any cached entry so the function makes a real fetch
        _model_cache.pop("openrouter", None)

        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.ConnectError("refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await get_available_models("openrouter")

        assert result == []


# ---------------------------------------------------------------------------
# TestGetOpenrouterModels
# ---------------------------------------------------------------------------


class TestGetOpenrouterModels:
    """Test _get_openrouter_models() with mocked httpx."""

    async def test_success_parses_model_list(self):
        """Successful response is parsed into model dicts."""
        fake_data = {
            "data": [
                {
                    "id": "meta-llama/llama-3-8b:free",
                    "name": "Llama 3 8B (free)",
                    "description": "A free model",
                    "pricing": {"prompt": "0"},
                },
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "description": "Paid model",
                    "pricing": {"prompt": "0.03"},
                },
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
            result = await _get_openrouter_models()

        assert len(result) == 2
        assert result[0]["name"] == "meta-llama/llama-3-8b:free"
        assert result[0]["provider"] == "openrouter"
        assert result[0]["is_free"] is True
        assert result[1]["is_free"] is False

    async def test_free_model_by_zero_pricing(self):
        """Model with prompt price = 0 is marked free even without :free suffix."""
        fake_data = {
            "data": [
                {
                    "id": "some-org/free-model-v1",
                    "name": "Free Model",
                    "description": "",
                    "pricing": {"prompt": "0"},
                }
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
            result = await _get_openrouter_models()

        assert result[0]["is_free"] is True

    async def test_connection_error_returns_empty_list(self):
        """Connection error returns empty list."""
        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.ConnectError("refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_openrouter_models()

        assert result == []

    async def test_empty_data_returns_empty_list(self):
        """Response with empty data array returns empty list."""
        fake_data = {"data": []}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_data
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.httpx.AsyncClient", return_value=client_instance):
            result = await _get_openrouter_models()

        assert result == []


# ---------------------------------------------------------------------------
# TestGenerateOpenrouter
# ---------------------------------------------------------------------------


class TestGenerateOpenrouter:
    """Test _generate_openrouter() with mocked httpx."""

    async def test_success_returns_content(self):
        """Successful response returns the message content."""
        fake_reply = {"choices": [{"message": {"content": "Hello from OpenRouter."}}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.OPENROUTER_API_KEY", "test-key"):
            with patch(
                "src.llm.client.httpx.AsyncClient", return_value=client_instance
            ):
                result = await _generate_openrouter(
                    "openrouter/llama", "What is 2+2?", None, 60, None
                )

        assert result == "Hello from OpenRouter."

    async def test_sends_system_message_when_provided(self):
        """When system is provided, it is included as a system message."""
        fake_reply = {"choices": [{"message": {"content": "ok"}}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.OPENROUTER_API_KEY", "test-key"):
            with patch(
                "src.llm.client.httpx.AsyncClient", return_value=client_instance
            ):
                await _generate_openrouter(
                    "openrouter/llama",
                    "User question",
                    "You are a helper.",
                    60,
                    None,
                )

        call_args = client_instance.post.call_args
        payload = call_args.kwargs.get("json", {})
        messages = payload.get("messages", [])
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles

    async def test_exception_propagates(self):
        """When httpx raises, the exception propagates out."""
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.TimeoutException("timeout")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.OPENROUTER_API_KEY", "test-key"):
            with patch(
                "src.llm.client.httpx.AsyncClient", return_value=client_instance
            ):
                with pytest.raises(httpx.TimeoutException):
                    await _generate_openrouter(
                        "openrouter/llama", "hello", None, 60, None
                    )

    async def test_no_api_key_raises_value_error(self):
        """Raises ValueError when OPENROUTER_API_KEY is not set."""
        with patch("src.llm.client.OPENROUTER_API_KEY", ""):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                await _generate_openrouter("openrouter/llama", "hello", None, 60, None)


# ---------------------------------------------------------------------------
# TestGenerateOpencode
# ---------------------------------------------------------------------------


class TestGenerateOpencode:
    """Test _generate_opencode() with mocked httpx."""

    async def test_no_api_key_raises_value_error(self):
        """Raises ValueError when OPENCODE_API_KEY is not set."""
        with patch("src.llm.client.OPENCODE_API_KEY", ""):
            with pytest.raises(ValueError, match="OPENCODE_API_KEY"):
                await _generate_opencode(
                    "opencode/glm-4.7-free", "hello", None, 60, None
                )

    async def test_success_returns_content(self):
        """Successful response returns the message content."""
        fake_reply = {"choices": [{"message": {"content": "OpenCode response here."}}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.OPENCODE_API_KEY", "oc-key"):
            with patch(
                "src.llm.client.httpx.AsyncClient", return_value=client_instance
            ):
                result = await _generate_opencode(
                    "opencode/glm-4.7-free", "Test prompt", None, 60, None
                )

        assert result == "OpenCode response here."

    async def test_sends_bearer_token(self):
        """Authorization header uses Bearer token format."""
        fake_reply = {"choices": [{"message": {"content": "ok"}}]}
        mock_response = MagicMock()
        mock_response.json.return_value = fake_reply
        mock_response.raise_for_status = MagicMock()

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.OPENCODE_API_KEY", "my-opencode-key"):
            with patch(
                "src.llm.client.httpx.AsyncClient", return_value=client_instance
            ):
                await _generate_opencode(
                    "opencode/glm-4.7-free", "prompt", None, 60, None
                )

        call_args = client_instance.post.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer my-opencode-key"

    async def test_exception_propagates(self):
        """When httpx raises, the exception propagates out."""
        client_instance = AsyncMock()
        client_instance.post.side_effect = RuntimeError("API error")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("src.llm.client.OPENCODE_API_KEY", "oc-key"):
            with patch(
                "src.llm.client.httpx.AsyncClient", return_value=client_instance
            ):
                with pytest.raises(RuntimeError):
                    await _generate_opencode(
                        "opencode/glm-4.7-free", "hello", None, 60, None
                    )


# ---------------------------------------------------------------------------
# TestGenerateRouting
# ---------------------------------------------------------------------------


class TestGenerateRouting:
    """Test generate() routes to the correct provider."""

    async def test_generate_routes_to_openrouter(self):
        """generate() with openrouter/ prefix calls _generate_openrouter."""
        with patch(
            "src.llm.client._generate_openrouter",
            new_callable=AsyncMock,
            return_value="openrouter answer",
        ) as mock:
            result = await generate("openrouter/llama", "hello")

        mock.assert_awaited_once()
        assert result == "openrouter answer"

    async def test_generate_routes_to_opencode(self):
        """generate() with opencode/ prefix calls _generate_opencode."""
        with patch(
            "src.llm.client._generate_opencode",
            new_callable=AsyncMock,
            return_value="opencode answer",
        ) as mock:
            result = await generate("opencode/glm-4.7-free", "hello")

        mock.assert_awaited_once()
        assert result == "opencode answer"

    async def test_generate_routes_to_ollama_for_bare_model(self):
        """generate() with bare model name calls _generate_ollama."""
        with patch(
            "src.llm.client._generate_ollama",
            new_callable=AsyncMock,
            return_value="ollama answer",
        ) as mock:
            result = await generate("mistral:7b", "hello")

        mock.assert_awaited_once()
        assert result == "ollama answer"

    async def test_generate_unknown_provider_raises(self):
        """generate() with an unknown provider prefix raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            # Force get_provider_for_model to return a fake provider
            with patch(
                "src.llm.client.get_provider_for_model", return_value="fakecloud"
            ):
                await generate("fakecloud/model", "hello")


# ---------------------------------------------------------------------------
# TestLegacyWrappers
# ---------------------------------------------------------------------------


class TestLegacyWrappers:
    """Test legacy compatibility wrapper functions."""

    async def test_get_available_models_legacy_calls_get_available_models(self):
        """get_available_models_legacy() delegates to get_available_models('ollama')."""
        fake_models = [{"name": "m", "provider": "ollama", "is_free": True}]
        with patch(
            "src.llm.client.get_available_models",
            new_callable=AsyncMock,
            return_value=fake_models,
        ) as mock:
            result = await get_available_models_legacy()

        mock.assert_awaited_once_with("ollama")
        assert result == fake_models

    async def test_generate_legacy_delegates_to_generate(self):
        """generate_legacy() delegates to generate() with the same arguments."""
        with patch(
            "src.llm.client.generate",
            new_callable=AsyncMock,
            return_value="answer",
        ) as mock:
            result = await generate_legacy("mistral:7b", "prompt", "system", 90)

        mock.assert_awaited_once_with("mistral:7b", "prompt", "system", 90, None)
        assert result == "answer"


# ---------------------------------------------------------------------------
# TestGetProviderForModelEdgeCases
# ---------------------------------------------------------------------------


class TestGetProviderForModelEdgeCases:
    """Additional edge cases for get_provider_for_model()."""

    def test_empty_string_returns_ollama(self):
        """Empty model string defaults to ollama."""
        assert get_provider_for_model("") == "ollama"

    def test_model_with_colon_only_returns_ollama(self):
        """Model name like ':tag' with no namespace returns ollama."""
        assert get_provider_for_model(":latest") == "ollama"

    def test_opencode_namespace_exact_match(self):
        """opencode/ prefix (exact PROVIDERS key) routes to opencode."""
        assert get_provider_for_model("opencode/minimax-m2.5-free") == "opencode"

    def test_openrouter_namespace_exact_match(self):
        """openrouter/ prefix routes to openrouter."""
        assert (
            get_provider_for_model("openrouter/mistral-7b-instruct:free")
            == "openrouter"
        )
