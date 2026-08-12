import io
import urllib.request

import pytest

from specify_cli._github_http import (
    _StripAuthOnRedirect,
    open_github_url,
    read_bounded,
)


class _Response(io.BytesIO):
    def __init__(self, data: bytes, content_length: str | None = None):
        super().__init__(data)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length


def test_read_bounded_accepts_limit_and_rejects_oversized_body():
    assert read_bounded(_Response(b"data"), 4) == b"data"
    with pytest.raises(ValueError, match="exceeds"):
        read_bounded(_Response(b"large"), 4, label="catalog")
    with pytest.raises(ValueError, match="exceeds"):
        read_bounded(_Response(b"", "5"), 4, label="catalog")


def test_redirect_handler_rejects_downgrade_and_strips_cross_host_auth():
    handler = _StripAuthOnRedirect()
    request = urllib.request.Request(
        "https://github.com/example/archive",
        headers={"Authorization": "Bearer secret"},
    )
    with pytest.raises(ValueError, match="unsafe redirect"):
        handler.redirect_request(request, None, 302, "Found", {}, "http://example.com/file")

    redirected = handler.redirect_request(
        request, None, 302, "Found", {}, "https://example.com/file"
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None


def test_open_github_url_uses_safe_redirect_handler_without_auth(monkeypatch):
    captured = {}

    class _Opener:
        def open(self, request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return "response"

    def build_opener(handler):
        captured["handler"] = handler
        return _Opener()

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(urllib.request, "build_opener", build_opener)

    assert open_github_url("https://example.com/catalog.json", timeout=7) == "response"
    assert captured["handler"] is _StripAuthOnRedirect
    assert captured["timeout"] == 7
