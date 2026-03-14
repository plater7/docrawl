"""Job execution orchestration."""

import asyncio
import logging
import os as _os
import time
from dataclasses import dataclass as _dataclass
from pathlib import Path
from urllib.parse import urlparse

from src.jobs.manager import Job
from src.api.models import JobRequest
from src.crawler.discovery import discover_urls
from src.crawler.filter import filter_urls
from src.crawler.robots import RobotsParser
from src.llm.filter import filter_urls_with_llm
from src.llm.cleanup import cleanup_markdown, needs_llm_cleanup
from src.llm.client import get_available_models, get_provider_for_model
from src.scraper.page import (
    PageScraper,
    PagePool,
    fetch_markdown_native,
    fetch_markdown_proxy,
    fetch_html_fast,
)
from src.scraper.markdown import chunk_markdown
from src.scraper.detection import is_blocked_response, content_hash
from src.scraper.cache import PageCache
from src.jobs.state import save_job_state
from src.scraper.structured import (
    html_to_structured,
    save_structured,
    StructuredPage,
    ContentBlock,
)
from src.scraper.converters import get_converter
from src.scraper.converters.base import MarkdownConverter

logger = logging.getLogger(__name__)

MAX_SCRAPE_RETRIES = int(_os.environ.get("SCRAPE_MAX_RETRIES", "2"))


async def validate_models(
    crawl_model: str | None, pipeline_model: str | None, reasoning_model: str | None
) -> list[str]:
    """Validate that all required models are available.

    Returns list of errors, empty if all valid.  None values are skipped.
    """
    errors = []
    models_to_check = [
        ("crawl_model", crawl_model),
        ("pipeline_model", pipeline_model),
        ("reasoning_model", reasoning_model),
    ]

    for field, model in models_to_check:
        if model is None:
            continue
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


async def run_job(
    job: Job,
    page_pool: PagePool | None = None,
    resume_urls: list[str] | None = None,
) -> None:
    """Execute a crawl job with enriched phase/model SSE events.

    page_pool: optional pre-initialized PagePool from main.py lifespan (PR 1.2).
               If None, falls back to the legacy per-page create/close path.
    resume_urls: if provided, skip discovery/filtering and process only these URLs (PR 3.1).
    """
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
    # PR 3.4: resolve converter plugin (None → default "markdownify")
    _converter = get_converter(request.converter)

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

        # Validate models before starting (skip when all models are None — e.g. readerlm + skip_llm_cleanup)
        _any_model = any(
            m is not None
            for m in (
                request.crawl_model,
                request.pipeline_model,
                request.reasoning_model,
            )
        )
        validation_errors = (
            await validate_models(
                request.crawl_model, request.pipeline_model, request.reasoning_model
            )
            if _any_model
            else []
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

        # PR 3.1: skip discovery/filtering when resuming from saved state
        before_llm: float = 0.0
        llm_duration: float = 0.0
        if resume_urls is not None:
            urls = resume_urls
            await _log(
                job,
                "phase_change",
                {
                    "phase": "discovery",
                    "message": f"Resuming from state: {len(urls)} pending URLs (skipping discovery/filtering)",
                },
            )
        else:
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

            # FILTERING phase — LLM (skipped when crawl_model is None)
            before_llm = len(urls)
            if request.crawl_model is not None:
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
            else:
                llm_duration = 0.0

        if request.crawl_model is not None:
            await _log(
                job,
                "log",
                {
                    "phase": "filtering",
                    "active_model": request.crawl_model,
                    "message": f"LLM result: {before_llm} → {len(urls)} URLs ({llm_duration:.1f}s)",
                },
            )
        # end else (full discovery/filtering)

        job.pages_total = len(urls)

        if job.is_cancelled:
            return

        # SCRAPING + CLEANUP phase
        output_path = Path(request.output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        pages_ok = 0
        pages_partial = 0
        pages_failed = 0
        pages_skipped = 0  # PR 2.3: dedup skips
        pages_blocked = 0  # PR 2.3: bot-check pages
        pages_native_md = 0
        pages_proxy_md = 0
        pages_playwright = 0
        pages_http_fast = 0  # PR 1.3

        # PR 2.3: per-job content dedup state
        seen_hashes: set[str] = set()
        _hash_lock = asyncio.Lock()

        # PR 3.1: track completed/failed URLs for pause/resume checkpoint
        completed_urls: list[str] = []
        failed_urls: list[str] = []
        _url_track_lock = asyncio.Lock()

        # PR 2.4: optional page HTML cache
        page_cache: PageCache | None = None
        if request.use_cache:
            cache_dir = output_path / ".cache"
            page_cache = PageCache(cache_dir)

        # Semaphore enforces max_concurrent — closes CONS-010 / issue #56
        sem = asyncio.Semaphore(request.max_concurrent)
        # Lock to protect shared counters and job.pages_completed
        _counter_lock = asyncio.Lock()

        async def _process_page(i: int, url: str) -> None:
            nonlocal pages_ok, pages_partial, pages_failed, pages_skipped, pages_blocked
            nonlocal pages_native_md, pages_proxy_md, pages_playwright, pages_http_fast

            async with sem:
                # PR 3.1: suspend until job is resumed (no-op if running)
                await job.wait_if_paused()

                if job.is_cancelled:
                    return

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
                    raw_html: str | None = None  # PR 3.2: kept for structured output
                    fetch_method = "playwright"
                    load_time = 0.0

                    # PR 2.4: check cache before any network call
                    if page_cache is not None:
                        cached_html = page_cache.get(url)
                        if cached_html is not None:
                            markdown = _converter.convert(cached_html)  # PR 3.4
                            fetch_method = "cache"
                            load_time = time.monotonic() - page_start
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "scraping",
                                    "message": f"[{i + 1}/{len(urls)}] [cache] Served from cache {url} ({load_time:.2f}s)",
                                },
                            )

                    # Try native markdown via content negotiation
                    if request.use_native_markdown:
                        md_content, token_count = await fetch_markdown_native(url)
                        if md_content:
                            markdown = md_content
                            native_token_count = token_count
                            fetch_method = "native"
                            async with _counter_lock:
                                pages_native_md += 1
                            load_time = time.monotonic() - page_start
                            token_info = (
                                f", {token_count} tokens" if token_count else ""
                            )
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
                        proxy_url = request.markdown_proxy_url or "https://markdown.new"
                        md_content, _ = await fetch_markdown_proxy(url, proxy_url)
                        if md_content:
                            markdown = md_content
                            fetch_method = "proxy"
                            async with _counter_lock:
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

                    # HTTP fast-path: try plain HTTP before Playwright (PR 1.3)
                    if markdown is None and request.use_http_fast_path:
                        fast_md = await fetch_html_fast(url)
                        if fast_md:
                            markdown = fast_md
                            fetch_method = "http_fast"
                            async with _counter_lock:
                                pages_http_fast += 1
                            load_time = time.monotonic() - page_start
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "scraping",
                                    "message": f"[{i + 1}/{len(urls)}] [http-fast] Skipped Playwright for {url} ({load_time:.1f}s)",
                                },
                            )

                    # Fall back to Playwright with retries (pass pool if available — PR 1.2)
                    if markdown is None:
                        for _attempt in range(MAX_SCRAPE_RETRIES + 1):
                            try:
                                html = await scraper.get_html(
                                    url,
                                    pool=page_pool,
                                    content_selectors=request.content_selectors,
                                    noise_selectors=request.noise_selectors,
                                )
                                break
                            except asyncio.CancelledError:
                                raise
                            except Exception as _e:
                                if job.is_cancelled:
                                    raise asyncio.CancelledError()
                                if _attempt < MAX_SCRAPE_RETRIES:
                                    _wait = 2**_attempt
                                    logger.warning(
                                        f"Playwright scrape attempt {_attempt + 1}/{MAX_SCRAPE_RETRIES + 1} "
                                        f"failed for {url}: {_e}. Retrying in {_wait}s..."
                                    )
                                    await asyncio.sleep(_wait)
                                else:
                                    raise
                        raw_html = html  # PR 3.2: keep for structured output
                        load_time = time.monotonic() - page_start
                        markdown = _converter.convert(html)  # PR 3.4
                        async with _counter_lock:
                            pages_playwright += 1
                        # PR 2.4: cache the raw HTML (only if not blocked — checked below)
                        if page_cache is not None:
                            if not is_blocked_response(markdown):
                                page_cache.put(url, html)

                    # PR 2.3: check for blocked response (bot-check pages)
                    if is_blocked_response(markdown):
                        async with _counter_lock:
                            job.pages_blocked += 1
                            job.pages_completed += 1
                        await _log(
                            job,
                            "log",
                            {
                                "phase": "scraping",
                                "message": f"[{i + 1}/{len(urls)}] ⚠ blocked response detected, skipping {url}",
                                "level": "warning",
                            },
                        )
                        return

                    # PR 2.3: content dedup — skip near-identical pages
                    h = content_hash(markdown)
                    async with _hash_lock:
                        if h in seen_hashes:
                            async with _counter_lock:
                                job.pages_skipped += 1
                                job.pages_completed += 1
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "scraping",
                                    "message": f"[{i + 1}/{len(urls)}] ⚡ duplicate content, skipping {url}",
                                },
                            )
                            return
                        seen_hashes.add(h)

                    chunks = chunk_markdown(
                        markdown, native_token_count=native_token_count
                    )

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

                    # Skip when the converter already produces clean Markdown (ReaderLM)
                    # or when the caller explicitly opts out via skip_llm_cleanup.
                    _READERLM_CONVERTERS = {"readerlm", "readerlm-v1"}
                    _skip_cleanup = getattr(request, "skip_llm_cleanup", False) or (
                        request.converter in _READERLM_CONVERTERS
                    )
                    # Narrow type for mypy: pipeline_model is non-None when cleanup runs
                    # (enforced by JobRequest.validate_models_required)
                    _pipeline_model: str = request.pipeline_model or ""
                    if request.output_format == "json" or _skip_cleanup:
                        # PR 3.2: skip LLM cleanup entirely for JSON output
                        cleaned_chunks = list(chunks)
                    else:
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

                    for ci, chunk in (
                        enumerate(chunks) if request.output_format != "json" else []
                    ):
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
                            cleaned = await cleanup_markdown(chunk, _pipeline_model)
                            chunk_time = time.monotonic() - chunk_start
                            cleaned_chunks.append(cleaned)

                            if len(chunks) > 1:
                                await _log(
                                    job,
                                    "log",
                                    {
                                        "phase": "cleanup",
                                        "active_model": _pipeline_model,
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
                                    "active_model": _pipeline_model,
                                    "message": f"[{i + 1}/{len(urls)}] Chunk {ci + 1}/{len(chunks)} ✗ failed, using raw",
                                    "level": "warning",
                                },
                            )

                    # Save sub-phase
                    md_file_path = _url_to_filepath(url, base_url, output_path)

                    if request.output_format == "json" or _skip_cleanup:
                        # PR 3.2: structured JSON output — no LLM cleanup
                        if raw_html is not None:
                            structured_page = html_to_structured(url, raw_html)
                        else:
                            structured_page = StructuredPage(
                                url=url,
                                title=None,
                                blocks=[
                                    ContentBlock(type="paragraph", content=markdown)
                                ],
                            )
                        json_path = md_file_path.with_suffix(".json")
                        save_structured(structured_page, json_path)
                        file_size = json_path.stat().st_size
                        file_path = json_path
                        chunks_failed = 0  # JSON output never has chunk failures
                    else:
                        # Default markdown output (atomic write via .tmp + rename — closes issue #99)
                        final_md = "\n\n".join(cleaned_chunks)
                        md_file_path.parent.mkdir(parents=True, exist_ok=True)
                        tmp_path = md_file_path.with_suffix(".tmp")
                        tmp_path.write_text(final_md, encoding="utf-8")
                        tmp_path.rename(md_file_path)
                        file_size = md_file_path.stat().st_size
                        file_path = md_file_path

                    async with _counter_lock:
                        if chunks_failed == 0:
                            pages_ok += 1
                        else:
                            pages_partial += 1
                    async with _url_track_lock:
                        completed_urls.append(url)  # PR 3.1

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
                    async with _counter_lock:
                        pages_failed += 1
                    async with _url_track_lock:
                        failed_urls.append(url)  # PR 3.1
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

                async with _counter_lock:
                    job.pages_completed += 1

                await asyncio.sleep(delay_s)

        # PR 3.3: opt-in pipeline mode (producer/consumer) vs default concurrent scraping
        if request.use_pipeline_mode:
            # Notify UI of scraping phase start (fixes UI stuck on "filtering")
            await _log(
                job,
                "phase_change",
                {
                    "phase": "scraping",
                    "message": f"Processing {len(urls)} pages (pipeline mode)...",
                    "progress": f"0/{len(urls)}",
                },
            )
            (
                pages_ok,
                pages_partial,
                pages_failed,
                pages_native_md,
                pages_proxy_md,
                pages_http_fast,
                pages_playwright,
            ) = await _run_pipeline_mode(
                job=job,
                urls=urls,
                base_url=base_url,
                output_path=output_path,
                request=request,
                scraper=scraper,
                page_pool=page_pool,
                page_cache=page_cache,
                seen_hashes=seen_hashes,
                _hash_lock=_hash_lock,
                completed_urls=completed_urls,
                failed_urls=failed_urls,
                delay_s=delay_s,
                converter=_converter,
            )
        else:
            # Notify UI of scraping phase start before loop (fixes UI stuck on "filtering")
            await _log(
                job,
                "phase_change",
                {
                    "phase": "scraping",
                    "message": f"Processing {len(urls)} pages...",
                    "progress": f"0/{len(urls)}",
                },
            )
            # Launch all pages concurrently, semaphore controls actual parallelism
            await asyncio.gather(*[_process_page(i, url) for i, url in enumerate(urls)])

        # PR 3.1: save final state checkpoint (completed or paused)
        pending_urls = [
            u for u in urls if u not in completed_urls and u not in failed_urls
        ]
        try:
            import json as _json

            save_job_state(
                output_path,
                job_id=job.id,
                request_dict=_json.loads(job.request.model_dump_json()),
                completed_urls=list(completed_urls),
                failed_urls=list(failed_urls),
                pending_urls=pending_urls,
            )
        except Exception as state_err:
            logger.warning(f"Failed to save job state: {state_err}")

        if not job.is_cancelled:
            _generate_index(urls, output_path)

            job.status = "completed"
            job.completed_at = time.time()  # PR 1.5
            await _log(
                job,
                "phase_change",
                {
                    "phase": "done",
                    "message": "Job completed",
                },
            )
            logger.info(
                f"[{job.id[:8]}] Fetch methods: {pages_native_md} native, "
                f"{pages_proxy_md} proxy, {pages_http_fast} http_fast, "
                f"{pages_playwright} playwright"
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
                    "pages_http_fast": pages_http_fast,
                    "pages_playwright": pages_playwright,
                    "pages_skipped": job.pages_skipped,
                    "pages_blocked": job.pages_blocked,
                    "cache_hits": page_cache.hits if page_cache else 0,
                    "cache_misses": page_cache.misses if page_cache else 0,
                    "output_path": str(output_path),
                    "message": f"Done: {pages_ok} ok, {pages_partial} partial, {pages_failed} failed",
                },
            )

    except Exception as e:
        logger.error(f"Job {job.id} failed: {e}")
        job.status = "failed"
        job.completed_at = time.time()  # PR 1.5
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
        rel_path = path or "index"
        lines.append(f"- [{name}]({rel_path}.md)")

    index_path = output_path / "_index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# PR 3.3: Producer / Consumer pipeline
# ---------------------------------------------------------------------------


@_dataclass
class ScrapedPage:
    """Item passed from pipeline producer to consumer (PR 3.3)."""

    index: int
    url: str
    markdown: str
    raw_html: str | None
    native_token_count: int | None
    fetch_method: str
    load_time: float


_PIPELINE_SENTINEL: ScrapedPage | None = None  # signals producer is done


async def _run_pipeline_mode(
    *,
    job: "Job",
    urls: list[str],
    base_url: str,
    output_path: Path,
    request: "JobRequest",
    scraper: "PageScraper",
    page_pool: "PagePool | None",
    page_cache: "PageCache | None",
    seen_hashes: set[str],
    _hash_lock: asyncio.Lock,
    completed_urls: list[str],
    failed_urls: list[str],
    delay_s: float,
    converter: "MarkdownConverter",
) -> tuple[int, int, int, int, int, int, int]:
    """Producer/Consumer pipeline for page fetching + LLM cleanup (PR 3.3).

    Producer: fetches pages concurrently (respecting semaphore), enqueues
              ScrapedPage items.
    Consumer: single coroutine — dedup, LLM cleanup, atomic file save.
    asyncio.Queue(maxsize=20) provides natural backpressure.
    """
    queue: asyncio.Queue[ScrapedPage | None] = asyncio.Queue(maxsize=20)
    sem = asyncio.Semaphore(request.max_concurrent)
    _counter_lock = asyncio.Lock()

    # Shared counters via mutable dict (avoids nonlocal complexity)
    c = {
        "ok": 0,
        "partial": 0,
        "failed": 0,
        "native_md": 0,
        "proxy_md": 0,
        "http_fast": 0,
        "playwright": 0,
    }

    async def _fetch_one(i: int, url: str) -> None:
        async with sem:
            await job.wait_if_paused()
            if job.is_cancelled:
                return
            try:
                page_start = time.monotonic()
                markdown: str | None = None
                raw_html: str | None = None
                fetch_method = "playwright"
                native_token_count: int | None = None

                # PR 2.4: cache hit
                if page_cache is not None:
                    cached_html = page_cache.get(url)
                    if cached_html:
                        raw_html = cached_html
                        markdown = converter.convert(cached_html)  # PR 3.4
                        fetch_method = "cache"

                # Native markdown (Ollama endpoint)
                if markdown is None and request.use_native_markdown:
                    native_md, token_count = await fetch_markdown_native(url)
                    if native_md:
                        markdown = native_md
                        native_token_count = token_count
                        fetch_method = "native"
                        async with _counter_lock:
                            c["native_md"] += 1

                # Markdown proxy
                if markdown is None and request.use_markdown_proxy:
                    proxy_url = request.markdown_proxy_url or "https://markdown.new"
                    md_content, _ = await fetch_markdown_proxy(url, proxy_url)
                    if md_content:
                        markdown = md_content
                        fetch_method = "proxy"
                        async with _counter_lock:
                            c["proxy_md"] += 1

                # HTTP fast-path (PR 1.3)
                if markdown is None and request.use_http_fast_path:
                    fast_md = await fetch_html_fast(url)
                    if fast_md:
                        markdown = fast_md
                        fetch_method = "http_fast"
                        async with _counter_lock:
                            c["http_fast"] += 1

                # Playwright fallback with retries
                if markdown is None:
                    for _attempt in range(MAX_SCRAPE_RETRIES + 1):
                        try:
                            html = await scraper.get_html(
                                url,
                                pool=page_pool,
                                content_selectors=request.content_selectors,
                                noise_selectors=request.noise_selectors,
                            )
                            break
                        except asyncio.CancelledError:
                            raise
                        except Exception as _e:
                            if job.is_cancelled:
                                raise asyncio.CancelledError()
                            if _attempt < MAX_SCRAPE_RETRIES:
                                _wait = 2**_attempt
                                logger.warning(
                                    f"Playwright scrape attempt {_attempt + 1}/{MAX_SCRAPE_RETRIES + 1} "
                                    f"failed for {url}: {_e}. Retrying in {_wait}s..."
                                )
                                await asyncio.sleep(_wait)
                            else:
                                raise
                    raw_html = html
                    markdown = converter.convert(html)  # PR 3.4
                    async with _counter_lock:
                        c["playwright"] += 1
                    if page_cache is not None and not is_blocked_response(markdown):
                        page_cache.put(url, html)

                load_time = time.monotonic() - page_start
                await queue.put(
                    ScrapedPage(
                        index=i,
                        url=url,
                        markdown=markdown,
                        raw_html=raw_html,
                        native_token_count=native_token_count,
                        fetch_method=fetch_method,
                        load_time=load_time,
                    )
                )
            except Exception as e:
                logger.error(f"Job {job.id}: pipeline producer error for {url}: {e}")
                async with _counter_lock:
                    c["failed"] += 1
                    job.pages_completed += 1
            await asyncio.sleep(delay_s)

    async def _producer() -> None:
        try:
            await asyncio.gather(*[_fetch_one(i, url) for i, url in enumerate(urls)])
        finally:
            await queue.put(_PIPELINE_SENTINEL)

    async def _consumer() -> None:
        while True:
            item = await queue.get()
            if item is None:  # _PIPELINE_SENTINEL
                break

            page: ScrapedPage = item
            url = page.url
            markdown = page.markdown

            try:
                # PR 2.3: blocked response check
                if is_blocked_response(markdown):
                    async with _counter_lock:
                        job.pages_blocked += 1
                        job.pages_completed += 1
                    continue

                # PR 2.3: content dedup
                h = content_hash(markdown)
                async with _hash_lock:
                    if h in seen_hashes:
                        async with _counter_lock:
                            job.pages_skipped += 1
                            job.pages_completed += 1
                        continue
                    seen_hashes.add(h)

                file_path = _url_to_filepath(url, base_url, output_path)

                _READERLM_CONVERTERS = {"readerlm", "readerlm-v1"}
                _skip_cleanup = getattr(request, "skip_llm_cleanup", False) or (
                    request.converter in _READERLM_CONVERTERS
                )
                if request.output_format == "json" or _skip_cleanup:  # noqa: F821
                    # PR 3.2: structured JSON — no LLM, skip chunking entirely
                    if page.raw_html is not None:
                        structured_page = html_to_structured(url, page.raw_html)
                    else:
                        structured_page = StructuredPage(
                            url=url,
                            title=None,
                            blocks=[ContentBlock(type="paragraph", content=markdown)],
                        )
                    json_path = file_path.with_suffix(".json")
                    save_structured(structured_page, json_path)
                    completed_urls.append(url)
                    async with _counter_lock:
                        c["ok"] += 1
                        job.pages_completed += 1
                    continue

                # Narrow type for mypy: pipeline_model is non-None when cleanup runs
                # (enforced by JobRequest.validate_models_required)
                _pipeline_model: str = request.pipeline_model or ""
                chunks = chunk_markdown(
                    markdown, native_token_count=page.native_token_count
                )
                chunks_failed = 0
                cleaned_chunks: list[str] = []
                for chunk in chunks:
                    if job.is_cancelled:
                        break
                    try:
                        if needs_llm_cleanup(chunk):
                            cleaned = await cleanup_markdown(chunk, _pipeline_model)
                        else:
                            cleaned = chunk
                        cleaned_chunks.append(cleaned)
                    except Exception as chunk_err:
                        logger.warning(
                            f"Pipeline chunk cleanup failed for {url}: {chunk_err}"
                        )
                        cleaned_chunks.append(chunk)
                        chunks_failed += 1

                final_md = "\n\n".join(cleaned_chunks)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = file_path.with_suffix(".tmp")
                tmp_path.write_text(final_md, encoding="utf-8")
                _os.replace(tmp_path, file_path)

                completed_urls.append(url)
                async with _counter_lock:
                    if chunks_failed == 0:
                        c["ok"] += 1
                    else:
                        c["partial"] += 1
                    job.pages_completed += 1

            except Exception as e:
                logger.error(f"Job {job.id}: pipeline consumer error for {url}: {e}")
                failed_urls.append(url)
                async with _counter_lock:
                    c["failed"] += 1
                    job.pages_completed += 1

    await asyncio.gather(_producer(), _consumer())
    return (
        c["ok"],
        c["partial"],
        c["failed"],
        c["native_md"],
        c["proxy_md"],
        c["http_fast"],
        c["playwright"],
    )
