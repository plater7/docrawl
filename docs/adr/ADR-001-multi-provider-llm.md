# ADR-001: Multi-Provider LLM Architecture

**Status:** Accepted  
**Date:** 2025-12 (retroactive)  
**Deciders:** plater7

## Context

DocRawl uses LLMs for two pipeline stages: URL filtering (classifying URLs as documentation vs non-documentation) and markdown cleanup (removing navigation residue, fixing formatting). Initially, only Ollama (local) was supported. Users needed cloud model access for better quality, and some wanted to use LM Studio instead of Ollama for local inference.

## Decision

Implement a provider-agnostic LLM client (`src/llm/client.py`) supporting four providers:

| Provider | Type | Auth | Use Case |
|----------|------|------|----------|
| Ollama | Local | None | Default, development, privacy |
| LM Studio | Local | Optional Bearer | Alternative local inference |
| OpenRouter | Cloud | API key | Production quality, model variety |
| OpenCode | Cloud | API key | Claude/GPT access via proxy |

Provider is auto-detected from model name prefix (e.g., `opencode/claude-sonnet-4-5` routes to OpenCode). Bare model names default to Ollama.

Model lists are cached for 60 seconds (`MODEL_CACHE_TTL`) to avoid repeated API calls during job setup.

## Consequences

**Positive:**
- Users can mix local and cloud models per job (e.g., cheap local model for URL filtering, quality cloud model for cleanup)
- No vendor lock-in — switching providers requires only changing the model name string
- Model validation happens at job start, failing fast before any crawling begins

**Negative:**
- Each provider has different API shapes (Ollama native API vs OpenAI-compatible for others), requiring per-provider code paths in `generate()`
- `options` dict (num_ctx, temperature, etc.) is Ollama-specific; cloud providers ignore most of these parameters
- No unified error handling across providers (timeout behavior, rate limits differ)

**Risks:**
- Cloud provider API changes could break compatibility silently
- Model name prefix convention is implicit — no validation that a model actually exists on the detected provider until runtime