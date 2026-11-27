"""One HTTP client for every source: timeouts, retries, politeness and a health ledger.

The ledger feeds the colophon, so what the edition says it checked is what was actually requested.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from timeleaf import __version__
from timeleaf.models import Health

HONEST_UA = f"timeleaf/{__version__} (+https://timeleaf.ee/about)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0 Safari/537.36"
)

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class Http:
    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        retries: int = 3,
        min_interval: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client or httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True)
        self.retries = retries
        self.min_interval = min_interval
        self.sleep = sleep
        self.health = Health()
        self._ua = HONEST_UA
        self._last: float = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            self.sleep(wait)
        self._last = time.monotonic()

    def json(self, url: str, body: dict[str, Any] | None = None) -> Any | None:
        """GET (or POST ``body`` as JSON) and decode. Returns None after retries are exhausted."""
        err = "no attempt"
        for attempt in range(self.retries):
            self._throttle()
            headers = {"User-Agent": self._ua, "Accept": "application/json"}
            try:
                if body is None:
                    r = self.client.get(url, headers=headers)
                else:
                    r = self.client.post(url, headers=headers, json=body)
                if r.status_code == 403 and self._ua == HONEST_UA:
                    # Some hosts refuse non-browser agents. Fall back once and say so in the run summary.
                    self._ua = BROWSER_UA
                    self.health.user_agent_fallback = True
                    err = "HTTP 403"
                    continue
                if r.status_code in RETRY_STATUS:
                    err = f"HTTP {r.status_code}"
                elif r.is_error:
                    err = f"HTTP {r.status_code}"
                    break
                else:
                    data = r.json()
                    self.health.ok += 1
                    return data
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                err = type(e).__name__
            self.sleep(min(2**attempt + random.random(), 20))  # noqa: S311 - jitter, not crypto
        self.health.failed.append(f"{url[:90]} ({err})")
        return None

    def close(self) -> None:
        self.client.close()
