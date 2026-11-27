"""Shared fixtures. Network is never used in tests: Substack and LessWrong are served by a MockTransport."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from timeleaf.fetch.http import Http
from timeleaf.models import Candidates, Edition, Sources

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
NOW = dt.datetime(2026, 11, 27, 6, 0, tzinfo=dt.UTC)


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def sources() -> Sources:
    return Sources.model_validate(load("sources.json"))


@pytest.fixture
def edition1() -> Edition:
    return Edition.model_validate_json(
        (ROOT / "content/editions/2026-11-27.json").read_text(encoding="utf-8")
    )


def substack_routes() -> dict[str, Any]:
    return load("substack_routes.json")  # type: ignore[no-any-return]


def mock_http(routes: dict[str, Any], *, fail: set[str] | None = None) -> Http:
    """An Http whose requests are answered from ``routes`` (path+query -> JSON)."""
    fail = fail or set()

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.raw_path.decode()
        if request.url.host == "www.lesswrong.com":
            key = "lesswrong"
        if key in fail:
            return httpx.Response(503)
        if key not in routes:
            return httpx.Response(404, json={"error": "not found", "path": key})
        return httpx.Response(200, json=routes[key])

    return Http(httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0, sleep=lambda _s: None)


@pytest.fixture
def http_factory() -> Callable[..., Http]:
    return mock_http


@pytest.fixture
def candidates(sources: Sources) -> Candidates:
    from timeleaf.fetch.collect import collect

    return collect(sources, mock_http(substack_routes()), days=7, now=NOW)
