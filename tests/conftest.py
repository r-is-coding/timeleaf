"""Shared fixtures. Network is never used in tests: Substack and LessWrong are served by a MockTransport.

Two readers appear in tests. ``richard`` is the real one in ``readers/`` (the owner's paper, edition 1).
``juniper`` is an invented person in ``tests/fixtures/readers/``, whose sources are the mocked routes.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from timeleaf import readers as rd
from timeleaf.fetch.http import Http
from timeleaf.models import Candidates, Edition, Sources
from timeleaf.readers import ReaderHome

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
READERS = ROOT / "readers"
FIXTURE_READERS = FIXTURES / "readers"
EDITION1 = READERS / "richard/editions/2026-11-27.json"
NOW = dt.datetime(2026, 11, 27, 6, 0, tzinfo=dt.UTC)


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def richard() -> ReaderHome:
    return rd.load(READERS, "richard")


@pytest.fixture
def juniper() -> ReaderHome:
    return rd.load(FIXTURE_READERS, "juniper")


@pytest.fixture
def sources(juniper: ReaderHome) -> Sources:
    return juniper.sources


@pytest.fixture
def edition1() -> Edition:
    return Edition.model_validate_json(EDITION1.read_text(encoding="utf-8"))


@pytest.fixture
def two_readers(tmp_path: Path) -> Path:
    """A readers folder holding the owner's real paper and the invented second reader."""
    root = tmp_path / "readers"
    shutil.copytree(READERS / "richard", root / "richard")
    shutil.copytree(FIXTURE_READERS / "juniper", root / "juniper")
    return root


def substack_routes() -> dict[str, Any]:
    return load("substack_routes.json")  # type: ignore[no-any-return]


def mock_http(routes: dict[str, Any], *, fail: set[str] | None = None) -> Http:
    """An Http whose requests are answered from ``routes``.

    Keys are path+query for substack.com, host+path+query for a publication's own host, and
    "lesswrong" for the GraphQL endpoint.
    """
    fail = fail or set()

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.raw_path.decode()
        if request.url.host == "www.lesswrong.com":
            key = "lesswrong"
        elif request.url.host != "substack.com":
            key = request.url.host + key
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
