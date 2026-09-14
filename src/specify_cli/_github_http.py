"""Shared GitHub-authenticated HTTP helpers.

Used by both ExtensionCatalog and PresetCatalog to attach
GITHUB_TOKEN / GH_TOKEN credentials to requests targeting
GitHub-hosted domains, while preventing token leakage to
third-party hosts on redirects.
"""

import os
import urllib.request
from typing import BinaryIO, Dict
from urllib.parse import urlparse

# GitHub-owned hostnames that should receive the Authorization header.
# Includes codeload.github.com because GitHub archive URL downloads
# (e.g. /archive/refs/tags/<tag>.zip) redirect there and require auth
# for private repositories.
GITHUB_HOSTS = frozenset({
    "raw.githubusercontent.com",
    "github.com",
    "api.github.com",
    "codeload.github.com",
})
MAX_JSON_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_RESPONSE_BYTES = 100 * 1024 * 1024


def read_bounded(response: BinaryIO, max_bytes: int, *, label: str = "response") -> bytes:
    """Read at most ``max_bytes`` and fail if the response is larger."""
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    content_length = getattr(response, "headers", {}).get("Content-Length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise ValueError(f"{label} exceeds the {max_bytes}-byte limit")
        except ValueError as exc:
            if "exceeds" in str(exc):
                raise
    data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"{label} exceeds the {max_bytes}-byte limit")
    return data


def build_github_request(url: str) -> urllib.request.Request:
    """Build a urllib Request, adding a GitHub auth header when available.

    Reads GITHUB_TOKEN or GH_TOKEN from the environment and attaches an
    ``Authorization: Bearer <value>`` header when the target hostname is one
    of the known GitHub-owned domains. Non-GitHub URLs are returned as plain
    requests so credentials are never leaked to third-party hosts.

    Raises:
        ValueError: If ``url`` is empty or whitespace-only.
        ValueError: If ``url`` does not use the ``http`` or ``https`` scheme.
        ValueError: If ``url`` does not include a hostname.
    """
    headers: Dict[str, str] = {}
    url = url.strip()
    if not url:
        raise ValueError("url must not be empty")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"url must start with http:// or https://, got: {url!r}")
    if not parsed.hostname:
        raise ValueError(f"url must include a hostname, got: {url!r}")
    # Validate explicit ports before constructing a credential-bearing request.
    parsed.port
    github_token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    gh_token = (os.environ.get("GH_TOKEN") or "").strip()
    token = github_token or gh_token or None
    hostname = parsed.hostname.lower()
    if token and hostname in GITHUB_HOSTS:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect handler that drops the Authorization header when leaving GitHub.

    Prevents token leakage to CDNs or other third-party hosts that GitHub
    may redirect to (e.g. S3 for release asset downloads, objects.githubusercontent.com).
    Auth is preserved as long as the redirect target remains within GITHUB_HOSTS.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        is_localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and is_localhost
        ):
            raise ValueError(f"Refusing unsafe redirect target: {newurl}")
        original_auth = req.get_header("Authorization")
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            hostname = (urlparse(newurl).hostname or "").lower()
            if hostname in GITHUB_HOSTS:
                if original_auth:
                    new_req.add_unredirected_header("Authorization", original_auth)
            else:
                new_req.headers.pop("Authorization", None)
                new_req.unredirected_hdrs.pop("Authorization", None)
        return new_req


def open_github_url(url: str, timeout: int = 10):
    """Open a URL with GitHub auth, stripping the header on cross-host redirects.

    When the request carries an Authorization header, a custom redirect
    handler drops that header if the redirect target is not a GitHub-owned
    domain, preventing token leakage to CDNs or other third-party hosts
    that GitHub may redirect to (e.g. S3 for release asset downloads).
    """
    req = build_github_request(url)

    opener = urllib.request.build_opener(_StripAuthOnRedirect)
    return opener.open(req, timeout=timeout)
