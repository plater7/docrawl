"""robots.txt parser."""

import logging
from urllib.parse import urlparse, urljoin

import httpx

logger = logging.getLogger(__name__)


class RobotsParser:
    """Simple robots.txt parser."""

    def __init__(self) -> None:
        self.disallowed: list[str] = []
        self.crawl_delay: float | None = None

    async def load(self, base_url: str) -> bool:
        """Load and parse robots.txt from base URL."""
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(robots_url, timeout=10)
                if response.status_code != 200:
                    return False

                self._parse(response.text)
                return True
        except Exception as e:
            logger.warning(f"Failed to load robots.txt: {e}")
            return False

    def _parse(self, content: str) -> None:
        """Parse robots.txt content."""
        in_user_agent_all = False

        for line in content.splitlines():
            line = line.strip().lower()

            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_user_agent_all = agent == "*"
            elif in_user_agent_all:
                if line.startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        self.disallowed.append(path)
                elif line.startswith("crawl-delay:"):
                    try:
                        self.crawl_delay = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass

    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        parsed = urlparse(url)
        path = parsed.path

        for disallowed in self.disallowed:
            if path.startswith(disallowed):
                return False
        return True
