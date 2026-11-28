from __future__ import annotations

import httpx

from tests.conftest import NOW, mock_http, substack_routes
from timeleaf.fetch.collect import collect
from timeleaf.fetch.http import BROWSER_UA, HONEST_UA, Http
from timeleaf.fetch.substack import Substack, headings, links, text, text_with_links
from timeleaf.models import Candidates, Sources


def test_text_with_links_keeps_each_link_next_to_its_words() -> None:
    body = (
        '<p>See <a class="x" href="https://a.example/x/?utm_source=1#top"><em>the bill</em></a> and '
        '<a href="https://substackcdn.com/i.png"><img src="i"></a>'
        '<a href="https://p.example/subscribe">subscribe</a> or <a href="mailto:a@b.example">write</a>.</p>'
    )
    out = text_with_links(body, 500)
    assert out == "See the bill [https://a.example/x] and subscribe or write."
    # the URL is exactly the one `links` reports, so the editor can copy it
    assert links({"body_html": body}) == ["https://a.example/x"]
    assert text_with_links(None, 10) == ""


def test_text_with_links_never_cuts_a_url_in_half() -> None:
    body = 'Start <a href="https://a.example/long/path">here</a> end'
    assert text_with_links(body, 30) == "Start here"
    assert text_with_links(body, 200) == "Start here [https://a.example/long/path] end"


def test_links_keep_real_queries_and_only_real_hrefs() -> None:
    """A query can be the address (youtube.com/watch?v=...): keep it, so the editor copies a working URL."""
    body = (
        '<a data-href="https://wrong.example/x" href="https://www.youtube.com/watch?v=abc&amp;t=3&amp;utm_source=x">'
        "the talk</a> "
        '<a href="https://u.example/b">unclosed <a href="https://c.example/c">next</a> '
        '<a href="https://substackcdn.com/i.png?w=600">img</a>'
    )
    out = text_with_links(body, 500)
    assert "the talk [https://www.youtube.com/watch?v=abc&t=3]" in out
    assert "next [https://c.example/c]" in out
    assert "wrong.example" not in out and "substackcdn" not in out
    assert links({"body_html": body}) == [
        "https://c.example/c",
        "https://u.example/b",
        "https://www.youtube.com/watch?v=abc&t=3",
    ]


def test_text_with_links_is_fast_on_broken_html() -> None:
    import time

    start = time.perf_counter()
    text_with_links('<p>x <a href="https://e.example/p">open ' * 4000, 20000)
    assert time.perf_counter() - start < 2


def test_archive_handles_both_response_shapes() -> None:
    ss = Substack(mock_http(substack_routes()))
    bare = ss.archive("https://fieldnotes.example/")  # a bare list, with one junk entry
    assert [p["id"] for p in bare] == [4001, 4002, 2001]
    wrapped = ss.archive("https://digest.example")  # {"posts": [...]}
    assert [p["id"] for p in wrapped] == [5001, 5002]
    assert ss.archive("https://missing.example") == []


def test_collect_publications(candidates: Candidates) -> None:
    by_title = {s.title: s for s in candidates.seeds}
    notes, digest = by_title["Field notes #7"], by_title["The digest"]
    assert notes.publication == "Field Notes" and digest.publication == "Garden Digest"
    # a roundup: links stay inline, junk links do not
    assert "Story 1: what happened [https://story1.example/s]." in notes.excerpt
    assert "substackcdn" not in notes.excerpt and "/subscribe" not in notes.excerpt
    assert "https://story6.example/s" in notes.links
    # not a roundup: plain text
    assert digest.excerpt == "Digest body."
    # same filters as subscriptions: short and old posts skipped
    assert "Housekeeping" not in by_title and "Old digest" not in by_title
    # the post that also arrives through a subscription appears once, under the subscription
    assert [s.publication for s in candidates.seeds if s.url == "https://roundup.example/p/1"] == [
        "Roundup Weekly"
    ]
    # publications vote like any other seed
    cited = {c.url: c.by for c in candidates.co_cited}
    assert cited["https://shared.example/x"] == ["Essays Monthly", "Field Notes", "Roundup Weekly"]


def test_collect_without_substack_handle_or_lesswrong(sources: Sources) -> None:
    s = sources.model_copy(update={"me": None, "lesswrong": False})
    http = mock_http(substack_routes())
    res = collect(s, http, days=7, now=NOW)
    assert sorted(p.title or "" for p in res.seeds) == ["Field notes #7", "Roundup #1", "The digest"]
    assert res.lesswrong == [] and res.health.failed == []


def test_text_strips_tags_and_entities() -> None:
    assert text("<p>Hello <b>world</b> &amp; friends</p>", 100) == "Hello world & friends"
    assert text(None, 10) == ""
    assert text("<p>abcdef</p>", 3) == "abc"


def test_links_skip_images_subscribe_and_dedupe() -> None:
    body = (
        '<a href="https://a.example/x/">1</a><a href="https://a.example/x">2</a>'
        '<a href="https://substackcdn.com/i.png">3</a><a href="https://p.example/subscribe">4</a>'
        '<a href="https://a.example/y?utm_medium=email">5</a>'
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
    # sorted by date, then URL; short and old posts skipped
    assert titles == ["An essay", "The digest", "Field notes #7", "Roundup #1"]
    essay, roundup = candidates.seeds[0], candidates.seeds[-1]
    assert essay.paywalled and essay.publication == "Essays Monthly"
    assert essay.excerpt == "Paid essay links x ."  # not a roundup: no inline links
    assert roundup.headings == ["The Quest for Sane Regulations", "Rhetorical Innovation"]
    assert "See this [https://news.example/a] and that [https://shared.example/x]." in roundup.excerpt
    assert "https://news.example/a" in roundup.links
    assert not any("substackcdn" in u or "subscribe" in u for u in roundup.links)


def test_collect_signals_lesswrong_cocited(candidates: Candidates) -> None:
    assert [(s.title, s.via) for s in candidates.signals] == [("Liked essay", "Ana")]
    assert candidates.lesswrong[0].karma == 150
    assert candidates.lesswrong[0].tags == ["AI"]
    assert [(c.url, c.by) for c in candidates.co_cited] == [
        ("https://shared.example/x", ["Essays Monthly", "Field Notes", "Roundup Weekly"])
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
