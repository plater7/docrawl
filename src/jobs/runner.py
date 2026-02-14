"""Job execution orchestration."""

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
from src.scraper.page import PageScraper
from src.scraper.markdown import html_to_markdown, chunk_markdown

logger = logging.getLogger(__name__)


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
        await _log(job, "phase_change", {
            "phase": "init",
            "message": "Initializing browser...",
        })
        await scraper.start()
        await _log(job, "phase_change", {
            "phase": "init",
            "message": "Browser ready",
        })

        # Robots.txt
        if request.respect_robots_txt:
            await robots.load(base_url)
            if robots.crawl_delay:
                delay_s = max(request.delay_ms / 1000, robots.crawl_delay)
                await _log(job, "log", {
                    "phase": "init",
                    "message": f"robots.txt loaded (crawl-delay: {robots.crawl_delay}s, using {delay_s}s)",
                })
            else:
                delay_s = request.delay_ms / 1000
                await _log(job, "log", {
                    "phase": "init",
                    "message": "robots.txt loaded (no crawl-delay)",
                })
        else:
            delay_s = request.delay_ms / 1000

        # DISCOVERY phase
        phase_start = time.monotonic()
        await _log(job, "phase_change", {
            "phase": "discovery",
            "message": "Crawling site structure...",
        })

        urls = await discover_urls(base_url, request.max_depth)

        discovery_time = time.monotonic() - phase_start
        await _log(job, "log", {
            "phase": "discovery",
            "message": f"Found {len(urls)} URLs ({discovery_time:.1f}s)",
        })

        if job.is_cancelled:
            return

        # FILTERING phase — basic
        phase_start = time.monotonic()
        total_before = len(urls)
        await _log(job, "phase_change", {
            "phase": "filtering",
            "message": "Applying basic filters...",
        })

        urls = filter_urls(urls, base_url)
        after_basic = len(urls)
        removed_basic = total_before - after_basic
        await _log(job, "log", {
            "phase": "filtering",
            "message": f"Basic filtering: {total_before} → {after_basic} URLs (removed {removed_basic} non-doc)",
        })

        # Robots.txt filtering
        if request.respect_robots_txt:
            before_robots = len(urls)
            urls = [u for u in urls if robots.is_allowed(u)]
            removed_robots = before_robots - len(urls)
            if removed_robots > 0:
                await _log(job, "log", {
                    "phase": "filtering",
                    "message": f"robots.txt: {before_robots} → {len(urls)} URLs (blocked {removed_robots})",
                })

        # FILTERING phase — LLM
        before_llm = len(urls)
        await _log(job, "phase_change", {
            "phase": "filtering",
            "active_model": request.crawl_model,
            "message": f"LLM filtering with {request.crawl_model}...",
        })

        llm_start = time.monotonic()
        urls = await filter_urls_with_llm(urls, request.crawl_model)
        llm_duration = time.monotonic() - llm_start

        await _log(job, "log", {
            "phase": "filtering",
            "active_model": request.crawl_model,
            "message": f"LLM result: {before_llm} → {len(urls)} URLs ({llm_duration:.1f}s)",
        })

        job.pages_total = len(urls)

        if job.is_cancelled:
            return

        # SCRAPING + CLEANUP phase
        output_path = Path(request.output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        pages_ok = 0
        pages_partial = 0
        pages_failed = 0

        for i, url in enumerate(urls):
            if job.is_cancelled:
                break

            job.current_url = url
            page_start = time.monotonic()

            # Scraping sub-phase
            await _log(job, "phase_change", {
                "phase": "scraping",
                "message": "Loading page...",
                "progress": f"{i + 1}/{len(urls)}",
                "url": url,
            })

            try:
                html = await scraper.get_html(url)
                load_time = time.monotonic() - page_start
                markdown = html_to_markdown(html)
                chunks = chunk_markdown(markdown)

                await _log(job, "log", {
                    "phase": "scraping",
                    "message": f"[{i+1}/{len(urls)}] Loaded {url} ({load_time:.1f}s, {len(chunks)} chunks)",
                })

                # Cleanup sub-phase
                cleaned_chunks: list[str] = []
                chunks_failed = 0
                cleanup_start = time.monotonic()

                await _log(job, "phase_change", {
                    "phase": "cleanup",
                    "active_model": request.pipeline_model,
                    "message": f"Cleaning {len(chunks)} chunks...",
                    "progress": f"{i + 1}/{len(urls)}",
                    "url": url,
                })

                for ci, chunk in enumerate(chunks):
                    if job.is_cancelled:
                        break

                    # Skip LLM cleanup for already-clean chunks
                    if not needs_llm_cleanup(chunk):
                        cleaned_chunks.append(chunk)
                        if len(chunks) > 1:
                            await _log(job, "log", {
                                "phase": "cleanup",
                                "message": f"[{i+1}/{len(urls)}] Chunk {ci+1}/{len(chunks)} ⚡ skip (clean)",
                            })
                        continue

                    try:
                        chunk_start = time.monotonic()
                        cleaned = await cleanup_markdown(chunk, request.pipeline_model)
                        chunk_time = time.monotonic() - chunk_start
                        cleaned_chunks.append(cleaned)

                        # Only log individual chunks if more than 1
                        if len(chunks) > 1:
                            await _log(job, "log", {
                                "phase": "cleanup",
                                "active_model": request.pipeline_model,
                                "message": f"[{i+1}/{len(urls)}] Chunk {ci+1}/{len(chunks)} ✓ ({chunk_time:.1f}s)",
                            })
                    except Exception as e:
                        chunks_failed += 1
                        cleaned_chunks.append(chunk)
                        await _log(job, "log", {
                            "phase": "cleanup",
                            "active_model": request.pipeline_model,
                            "message": f"[{i+1}/{len(urls)}] Chunk {ci+1}/{len(chunks)} ✗ failed, using raw",
                            "level": "warning",
                        })

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

                size_str = f"{file_size / 1024:.1f} KB" if file_size >= 1024 else f"{file_size} B"
                rel_path = str(file_path.relative_to(output_path))

                await _log(job, "log", {
                    "phase": "save",
                    "message": f"[{i+1}/{len(urls)}] → {rel_path} ({size_str})" + (f" ⚠ {chunks_failed} chunks failed" if chunks_failed > 0 else " ✓"),
                })

            except Exception as e:
                pages_failed += 1
                page_time = time.monotonic() - page_start
                logger.error(f"Failed to process {url}: {e}")
                await _log(job, "log", {
                    "phase": "scraping",
                    "message": f"[{i+1}/{len(urls)}] ✗ {url}: {e} ({page_time:.1f}s)",
                    "level": "error",
                })

            job.pages_completed = i + 1
            await asyncio.sleep(delay_s)

        if not job.is_cancelled:
            _generate_index(urls, output_path)

            job.status = "completed"
            await _log(job, "phase_change", {
                "phase": "done",
                "message": "Job completed",
            })
            await _log(job, "job_done", {
                "status": "completed",
                "pages_ok": pages_ok,
                "pages_partial": pages_partial,
                "pages_failed": pages_failed,
                "output_path": str(output_path),
                "message": f"Done: {pages_ok} ok, {pages_partial} partial, {pages_failed} failed",
            })

    except Exception as e:
        logger.error(f"Job {job.id} failed: {e}")
        job.status = "failed"
        await job.emit_event("phase_change", {
            "phase": "failed",
            "message": str(e),
        })
        await job.emit_event("job_done", {"status": "failed", "error": str(e)})
    finally:
        await scraper.stop()


def _url_to_filepath(url: str, base_url: str, output_path: Path) -> Path:
    """Convert URL to file path, preserving structure."""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    # Get relative path from base
    path = parsed.path
    base_path = base_parsed.path.rstrip("/")
    if path.startswith(base_path):
        path = path[len(base_path):]

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
