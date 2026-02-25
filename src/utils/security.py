"""Shared security utilities — SSRF validation."""

import ipaddress
import socket
from urllib.parse import urlparse

# Private/reserved network ranges
PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_url_not_ssrf(url: str) -> None:
    """Raise ValueError if the URL resolves to a private/internal address.

    Closes CONS-002 / issue #51 (SSRF via Playwright).
    """
    host = urlparse(url).hostname
    if not host:
        raise ValueError(f"URL has no hostname: {url}")
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(host))
        if any(addr in net for net in PRIVATE_NETS):
            raise ValueError(f"URL targets private/internal address: {url}")
    except socket.gaierror:
        pass  # DNS doesn't resolve — let it fail naturally later
