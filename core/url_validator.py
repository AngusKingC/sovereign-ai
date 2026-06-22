"""URL validation to prevent SSRF attacks.

Single responsibility: Validate URLs to block requests to private/internal networks.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


# Private/reserved network ranges that should be blocked
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),        # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),     # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),    # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local
    ipaddress.ip_network("0.0.0.0/8"),         # Current network
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]


def validate_url(url: str) -> str:
    """Validate a URL to prevent SSRF.

    Checks that the URL uses an allowed scheme and does not resolve
    to a private/internal network address.

    Args:
        url: The URL to validate

    Returns:
        The validated URL (unchanged)

    Raises:
        ValueError: If the URL is invalid, uses a disallowed scheme,
            or resolves to a private/internal IP address
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")

    parsed = urlparse(url)

    # Only allow http and https schemes
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed; use http or https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must contain a valid hostname")

    # Resolve hostname to IP and check against blocked networks
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    for addr_info in addr_infos:
        ip = ipaddress.ip_address(addr_info[4][0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(
                    f"URL resolves to private/internal address ({ip}); "
                    "requests to internal networks are blocked"
                )

    return url
