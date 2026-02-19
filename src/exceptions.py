"""Custom exceptions for Docrawl with user-friendly messages.

🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.
"""


class DocrawlError(Exception):
    """Base exception for Docrawl errors."""
    
    def __init__(self, message: str, user_hint: str | None = None):
        self.message = message
        self.user_hint = user_hint
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.user_hint:
            return f"{self.message}\n  Hint: {self.user_hint}"
        return self.message


class OllamaNotRunningError(DocrawlError):
    """Ollama service is not reachable."""
    
    def __init__(self, url: str = "http://localhost:11434"):
        super().__init__(
            message=f"Cannot connect to Ollama at {url}",
            user_hint="Start Ollama with: ollama serve"
        )


class ModelNotFoundError(DocrawlError):
    """Requested model is not available."""
    
    def __init__(self, model: str, provider: str = "ollama"):
        hint = f"Pull the model with: ollama pull {model}"
        if provider != "ollama":
            hint = f"Check that your API key is configured for {provider}"
        super().__init__(
            message=f"Model '{model}' not found on {provider}",
            user_hint=hint
        )


class DiskSpaceError(DocrawlError):
    """Insufficient disk space."""
    
    def __init__(self, free_gb: float, required_gb: float = 1.0):
        super().__init__(
            message=f"Low disk space: {free_gb:.2f}GB free (need {required_gb}GB)",
            user_hint="Free up disk space or change output directory"
        )


class PermissionDeniedError(DocrawlError):
    """Cannot write to output directory."""
    
    def __init__(self, path: str):
        super().__init__(
            message=f"Permission denied writing to {path}",
            user_hint="Run: sudo chown -R $USER:$USER ./data"
        )


class ProviderNotConfiguredError(DocrawlError):
    """API provider is missing required configuration."""
    
    def __init__(self, provider: str, missing_key: str):
        super().__init__(
            message=f"{provider} requires {missing_key} to be set",
            user_hint=f"Add {missing_key} to your .env file"
        )


class CrawlError(DocrawlError):
    """Generic error during crawl operation."""
    
    def __init__(self, message: str, url: str | None = None):
        full_msg = f"{message}" + (f" (URL: {url})" if url else "")
        super().__init__(message=full_msg)


class ValidationError(DocrawlError):
    """Input validation error."""
    
    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Invalid {field}: {reason}",
            user_hint=f"Check the {field} field in the form"
        )
