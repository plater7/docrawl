"""robots.txt parser."""

import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class RobotsParser:
    """Simple robots.txt parser supporting Disallow and Allow directives."""

    def __init__(self) -> None:
        self.disallowed: list[str] = []
        self.allowed: list[str] = []
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
                elif line.startswith("allow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        self.allowed.append(path)
                elif line.startswith("crawl-delay:"):
                    try:
                        self.crawl_delay = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass

    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt.

        Uses specificity-based precedence: the longest matching rule wins.
        If Allow and Disallow tie on length, Allow wins (RFC 9309 §2.2.2).
        """
        parsed = urlparse(url)
        path = parsed.path

        best_disallow_len: int | None = None
        for rule in self.disallowed:
            if path.startswith(rule):
                if best_disallow_len is None or len(rule) > best_disallow_len:
                    best_disallow_len = len(rule)

        best_allow_len: int | None = None
        for rule in self.allowed:
            if path.startswith(rule):
                if best_allow_len is None or len(rule) > best_allow_len:
                    best_allow_len = len(rule)

        # No rule matched at all -> allowed
        if best_disallow_len is None and best_allow_len is None:
            return True

        # Only allow matched -> allowed
        if best_disallow_len is None:
            return True

        # Only disallow matched -> blocked
        if best_allow_len is None:
            return False

        # Both matched: Allow wins on tie or when more specific
        return best_allow_len >= best_disallow_len
