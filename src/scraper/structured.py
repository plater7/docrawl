"""Structured JSON output from HTML pages (PR 3.2).

Converts HTML to a typed block structure instead of plain markdown.
Block types: heading, paragraph, code, table, list, image, blockquote.

Design decisions:
- opt-in via JobRequest.output_format = "json" (default: "markdown")
- No LLM cleanup applied to JSON output (preserves raw content)
- BeautifulSoup parser, recurses into containers (div, section, article, main)
- Output file: same path as markdown but with .json extension
- Atomic write (.tmp → rename)
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BlockType = Literal["heading", "paragraph", "code", "table", "list", "image", "blockquote"]

CONTAINER_TAGS = {"div", "section", "article", "main", "aside", "nav", "header"}


@dataclass
class ContentBlock:
    """A typed content block extracted from HTML."""

    type: BlockType
    content: str
    level: int | None = None  # For headings: 1-6
    language: str | None = None  # For code blocks: detected language
    alt: str | None = None  # For images: alt text


@dataclass
class StructuredPage:
    """Structured representation of a scraped page."""

    url: str
    title: str | None
    blocks: list[ContentBlock]


def _parse_element(el: Tag) -> list[ContentBlock]:
    """Recursively parse an HTML element into ContentBlocks."""
    blocks: list[ContentBlock] = []
    name = el.name if el.name else ""

    # Headings
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        text = el.get_text(separator=" ", strip=True)
        if text:
            blocks.append(ContentBlock(
                type="heading",
                content=text,
                level=int(name[1]),
            ))
        return blocks

    # Code blocks
    if name == "pre":
        code_el = el.find("code")
        if code_el:
            lang = None
            classes = code_el.get("class", [])
            for cls in classes:
                if isinstance(cls, str) and cls.startswith("language-"):
                    lang = cls[len("language-"):]
                    break
            blocks.append(ContentBlock(
                type="code",
                content=code_el.get_text(),
                language=lang,
            ))
        else:
            blocks.append(ContentBlock(type="code", content=el.get_text()))
        return blocks

    # Inline code (standalone)
    if name == "code" and (el.parent is None or el.parent.name != "pre"):
        text = el.get_text()
        if text.strip():
            blocks.append(ContentBlock(type="code", content=text))
        return blocks

    # Tables
    if name == "table":
        rows = []
        for row in el.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True) for td in row.find_all(["td", "th"])]
            rows.append(cells)
        if rows:
            blocks.append(ContentBlock(type="table", content=json.dumps(rows)))
        return blocks

    # Lists
    if name in {"ul", "ol"}:
        items = [li.get_text(separator=" ", strip=True) for li in el.find_all("li", recursive=False)]
        if items:
            blocks.append(ContentBlock(type="list", content="\n".join(items)))
        return blocks

    # Blockquotes
    if name == "blockquote":
        text = el.get_text(separator="\n", strip=True)
        if text:
            blocks.append(ContentBlock(type="blockquote", content=text))
        return blocks

    # Images
    if name == "img":
        src = el.get("src", "")
        alt = el.get("alt", "")
        if src:
            blocks.append(ContentBlock(type="image", content=str(src), alt=str(alt) if alt else None))
        return blocks

    # Paragraphs
    if name == "p":
        text = el.get_text(separator=" ", strip=True)
        if text:
            blocks.append(ContentBlock(type="paragraph", content=text))
        return blocks

    # Container elements — recurse
    if name in CONTAINER_TAGS or name in {"body", "html"}:
        for child in el.children:
            if isinstance(child, Tag):
                blocks.extend(_parse_element(child))
        return blocks

    # Fallback: extract text as paragraph for unrecognised tags.
    # 20-char threshold filters out stray single words / punctuation (e.g. nav labels).
    text = el.get_text(separator=" ", strip=True)
    if text and len(text) > 20:
        blocks.append(ContentBlock(type="paragraph", content=text))

    return blocks


def html_to_structured(url: str, html: str) -> StructuredPage:
    """Parse HTML into a StructuredPage with typed ContentBlocks."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else None

    # Find main content area
    content_el = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find("body")
        or soup
    )

    blocks: list[ContentBlock] = []
    if isinstance(content_el, Tag):
        blocks = _parse_element(content_el)

    return StructuredPage(url=url, title=title, blocks=blocks)


def save_structured(page: StructuredPage, file_path: Path) -> None:
    """Atomically write a StructuredPage as JSON to file_path.

    The file extension should be .json.
    """
    data = {
        "url": page.url,
        "title": page.title,
        "blocks": [asdict(b) for b in page.blocks],
    }
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, file_path)
