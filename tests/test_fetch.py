from __future__ import annotations

import httpx

from tests.conftest import NOW, mock_http, substack_routes
from timeleaf.fetch.collect import collect
from timeleaf.fetch.http import BROWSER_UA, HONEST_UA, Http
from timeleaf.fetch.substack import headings, links, text
from timeleaf.models import Candidates, Sources


def test_text_strips_tags_and_entities() -> None:
    assert text("<p>Hello <b>world</b> &amp; friends</p>", 100) == "Hello world & friends"
    assert text(None, 10) == ""
    assert text("<p>abcdef</p>", 3) == "abc"


def test_links_skip_images_subscribe_and_dedupe() -> None:
    body = (
        '<a href="https://a.example/x/">1</a><a href="https://a.example/x">2</a>'
        '<a href="https://substackcdn.com/i.png">3</a><a href="https://p.example/subscribe">4</a>'
        '<a href="https://a.example/y?utm=1">5</a>'
    )
    assert links({"body_html": body}) == ["https://a.example/x", "https://a.example/y"]


def test_headings() -> None:
    assert headings({"body_html": "<h2>One</h2><p>x</p><h3 id='a'>Two <em>2</em></h3>"}) == ["One", "Two 2"]


def test_collect_friends(candidates: Candidates) -> None:
    ana, ben = candidates.friends
    assert [p.title for p in ana.new_posts] == ["Ana's new post"]
    assert ana.new_posts[0].excerpt == "Hello world & friends"
    assert ben.new_posts == []
    assert ben.latest_post is not None and ben.latest_post.title == "Ben's last post"
    # recommendations: recent like only; own note and comments ignored; duplicates merged
    assert [p.title for p in ana.recommended] == ["Liked essay"]
    assert ana.recommended[0].how == "post_like"
    assert ben.recommended == []


def test_collect_seeds(candidates: Candidates) -> None:
    titles = [s.title for s in candidates.seeds]
    assert titles == ["An essay", "Roundup #1"]  # sorted by date; short and old posts skipped
    essay, roundup = candidates.seeds
    assert essay.paywalled and essay.publication == "Essays Monthly"
    assert roundup.headings == ["The Quest for Sane Regulations", "Rhetorical Innovation"]
    assert "https://news.example/a" in roundup.links
    assert not any("substackcdn" in u or "subscribe" in u for u in roundup.links)


def test_collect_signals_lesswrong_cocited(candidates: Candidates) -> None:
    assert [(s.title, s.via) for s in candidates.signals] == [("Liked essay", "Ana")]
    assert candidates.lesswrong[0].karma == 150
    assert candidates.lesswrong[0].tags == ["AI"]
    assert [(c.url, c.by) for c in candidates.co_cited] == [
        ("https://shared.example/x", ["Essays Monthly", "Roundup Weekly"])
    ]
    assert candidates.health.ok > 10 and candidates.health.failed == []


def test_collect_survives_failures(sources: Sources) -> None:
    http = mock_http(substack_routes(), fail={"/api/v1/user/ana/public_profile", "lesswrong"})
    res = collect(sources, http, days=7, now=NOW)
    assert [f.name for f in res.friends] == ["Ben"]
    assert res.lesswrong == []
    assert len(res.health.failed) == 2
    assert all("HTTP 503" in f for f in res.health.failed)


def test_http_falls_back_to_browser_user_agent_once() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ua = request.headers["User-Agent"]
        seen.append(ua)
        return httpx.Response(403) if ua == HONEST_UA else httpx.Response(200, json={"ok": True})

    http = Http(httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0, sleep=lambda _s: None)
    assert http.json("https://h.example/a") == {"ok": True}
    assert http.json("https://h.example/b") == {"ok": True}
    assert seen == [HONEST_UA, BROWSER_UA, BROWSER_UA]
    assert http.health.user_agent_fallback


def test_http_retries_then_records_failure() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    http = Http(
        httpx.Client(transport=httpx.MockTransport(handler)), retries=3, min_interval=0, sleep=lambda _s: None
    )
    assert http.json("https://h.example/x") is None
    assert calls == 3
    assert http.health.failed == ["https://h.example/x (HTTP 500)"]


def test_http_does_not_retry_client_errors() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    http = Http(httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0, sleep=lambda _s: None)
    assert http.json("https://h.example/x") is None
    assert calls == 1


def test_http_post_json_and_bad_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"got": request.read().decode()})
        return httpx.Response(200, content=b"not json")

    http = Http(
        httpx.Client(transport=httpx.MockTransport(handler)), retries=1, min_interval=0, sleep=lambda _s: None
    )
    assert http.json("https://h.example/q", {"query": "x"}) == {"got": '{"query":"x"}'}
    assert http.json("https://h.example/bad") is None
    assert "JSONDecodeError" in http.health.failed[0]
