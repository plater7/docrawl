"""Job execution orchestration.

🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.
"""

import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

from src.jobs.manager import Job
from src.crawler.discovery import discover_urls
from src.crawler.filter import filter_urls
from src.crawler.robots import RobotsParser
from src.llm.filter import filter_urls_with_llm
from src.llm.cleanup import cleanup_markdown, needs_llm_cleanup
from src.llm.client import get_available_models, get_provider_for_model
from src.scraper.page import PageScraper, fetch_markdown_native, fetch_markdown_proxy
from src.scraper.markdown import html_to_markdown, chunk_markdown

logger = logging.getLogger(__name__)


async def validate_models(
    crawl_model: str, pipeline_model: str, reasoning_model: str
) -> list[str]:
    """Validate that all required models are available.

    Returns list of errors, empty if all valid.
    """
    errors = []
    models_to_check = [
        ("crawl_model", crawl_model),
        ("pipeline_model", pipeline_model),
        ("reasoning_model", reasoning_model),
    ]

    for field, model in models_to_check:
        provider = get_provider_for_model(model)

        try:
            available = await get_available_models(provider)
            model_names = [m["name"] for m in available]

            # For Ollama, check exact match or base model name
            if provider == "ollama":
                # Handle model names with tags (e.g., mistral:7b vs mistral:latest)
                base_model = model.split(":")[0]
                found = any(
                    m == model
                    or m == f"{base_model}:latest"
                    or m.startswith(f"{base_model}:")
                    for m in model_names
                )
                if not found and model_names:
                    errors.append(
                        f"Model '{model}' not found. Available: {', '.join(model_names[:5])}{'...' if len(model_names) > 5 else ''}"
                    )
            # For API providers, we trust the model list (they have many models)
            # Just check that we got a response
            elif not available and provider in ["openrouter", "opencode"]:
                errors.append(
                    f"Cannot verify model '{model}' - check {provider} API key"
                )

        except Exception as e:
            errors.append(f"Failed to validate {field} '{model}': {e}")

    return errors


async def _log(job: Job, event_type: str, data: dict) -> None:
    """Emit SSE event and log the message to stdout."""
    await job.emit_event(event_type, data)
    msg = data.get("message", "")
    if msg:
        phase = data.get("phase", "")
        model = data.get("active_model", "")
        level = data.get("level", "")
        prefix = f"[{job.id[:8]}] [{phase}]" if phase else f"[{job.id[:8]}]"
        suffix = f" [{model}]" if model else ""
        full_msg = f"{prefix} {msg}{suffix}"
        if level == "error":
            logger.error(full_msg)
        elif level == "warning":
            logger.warning(full_msg)
        else:
            logger.info(full_msg)


async def run_job(job: Job) -> None:
    """Execute a crawl job with enriched phase/model SSE events."""
    # TODO: reasoning_model will be used for:
    # - Site structure analysis before crawling
    # - Complex content filtering (language selection, cross-page dedup)
    # - Documentation quality assessment
    # Currently unused, passed through for future pipeline stages
    job.status = "running"
    request = job.request
    base_url = str(request.url)

    scraper = PageScraper()
    robots = RobotsParser()

    try:
        # INIT phase
        await _log(
            job,
            "phase_change",
            {
                "phase": "init",
                "message": "Validating models...",
            },
        )

        # Validate models before starting
        validation_errors = await validate_models(
            request.crawl_model, request.pipeline_model, request.reasoning_model
        )
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            await _log(
                job,
                "log",
                {
                    "phase": "init",
                    "message": f"Model validation failed: {error_msg}",
                    "level": "error",
                },
            )
            job.status = "failed"
            await job.emit_event(
                "job_done",
                {
                    "status": "failed",
                    "error": f"Model validation failed: {error_msg}",
                },
            )
            return

        await _log(
            job,
            "phase_change",
            {
                "phase": "init",
                "message": "Initializing browser...",
            },
        )
        await scraper.start()
        await _log(
            job,
            "phase_change",
            {
                "phase": "init",
                "message": "Browser ready",
            },
        )

        # Robots.txt
        if request.respect_robots_txt:
            await robots.load(base_url)
            if robots.crawl_delay:
                delay_s = max(request.delay_ms / 1000, robots.crawl_delay)
                await _log(
                    job,
                    "log",
                    {
                        "phase": "init",
                        "message": f"robots.txt loaded (crawl-delay: {robots.crawl_delay}s, using {delay_s}s)",
                    },
                )
            else:
                delay_s = request.delay_ms / 1000
                await _log(
                    job,
                    "log",
                    {
                        "phase": "init",
                        "message": "robots.txt loaded (no crawl-delay)",
                    },
                )
        else:
            delay_s = request.delay_ms / 1000

        # DISCOVERY phase
        phase_start = time.monotonic()
        await _log(
            job,
            "phase_change",
            {
                "phase": "discovery",
                "message": "Crawling site structure...",
            },
        )

        urls = await discover_urls(
            base_url, request.max_depth, request.filter_sitemap_by_path
        )

        discovery_time = time.monotonic() - phase_start
        await _log(
            job,
            "log",
            {
                "phase": "discovery",
                "message": f"Found {len(urls)} URLs ({discovery_time:.1f}s)",
            },
        )

        if job.is_cancelled:
            return

        # FILTERING phase — basic
        phase_start = time.monotonic()
        total_before = len(urls)
        await _log(
            job,
            "phase_change",
            {
                "phase": "filtering",
                "message": "Applying basic filters...",
            },
        )

        urls = filter_urls(urls, base_url, request.language)
        after_basic = len(urls)
        removed_basic = total_before - after_basic
        await _log(
            job,
            "log",
            {
                "phase": "filtering",
                "message": f"Basic filtering: {total_before} → {after_basic} URLs (removed {removed_basic} non-doc)",
            },
        )

        # Robots.txt filtering
        if request.respect_robots_txt:
            before_robots = len(urls)
            urls = [u for u in urls if robots.is_allowed(u)]
            removed_robots = before_robots - len(urls)
            if removed_robots > 0:
                await _log(
                    job,
                    "log",
                    {
                        "phase": "filtering",
                        "message": f"robots.txt: {before_robots} → {len(urls)} URLs (blocked {removed_robots})",
                    },
                )

        # FILTERING phase — LLM
        before_llm = len(urls)
        await _log(
            job,
            "phase_change",
            {
                "phase": "filtering",
                "active_model": request.crawl_model,
                "message": f"LLM filtering with {request.crawl_model}...",
            },
        )

        llm_start = time.monotonic()
        urls = await filter_urls_with_llm(urls, request.crawl_model)
        llm_duration = time.monotonic() - llm_start

        await _log(
            job,
            "log",
            {
                "phase": "filtering",
                "active_model": request.crawl_model,
                "message": f"LLM result: {before_llm} → {len(urls)} URLs ({llm_duration:.1f}s)",
            },
        )

        job.pages_total = len(urls)

        if job.is_cancelled:
            return

        # SCRAPING + CLEANUP phase
        output_path = Path(request.output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        pages_ok = 0
        pages_partial = 0
        pages_failed = 0
        pages_native_md = 0
        pages_proxy_md = 0
        pages_playwright = 0

        for i, url in enumerate(urls):
            if job.is_cancelled:
                break

            job.current_url = url
            page_start = time.monotonic()

            # Scraping sub-phase
            await _log(
                job,
                "phase_change",
                {
                    "phase": "scraping",
                    "message": "Loading page...",
                    "progress": f"{i + 1}/{len(urls)}",
                    "url": url,
                },
            )

            try:
                markdown = None
                native_token_count = None
                fetch_method = "playwright"
                load_time = 0.0

                # Try native markdown via content negotiation
                if request.use_native_markdown:
                    md_content, token_count = await fetch_markdown_native(url)
                    if md_content:
                        markdown = md_content
                        native_token_count = token_count
                        fetch_method = "native"
                        pages_native_md += 1
                        load_time = time.monotonic() - page_start
                        token_info = f", {token_count} tokens" if token_count else ""
                        await _log(
                            job,
                            "log",
                            {
                                "phase": "scraping",
                                "message": f"[{i + 1}/{len(urls)}] [native-md] Skipped Playwright for {url} ({load_time:.1f}s{token_info})",
                            },
                        )

                # Try markdown proxy as fallback
                if markdown is None and request.use_markdown_proxy:
                    md_content, _ = await fetch_markdown_proxy(
                        url, request.markdown_proxy_url
                    )
                    if md_content:
                        markdown = md_content
                        fetch_method = "proxy"
                        pages_proxy_md += 1
                        load_time = time.monotonic() - page_start
                        await _log(
                            job,
                            "log",
                            {
                                "phase": "scraping",
                                "message": f"[{i + 1}/{len(urls)}] [proxy-md] Fetched via proxy for {url} ({load_time:.1f}s)",
                            },
                        )

                # Fall back to Playwright
                if markdown is None:
                    html = await scraper.get_html(url)
                    load_time = time.monotonic() - page_start
                    markdown = html_to_markdown(html)
                    pages_playwright += 1

                chunks = chunk_markdown(markdown, native_token_count=native_token_count)

                await _log(
                    job,
                    "log",
                    {
                        "phase": "scraping",
                        "message": f"[{i + 1}/{len(urls)}] Loaded {url} ({load_time:.1f}s, {len(chunks)} chunks, {fetch_method})",
                    },
                )

                # Cleanup sub-phase
                cleaned_chunks: list[str] = []
                chunks_failed = 0
                _cleanup_start = time.monotonic()

                await _log(
                    job,
                    "phase_change",
                    {
                        "phase": "cleanup",
                        "active_model": request.pipeline_model,
                        "message": f"Cleaning {len(chunks)} chunks...",
                        "progress": f"{i + 1}/{len(urls)}",
                        "url": url,
                    },
                )

                for ci, chunk in enumerate(chunks):
                    if job.is_cancelled:
                        break

                    # Skip LLM cleanup for already-clean chunks
                    if not needs_llm_cleanup(chunk):
                        cleaned_chunks.append(chunk)
                        if len(chunks) > 1:
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "cleanup",
                                    "message": f"[{i + 1}/{len(urls)}] Chunk {ci + 1}/{len(chunks)} ⚡ skip (clean)",
                                },
                            )
                        continue

                    try:
                        chunk_start = time.monotonic()
                        cleaned = await cleanup_markdown(chunk, request.pipeline_model)
                        chunk_time = time.monotonic() - chunk_start
                        cleaned_chunks.append(cleaned)

                        # Only log individual chunks if more than 1
                        if len(chunks) > 1:
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "cleanup",
                                    "active_model": request.pipeline_model,
                                    "message": f"[{i + 1}/{len(urls)}] Chunk {ci + 1}/{len(chunks)} ✓ ({chunk_time:.1f}s)",
                                },
                            )
                    except Exception:
                        chunks_failed += 1
                        cleaned_chunks.append(chunk)
                        await _log(
                            job,
                            "log",
                            {
                                "phase": "cleanup",
                                "active_model": request.pipeline_model,
                                "message": f"[{i + 1}/{len(urls)}] Chunk {ci + 1}/{len(chunks)} ✗ failed, using raw",
                                "level": "warning",
                            },
                        )

                # Save sub-phase
                final_md = "\n\n".join(cleaned_chunks)
                file_path = _url_to_filepath(url, base_url, output_path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(final_md, encoding="utf-8")
                file_size = file_path.stat().st_size

                if chunks_failed == 0:
                    pages_ok += 1
                else:
                    pages_partial += 1

                size_str = (
                    f"{file_size / 1024:.1f} KB"
                    if file_size >= 1024
                    else f"{file_size} B"
                )
                rel_path = str(file_path.relative_to(output_path))

                await _log(
                    job,
                    "log",
                    {
                        "phase": "save",
                        "message": f"[{i + 1}/{len(urls)}] → {rel_path} ({size_str})"
                        + (
                            f" ⚠ {chunks_failed} chunks failed"
                            if chunks_failed > 0
                            else " ✓"
                        ),
                    },
                )

            except Exception as e:
                pages_failed += 1
                page_time = time.monotonic() - page_start
                logger.error(f"Failed to process {url}: {e}")
                await _log(
                    job,
                    "log",
                    {
                        "phase": "scraping",
                        "message": f"[{i + 1}/{len(urls)}] ✗ {url}: {e} ({page_time:.1f}s)",
                        "level": "error",
                    },
                )

            job.pages_completed = i + 1
            await asyncio.sleep(delay_s)

        if not job.is_cancelled:
            _generate_index(urls, output_path)

            job.status = "completed"
            await _log(
                job,
                "phase_change",
                {
                    "phase": "done",
                    "message": "Job completed",
                },
            )
            await _log(
                job,
                "job_done",
                {
                    "status": "completed",
                    "pages_ok": pages_ok,
                    "pages_partial": pages_partial,
                    "pages_failed": pages_failed,
                    "pages_native_md": pages_native_md,
                    "pages_proxy_md": pages_proxy_md,
                    "pages_playwright": pages_playwright,
                    "output_path": str(output_path),
                    "message": f"Done: {pages_ok} ok, {pages_partial} partial, {pages_failed} failed",
                },
            )

    except Exception as e:
        logger.error(f"Job {job.id} failed: {e}")
        job.status = "failed"
        try:
            await job.emit_event(
                "phase_change",
                {
                    "phase": "failed",
                    "message": str(e),
                },
            )
            await job.emit_event("job_done", {"status": "failed", "error": str(e)})
        except Exception as emit_err:
            logger.error(f"Job {job.id}: failed to emit error event: {emit_err}")
    finally:
        # Stop browser — catch errors so they don't prevent terminal event
        try:
            await scraper.stop()
        except Exception as stop_err:
            logger.error(f"Job {job.id}: failed to stop browser: {stop_err}")

        # Safety net: if job is still "running", something went wrong
        # Emit terminal event so event_stream doesn't block forever
        if job.status == "running":
            job.status = "failed"
            try:
                await job.emit_event(
                    "job_done",
                    {
                        "status": "failed",
                        "error": "Job ended without proper completion",
                    },
                )
            except Exception:
                pass


def _url_to_filepath(url: str, base_url: str, output_path: Path) -> Path:
    """Convert URL to file path, preserving structure."""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    # Get relative path from base
    path = parsed.path
    base_path = base_parsed.path.rstrip("/")
    if path.startswith(base_path):
        path = path[len(base_path) :]

    path = path.strip("/")
    if not path:
        path = "index"

    # Remove any extension and add .md
    if "." in path.split("/")[-1]:
        path = path.rsplit(".", 1)[0]

    return output_path / f"{path}.md"


def _generate_index(urls: list[str], output_path: Path) -> None:
    """Generate _index.md with table of contents."""
    lines = ["# Documentation Index\n"]

    for url in urls:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        name = path.split("/")[-1] or "Home"
        rel_path = path.replace("/", "_") or "index"
        lines.append(f"- [{name}]({rel_path}.md)")

    index_path = output_path / "_index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
