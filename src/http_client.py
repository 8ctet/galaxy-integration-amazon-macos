"""Tiny async HTTP client built on the standard library only.

Why stdlib and not aiohttp/requests: GOG Galaxy runs plugins under its bundled
CPython 3.7 (x86_64 on macOS). Native wheels (aiohttp/multidict/yarl) would have
to be compiled for that exact ABI. ``urllib.request`` + ``json`` + ``ssl`` are
all pure stdlib, so the plugin ships with zero native dependencies. Blocking
calls run in the default executor to keep the asyncio loop responsive.
"""

import asyncio
import json as jsonlib
import logging
import ssl
import urllib.error
import urllib.request
from functools import partial

logger = logging.getLogger("amazon_plugin.http")


def build_ssl_context():
    """SSL context that works under Galaxy's bundled Python.framework.

    That interpreter has no usable system CA bundle, so verification fails with
    CERTIFICATE_VERIFY_FAILED unless we point it at certifi's bundle (this is why
    the other Galaxy plugins vendor certifi). Falls back to the system store only
    if certifi is somehow absent.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        logger.warning("certifi unavailable; falling back to system trust store")
        return ssl.create_default_context()


class HttpResponse:
    def __init__(self, status, body_bytes):
        self.status = status
        self._body = body_bytes

    @property
    def ok(self):
        return 200 <= self.status < 300

    def json(self):
        if not self._body:
            return {}
        return jsonlib.loads(self._body.decode("utf-8"))

    @property
    def text(self):
        return self._body.decode("utf-8", "replace") if self._body else ""


class HttpClient:
    """Minimal JSON-oriented HTTP client."""

    def __init__(self, ssl_context=None, total_retries=3):
        self._ssl = ssl_context or build_ssl_context()
        self._retries = total_retries

    async def request(self, method, url, headers=None, json_body=None):
        loop = asyncio.get_event_loop()
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = await loop.run_in_executor(
                    None, partial(self._blocking, method, url, headers, json_body)
                )
            except urllib.error.URLError as exc:
                # DNS / connection / TLS failure: retry a couple of times.
                if attempt > self._retries:
                    logger.error("%s %s failed: %s", method, url, exc)
                    raise
                await asyncio.sleep(min(2 ** attempt, 8))
                continue

            # Retry transient server-side errors and rate limiting.
            if resp.status in (429, 500, 502, 503, 504) and attempt <= self._retries:
                await asyncio.sleep(min(2 ** attempt, 8))
                continue
            return resp

    def _blocking(self, method, url, headers, json_body):
        data = None
        req_headers = dict(headers or {})
        # Some Amazon WAF rules reject the default "Python-urllib/x.y" UA.
        req_headers.setdefault("User-Agent", "AGSLauncher for Windows/1.0.0")
        if json_body is not None:
            data = jsonlib.dumps(json_body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
        try:
            with urllib.request.urlopen(req, context=self._ssl, timeout=30) as r:
                return HttpResponse(r.status, r.read())
        except urllib.error.HTTPError as exc:
            # HTTPError is a response too (4xx/5xx) — read its body for diagnostics.
            body = b""
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001 - best effort
                pass
            return HttpResponse(exc.code, body)
