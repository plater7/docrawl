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
- No vendor lock-in -- switching providers requires only changing the model name string
- Model validation happens at job start, failing fast before any crawling begins

**Negative:**
- Each provider has different API shapes (Ollama native API vs OpenAI-compatible for others), requiring per-provider code paths in `generate()`
- `options` dict (num_ctx, temperature, etc.) is Ollama-specific; cloud providers ignore most of these parameters
- No unified error handling across providers (timeout behavior, rate limits differ)

**Risks:**
- Cloud provider API changes could break compatibility silently
- Model name prefix convention is implicit -- no validation that a model actually exists on the detected provider until runtime

---

## Addendum: LM Studio (v0.9.10, PR #154)

**Date:** 2026-03-09  
**Status:** Accepted

### Context

LM Studio provides an OpenAI-compatible local inference server, popular among users who prefer its GUI-based model management over Ollama's CLI approach. Adding LM Studio as a 4th provider was requested to support users already running it.

### Decision

Add LM Studio as a new provider in the existing multi-provider architecture:

- **Endpoint**: Configurable via `LMSTUDIO_URL` (default: `http://localhost:1234/v1`)
- **Auth**: Optional Bearer token via `LMSTUDIO_API_KEY` (default: `lm-studio`)
- **Detection**: Model names prefixed with `lmstudio/` route to LM Studio
- **API**: Uses the same OpenAI-compatible code path as OpenRouter/OpenCode
- **Health check**: New `/api/health/lmstudio` endpoint added
- **UI**: Provider selector updated with LM Studio option + status dot

### Consequences

**Positive:**
- Minimal code change -- LM Studio reuses the OpenAI-compatible client path
- Users get a GUI-based local alternative to Ollama
- Health check endpoint enables monitoring

**Negative:**
- LM Studio's `localhost:1234` default conflicts with some development setups
- When running in Docker, requires `host.docker.internal` mapping (same as Ollama)

**No new risks** beyond those already identified for the multi-provider architecture.
