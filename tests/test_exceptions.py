"""Unit tests for src/exceptions.py — exception class hierarchy.

Covers every concrete exception class, __str__ formatting, and the
user_hint / message attributes.
"""

from src.exceptions import (
    CrawlError,
    DiskSpaceError,
    DocrawlError,
    LLMConnectionError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    ModelNotFoundError,
    OllamaNotRunningError,
    PermissionDeniedError,
    ProviderNotConfiguredError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# TestDocrawlError
# ---------------------------------------------------------------------------


class TestDocrawlError:
    """Base DocrawlError class tests."""

    def test_message_stored(self):
        """message attribute holds the constructor argument."""
        err = DocrawlError("something went wrong")
        assert err.message == "something went wrong"

    def test_user_hint_none_by_default(self):
        """user_hint defaults to None when not provided."""
        err = DocrawlError("msg")
        assert err.user_hint is None

    def test_user_hint_stored_when_provided(self):
        """user_hint is stored when passed."""
        err = DocrawlError("msg", user_hint="Try this")
        assert err.user_hint == "Try this"

    def test_str_without_hint_returns_message(self):
        """__str__ returns just the message when no hint is set."""
        err = DocrawlError("just message")
        assert str(err) == "just message"

    def test_str_with_hint_includes_hint(self):
        """__str__ includes the hint line when user_hint is set."""
        err = DocrawlError("Something broke", user_hint="Do the thing")
        result = str(err)
        assert "Something broke" in result
        assert "Hint: Do the thing" in result

    def test_is_exception_subclass(self):
        """DocrawlError is a subclass of Exception."""
        assert issubclass(DocrawlError, Exception)

    def test_can_be_raised_and_caught(self):
        """DocrawlError can be raised and caught as Exception."""
        caught = False
        try:
            raise DocrawlError("test error")
        except Exception:
            caught = True
        assert caught


# ---------------------------------------------------------------------------
# TestOllamaNotRunningError
# ---------------------------------------------------------------------------


class TestOllamaNotRunningError:
    """Tests for OllamaNotRunningError."""

    def test_default_url_in_message(self):
        """Default URL (localhost:11434) appears in the error message."""
        err = OllamaNotRunningError()
        assert "localhost:11434" in err.message

    def test_custom_url_in_message(self):
        """Custom URL passed to constructor appears in the error message."""
        err = OllamaNotRunningError(url="http://remote:11434")
        assert "remote:11434" in err.message

    def test_hint_mentions_ollama_serve(self):
        """user_hint suggests running 'ollama serve'."""
        err = OllamaNotRunningError()
        assert "ollama serve" in err.user_hint

    def test_is_docrawl_error_subclass(self):
        """OllamaNotRunningError inherits from DocrawlError."""
        assert issubclass(OllamaNotRunningError, DocrawlError)

    def test_str_contains_message_and_hint(self):
        """__str__ includes both message and hint."""
        err = OllamaNotRunningError()
        result = str(err)
        assert "Ollama" in result
        assert "ollama serve" in result


# ---------------------------------------------------------------------------
# TestModelNotFoundError
# ---------------------------------------------------------------------------


class TestModelNotFoundError:
    """Tests for ModelNotFoundError."""

    def test_model_name_in_message(self):
        """The model name appears in the error message."""
        err = ModelNotFoundError("mistral:7b")
        assert "mistral:7b" in err.message

    def test_provider_in_message(self):
        """Provider name appears in the error message."""
        err = ModelNotFoundError("gpt-4", provider="openai")
        assert "openai" in err.message

    def test_ollama_hint_mentions_pull(self):
        """For 'ollama' provider, hint includes 'ollama pull <model>'."""
        err = ModelNotFoundError("llama3:8b", provider="ollama")
        assert "ollama pull" in err.user_hint
        assert "llama3:8b" in err.user_hint

    def test_non_ollama_provider_hint_mentions_api_key(self):
        """For non-ollama providers, hint mentions API key configuration."""
        err = ModelNotFoundError("gpt-4", provider="openai")
        assert "API key" in err.user_hint or "api key" in err.user_hint.lower()

    def test_default_provider_is_ollama(self):
        """Default provider is 'ollama'."""
        err = ModelNotFoundError("mistral:7b")
        assert "ollama" in err.message

    def test_is_docrawl_error_subclass(self):
        """ModelNotFoundError inherits from DocrawlError."""
        assert issubclass(ModelNotFoundError, DocrawlError)


# ---------------------------------------------------------------------------
# TestDiskSpaceError
# ---------------------------------------------------------------------------


class TestDiskSpaceError:
    """Tests for DiskSpaceError."""

    def test_free_gb_in_message(self):
        """The available free_gb appears in the error message."""
        err = DiskSpaceError(free_gb=0.5)
        assert "0.50" in err.message

    def test_required_gb_in_message(self):
        """The required_gb appears in the error message."""
        err = DiskSpaceError(free_gb=0.5, required_gb=2.0)
        assert "2.0" in err.message

    def test_default_required_gb_is_one(self):
        """Default required_gb is 1.0 GB."""
        err = DiskSpaceError(free_gb=0.1)
        assert "1.0" in err.message

    def test_hint_mentions_free_space(self):
        """user_hint instructs user to free disk space."""
        err = DiskSpaceError(free_gb=0.1)
        assert (
            "disk space" in err.user_hint.lower() or "output" in err.user_hint.lower()
        )

    def test_is_docrawl_error_subclass(self):
        """DiskSpaceError inherits from DocrawlError."""
        assert issubclass(DiskSpaceError, DocrawlError)


# ---------------------------------------------------------------------------
# TestPermissionDeniedError
# ---------------------------------------------------------------------------


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError."""

    def test_path_in_message(self):
        """The directory path appears in the error message."""
        err = PermissionDeniedError("/data/output")
        assert "/data/output" in err.message

    def test_hint_mentions_chown(self):
        """user_hint suggests using chown to fix permissions."""
        err = PermissionDeniedError("/data")
        assert "chown" in err.user_hint

    def test_is_docrawl_error_subclass(self):
        """PermissionDeniedError inherits from DocrawlError."""
        assert issubclass(PermissionDeniedError, DocrawlError)

    def test_str_includes_path(self):
        """__str__ includes the path in the output."""
        err = PermissionDeniedError("/some/path")
        assert "/some/path" in str(err)


# ---------------------------------------------------------------------------
# TestProviderNotConfiguredError
# ---------------------------------------------------------------------------


class TestProviderNotConfiguredError:
    """Tests for ProviderNotConfiguredError."""

    def test_provider_in_message(self):
        """Provider name appears in the error message."""
        err = ProviderNotConfiguredError("openai", "OPENAI_API_KEY")
        assert "openai" in err.message

    def test_missing_key_in_message(self):
        """The missing configuration key appears in the error message."""
        err = ProviderNotConfiguredError("openrouter", "OPENROUTER_API_KEY")
        assert "OPENROUTER_API_KEY" in err.message

    def test_hint_mentions_env_file(self):
        """user_hint directs user to the .env file."""
        err = ProviderNotConfiguredError("openrouter", "OPENROUTER_API_KEY")
        assert ".env" in err.user_hint

    def test_hint_includes_key_name(self):
        """user_hint includes the missing key name."""
        err = ProviderNotConfiguredError("myservice", "MY_API_KEY")
        assert "MY_API_KEY" in err.user_hint

    def test_is_docrawl_error_subclass(self):
        """ProviderNotConfiguredError inherits from DocrawlError."""
        assert issubclass(ProviderNotConfiguredError, DocrawlError)


# ---------------------------------------------------------------------------
# TestCrawlError
# ---------------------------------------------------------------------------


class TestCrawlError:
    """Tests for CrawlError."""

    def test_message_stored(self):
        """The base message is stored and accessible."""
        err = CrawlError("fetch failed")
        assert "fetch failed" in err.message

    def test_url_appended_to_message(self):
        """When url is provided, it is appended to the message."""
        err = CrawlError("fetch failed", url="https://example.com/page")
        assert "https://example.com/page" in err.message

    def test_no_url_does_not_include_url_label(self):
        """When url is None, the message does not include '(URL: ...)'."""
        err = CrawlError("generic failure")
        assert "URL:" not in err.message

    def test_is_docrawl_error_subclass(self):
        """CrawlError inherits from DocrawlError."""
        assert issubclass(CrawlError, DocrawlError)

    def test_no_user_hint(self):
        """CrawlError does not set a user_hint by default."""
        err = CrawlError("something")
        assert err.user_hint is None


# ---------------------------------------------------------------------------
# TestValidationError
# ---------------------------------------------------------------------------


class TestValidationError:
    """Tests for ValidationError."""

    def test_field_in_message(self):
        """The field name appears in the error message."""
        err = ValidationError("url", "must be HTTPS")
        assert "url" in err.message

    def test_reason_in_message(self):
        """The reason appears in the error message."""
        err = ValidationError("url", "must be HTTPS")
        assert "must be HTTPS" in err.message

    def test_hint_mentions_field(self):
        """user_hint references the field name."""
        err = ValidationError("output_path", "must start with /data")
        assert "output_path" in err.user_hint

    def test_is_docrawl_error_subclass(self):
        """ValidationError inherits from DocrawlError."""
        assert issubclass(ValidationError, DocrawlError)

    def test_str_output(self):
        """__str__ includes both the message and the hint."""
        err = ValidationError("delay_ms", "must be >= 100")
        result = str(err)
        assert "delay_ms" in result
        assert "must be >= 100" in result


# ---------------------------------------------------------------------------
# TestExceptionHierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """All custom exceptions share the DocrawlError / Exception hierarchy."""

    def test_all_subclasses_caught_as_docrawl_error(self):
        """All concrete exceptions can be caught with DocrawlError."""
        exceptions = [
            OllamaNotRunningError(),
            ModelNotFoundError("m"),
            DiskSpaceError(0.5),
            PermissionDeniedError("/path"),
            ProviderNotConfiguredError("p", "KEY"),
            CrawlError("e"),
            ValidationError("f", "r"),
        ]
        for exc in exceptions:
            caught = False
            try:
                raise exc
            except DocrawlError:
                caught = True
            assert caught, f"{type(exc).__name__} not caught as DocrawlError"

    def test_all_subclasses_caught_as_exception(self):
        """All concrete exceptions can be caught with the built-in Exception."""
        exceptions = [
            OllamaNotRunningError(),
            ModelNotFoundError("m"),
            DiskSpaceError(0.5),
            PermissionDeniedError("/path"),
            ProviderNotConfiguredError("p", "KEY"),
            CrawlError("e"),
            ValidationError("f", "r"),
        ]
        for exc in exceptions:
            caught = False
            try:
                raise exc
            except Exception:
                caught = True
            assert caught, f"{type(exc).__name__} not caught as Exception"


# ---------------------------------------------------------------------------
# TestLLMProviderError
# ---------------------------------------------------------------------------


class TestLLMProviderError:
    """Tests for LLMProviderError base class."""

    def test_provider_attribute_stored(self):
        """provider attribute holds the constructor argument."""
        err = LLMProviderError("base error", provider="ollama")
        assert err.provider == "ollama"

    def test_message_stored(self):
        """message attribute holds the constructor argument."""
        err = LLMProviderError("something went wrong", provider="openai")
        assert err.message == "something went wrong"

    def test_user_hint_none_by_default(self):
        """user_hint defaults to None when not provided."""
        err = LLMProviderError("msg", provider="openai")
        assert err.user_hint is None

    def test_user_hint_stored_when_provided(self):
        """user_hint is stored when explicitly passed."""
        err = LLMProviderError("msg", provider="openai", user_hint="Check config")
        assert err.user_hint == "Check config"

    def test_is_docrawl_error_subclass(self):
        """LLMProviderError inherits from DocrawlError."""
        assert issubclass(LLMProviderError, DocrawlError)

    def test_str_with_hint_includes_both(self):
        """__str__ includes message and hint when both are set."""
        err = LLMProviderError("failed", provider="openai", user_hint="Try again")
        result = str(err)
        assert "failed" in result
        assert "Hint: Try again" in result

    def test_str_without_hint_returns_message_only(self):
        """__str__ returns only the message when no user_hint is set."""
        err = LLMProviderError("connection dropped", provider="ollama")
        assert str(err) == "connection dropped"

    def test_is_exception_subclass(self):
        """LLMProviderError is a subclass of the built-in Exception."""
        assert issubclass(LLMProviderError, Exception)

    def test_can_be_raised_and_caught(self):
        """LLMProviderError can be raised and caught as DocrawlError."""
        caught = False
        try:
            raise LLMProviderError("boom", provider="openai")
        except DocrawlError:
            caught = True
        assert caught


# ---------------------------------------------------------------------------
# TestLLMConnectionError
# ---------------------------------------------------------------------------


class TestLLMConnectionError:
    """Tests for LLMConnectionError."""

    def test_provider_in_message_no_detail(self):
        """Provider name appears in message when no detail is given."""
        err = LLMConnectionError(provider="ollama")
        assert "ollama" in err.message

    def test_message_no_detail_has_no_colon_suffix(self):
        """Message does not include a colon suffix when detail is empty string."""
        err = LLMConnectionError(provider="ollama", detail="")
        assert err.message == "Cannot connect to ollama"

    def test_detail_appended_to_message(self):
        """Non-empty detail is appended to the message after a colon."""
        err = LLMConnectionError(provider="ollama", detail="conn refused")
        assert "conn refused" in err.message
        assert ": conn refused" in err.message

    def test_provider_attribute_set(self):
        """provider attribute is set correctly."""
        err = LLMConnectionError(provider="openai")
        assert err.provider == "openai"

    def test_hint_mentions_provider(self):
        """user_hint references the provider name."""
        err = LLMConnectionError(provider="mistral")
        assert "mistral" in err.user_hint

    def test_is_llm_provider_error_subclass(self):
        """LLMConnectionError inherits from LLMProviderError."""
        assert issubclass(LLMConnectionError, LLMProviderError)

    def test_is_docrawl_error_subclass(self):
        """LLMConnectionError inherits from DocrawlError."""
        assert issubclass(LLMConnectionError, DocrawlError)

    def test_message_exact_format_no_detail(self):
        """Message is exactly 'Cannot connect to {provider}' when no detail given."""
        err = LLMConnectionError(provider="openai")
        assert err.message == "Cannot connect to openai"

    def test_str_contains_message_and_hint(self):
        """__str__ includes both the connection message and the hint."""
        err = LLMConnectionError(provider="ollama")
        result = str(err)
        assert "Cannot connect to ollama" in result
        assert "Hint:" in result


# ---------------------------------------------------------------------------
# TestLLMTimeoutError
# ---------------------------------------------------------------------------


class TestLLMTimeoutError:
    """Tests for LLMTimeoutError."""

    def test_provider_in_message(self):
        """Provider name appears in the error message."""
        err = LLMTimeoutError(provider="ollama", timeout_s=30)
        assert "ollama" in err.message

    def test_timeout_value_in_message(self):
        """The timeout value appears in the error message."""
        err = LLMTimeoutError(provider="ollama", timeout_s=30)
        assert "30" in err.message

    def test_float_timeout_in_message(self):
        """Float timeout values are included in the message."""
        err = LLMTimeoutError(provider="openai", timeout_s=12.5)
        assert "12.5" in err.message

    def test_default_timeout_is_zero(self):
        """Default timeout_s of 0 is reflected in the message."""
        err = LLMTimeoutError(provider="ollama")
        assert "0" in err.message

    def test_hint_mentions_timeout_or_model(self):
        """user_hint advises increasing timeout or using a smaller model."""
        err = LLMTimeoutError(provider="ollama", timeout_s=10)
        assert "timeout" in err.user_hint.lower() or "model" in err.user_hint.lower()

    def test_is_llm_provider_error_subclass(self):
        """LLMTimeoutError inherits from LLMProviderError."""
        assert issubclass(LLMTimeoutError, LLMProviderError)

    def test_is_docrawl_error_subclass(self):
        """LLMTimeoutError inherits from DocrawlError."""
        assert issubclass(LLMTimeoutError, DocrawlError)

    def test_message_has_s_suffix_on_timeout(self):
        """Timeout value in message is followed by the 's' seconds suffix."""
        err = LLMTimeoutError(provider="ollama", timeout_s=30)
        assert "30s" in err.message

    def test_str_contains_hint(self):
        """__str__ includes the user_hint for timeout errors."""
        err = LLMTimeoutError(provider="openai", timeout_s=60)
        result = str(err)
        assert "Hint:" in result


# ---------------------------------------------------------------------------
# TestLLMRateLimitError
# ---------------------------------------------------------------------------


class TestLLMRateLimitError:
    """Tests for LLMRateLimitError."""

    def test_provider_in_message(self):
        """Provider name appears in the error message."""
        err = LLMRateLimitError(provider="openai")
        assert "openai" in err.message

    def test_retry_after_none_by_default(self):
        """retry_after attribute is None when not provided."""
        err = LLMRateLimitError(provider="openai")
        assert err.retry_after is None

    def test_retry_after_stored_when_provided(self):
        """retry_after attribute holds the provided integer value."""
        err = LLMRateLimitError(provider="openai", retry_after=30)
        assert err.retry_after == 30

    def test_hint_with_retry_after_includes_seconds(self):
        """user_hint includes the retry_after value in seconds when set."""
        err = LLMRateLimitError(provider="openai", retry_after=30)
        assert "30" in err.user_hint
        assert "Retry after" in err.user_hint

    def test_hint_without_retry_after_is_generic(self):
        """user_hint falls back to a generic wait message when retry_after is None."""
        err = LLMRateLimitError(provider="openai", retry_after=None)
        assert "Wait" in err.user_hint or "retry" in err.user_hint.lower()

    def test_is_llm_provider_error_subclass(self):
        """LLMRateLimitError inherits from LLMProviderError."""
        assert issubclass(LLMRateLimitError, LLMProviderError)

    def test_is_docrawl_error_subclass(self):
        """LLMRateLimitError inherits from DocrawlError."""
        assert issubclass(LLMRateLimitError, DocrawlError)

    def test_retry_after_zero_treated_as_falsy(self):
        """retry_after=0 is falsy so hint falls back to the generic wait message."""
        err = LLMRateLimitError(provider="openai", retry_after=0)
        assert "Wait" in err.user_hint or "retry" in err.user_hint.lower()
        assert "0s" not in err.user_hint

    def test_str_contains_hint(self):
        """__str__ includes the user_hint for rate-limit errors."""
        err = LLMRateLimitError(provider="openai")
        result = str(err)
        assert "Hint:" in result


# ---------------------------------------------------------------------------
# TestLLMExceptionHierarchy
# ---------------------------------------------------------------------------


def _assert_catches(exc: BaseException, exc_type: type) -> None:
    """Assert that raising *exc* is caught by an ``except exc_type`` clause."""
    caught = False
    try:
        raise exc
    except exc_type:
        caught = True
    assert caught, f"{type(exc).__name__} not caught as {exc_type.__name__}"


def _assert_not_catches(exc: BaseException, exc_type: type) -> None:
    """Assert that raising *exc* is NOT caught by an ``except exc_type`` clause."""
    caught = False
    try:
        try:
            raise exc
        except exc_type:
            caught = True
    except type(exc):
        pass  # propagated as expected
    assert not caught, f"{type(exc).__name__} should not be caught as {exc_type.__name__}"


class TestLLMExceptionHierarchy:
    """LLM provider exceptions share the LLMProviderError / DocrawlError hierarchy."""

    _LLM_EXCEPTIONS = [
        LLMConnectionError("ollama"),
        LLMConnectionError("ollama", detail="conn refused"),
        LLMTimeoutError("openai", timeout_s=10),
        LLMRateLimitError("openai"),
        LLMRateLimitError("openai", retry_after=60),
    ]

    def test_all_llm_subclasses_caught_as_llm_provider_error(self):
        """All LLM concrete exceptions can be caught with LLMProviderError."""
        for exc in self._LLM_EXCEPTIONS:
            _assert_catches(exc, LLMProviderError)

    def test_all_llm_subclasses_caught_as_docrawl_error(self):
        """All LLM concrete exceptions can be caught with DocrawlError."""
        for exc in self._LLM_EXCEPTIONS:
            _assert_catches(exc, DocrawlError)

    def test_all_llm_subclasses_caught_as_exception(self):
        """All LLM concrete exceptions can be caught with the built-in Exception."""
        for exc in self._LLM_EXCEPTIONS:
            _assert_catches(exc, Exception)

    def test_llm_errors_not_caught_as_unrelated_docrawl_subclass(self):
        """LLM errors are not accidentally caught by unrelated DocrawlError subclasses."""
        _assert_not_catches(LLMConnectionError(provider="ollama"), OllamaNotRunningError)

    def test_different_llm_subtypes_not_interchangeable(self):
        """LLMTimeoutError is not caught by an except clause for LLMConnectionError."""
        _assert_not_catches(LLMTimeoutError(provider="openai", timeout_s=5), LLMConnectionError)
