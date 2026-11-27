from __future__ import annotations

import pytest

from timeleaf.models import Candidates, Edition, Item, Link
from timeleaf.validate import candidate_urls, errors, norm_url, validate


def rules(e: Edition, c: Candidates | None = None) -> set[str]:
    return {f.rule for f in errors(validate(e, c))}


def test_edition1_has_no_errors(edition1: Edition) -> None:
    assert rules(edition1) == set()


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://www.Example.com/p/x/", "http://example.com/p/x"),
        ("https://example.com/p/x?utm_source=a#frag", "https://example.com/p/x"),
    ],
)
def test_norm_url(a: str, b: str) -> None:
    assert norm_url(a) == norm_url(b)


def test_item_cap(edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections[0].items *= 4
    assert "item-cap" in rules(e)
    e.sections = e.sections[:1]
    e.sections[0].items = e.sections[0].items[:3]
    assert "item-cap" in rules(e)


def test_missing_why_source_url_and_essay_mins(edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    first = e.sections[0].items[0]
    first.why = " "
    first.source = None
    essay = next(i for i in e.items if i.kind == "essay")
    essay.mins = None
    e.sections[1].items[0].url = None
    assert {"why", "source", "essay-mins", "url"} <= rules(e)


def test_notes_are_exempt(edition1: Edition) -> None:
    note = next(i for i in edition1.items if i.kind == "note")
    assert note.url is None and note.why is None
    assert rules(edition1) == set()


def test_duplicate_url_is_a_warning(edition1: Edition) -> None:
    dupes = [f for f in validate(edition1) if f.rule == "duplicate"]
    assert dupes and all(f.severity == "warning" for f in dupes)


def test_section_ids_and_empty_sections(edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections[1].id = e.sections[0].id
    e.sections[2].items = []
    assert {"section-id", "empty-section"} <= rules(e)


def test_buzz_rules(edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections[0].items[0] = Item(
        kind="buzz", kicker="X", title="T", url="https://x.com/a/status/1", source="X", body="b", why="w"
    )
    assert {"buzz-seen", "buzz-links"} <= rules(e)
    e.sections[0].items[0].seen = "via Zvi"
    e.sections[0].items[0].more = [
        Link(label="a", url="https://x.com/a/status/2"),
        Link(label="b", url="https://x.com/b/status/3"),
    ]
    assert not {"buzz-seen", "buzz-links"} & rules(e)


def test_body_length_warning(edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    next(i for i in e.items if i.kind == "essay").body = "x" * 500
    assert any(f.rule == "body-length" and f.severity == "warning" for f in validate(e))


def test_provenance_and_friends(edition1: Edition, candidates: Candidates) -> None:
    found = rules(edition1, candidates)
    assert "provenance" in found  # edition 1 links are not in the synthetic candidates
    assert "friends" in found  # Ana's new post is missing


def test_candidate_urls_include_links_and_cocited(candidates: Candidates) -> None:
    urls = candidate_urls(candidates)
    for u in [
        "https://ana.substack.com/p/new",
        "https://news.example/a",
        "https://shared.example/x",
        "https://www.lesswrong.com/posts/abc/lw-post",
        "https://liked.example/p/essay",
        "https://ben.substack.com/p/last",
    ]:
        assert norm_url(u) in urls
