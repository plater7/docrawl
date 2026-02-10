"""Job execution orchestration."""

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

from src.jobs.manager import Job
from src.crawler.discovery import discover_urls
from src.crawler.filter import filter_urls
from src.crawler.robots import RobotsParser
from src.llm.filter import filter_urls_with_llm
from src.llm.cleanup import cleanup_markdown
from src.scraper.page import PageScraper
from src.scraper.markdown import html_to_markdown, chunk_markdown

logger = logging.getLogger(__name__)


async def run_job(job: Job) -> None:
    """Execute a crawl job."""
    job.status = "running"
    request = job.request
    base_url = str(request.url)

    scraper = PageScraper()
    robots = RobotsParser()

    try:
        await scraper.start()

        # Load robots.txt if requested
        if request.respect_robots_txt:
            await robots.load(base_url)
            if robots.crawl_delay:
                delay_s = max(request.delay_ms / 1000, robots.crawl_delay)
            else:
                delay_s = request.delay_ms / 1000
        else:
            delay_s = request.delay_ms / 1000

        # Discovery phase
        await job.emit_event("discovery", {"phase": "starting", "status": "trying"})
        urls = await discover_urls(base_url, request.max_depth)
        await job.emit_event("discovery", {"phase": "done", "urls_found": len(urls)})

        if job.is_cancelled:
            return

        # Filtering phase
        await job.emit_event("filtering", {"phase": "basic", "total": len(urls)})
        urls = filter_urls(urls, base_url)

        if request.respect_robots_txt:
            urls = [u for u in urls if robots.is_allowed(u)]

        await job.emit_event("filtering", {"phase": "llm", "after_basic": len(urls)})
        urls = await filter_urls_with_llm(urls, request.model)
        await job.emit_event("filtering", {"phase": "done", "after_llm": len(urls)})

        job.pages_total = len(urls)

        if job.is_cancelled:
            return

        # Scraping phase
        output_path = Path(request.output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        pages_ok = 0
        pages_partial = 0
        pages_failed = 0

        for i, url in enumerate(urls):
            if job.is_cancelled:
                break

            job.current_url = url
            await job.emit_event("page_start", {
                "url": url,
                "index": i + 1,
                "total": len(urls),
            })

            try:
                # Scrape page
                html = await scraper.get_html(url)
                markdown = html_to_markdown(html)

                # Chunk and cleanup
                chunks = chunk_markdown(markdown)
                cleaned_chunks: list[str] = []
                chunks_failed = 0

                for chunk in chunks:
                    if job.is_cancelled:
                        break
                    try:
                        cleaned = await cleanup_markdown(chunk, request.model)
                        cleaned_chunks.append(cleaned)
                    except Exception:
                        chunks_failed += 1
                        cleaned_chunks.append(chunk)  # Use raw on failure

                # Save to file
                final_md = "\n\n".join(cleaned_chunks)
                file_path = _url_to_filepath(url, base_url, output_path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(final_md, encoding="utf-8")

                if chunks_failed == 0:
                    pages_ok += 1
                    status = "ok"
                else:
                    pages_partial += 1
                    status = "partial"

                await job.emit_event("page_done", {
                    "url": url,
                    "status": status,
                    "chunks_failed": chunks_failed,
                    "chunks_total": len(chunks),
                })

            except Exception as e:
                pages_failed += 1
                logger.error(f"Failed to process {url}: {e}")
                await job.emit_event("page_error", {"url": url, "error": str(e)})

            job.pages_completed = i + 1
            await asyncio.sleep(delay_s)

        if not job.is_cancelled:
            # Generate index
            _generate_index(urls, output_path)

            job.status = "completed"
            await job.emit_event("job_done", {
                "status": "completed",
                "pages_ok": pages_ok,
                "pages_partial": pages_partial,
                "pages_failed": pages_failed,
                "output_path": str(output_path),
            })

    except Exception as e:
        logger.error(f"Job failed: {e}")
        job.status = "failed"
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
