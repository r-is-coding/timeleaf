from __future__ import annotations

import pytest

from timeleaf.models import Candidates, Edition, Item, Link, Post, Section, Sources
from timeleaf.readers import ReaderHome
from timeleaf.validate import candidate_urls, errors, norm_url, site_of, validate


def rules(e: Edition, c: Candidates | None = None, home: ReaderHome | None = None) -> set[str]:
    reader, sources = (home.reader, home.sources) if home else (None, None)
    return {f.rule for f in errors(validate(e, c, reader, sources))}


def test_edition1_has_no_errors(edition1: Edition, richard: ReaderHome) -> None:
    assert rules(edition1) == set()
    assert rules(edition1, home=richard) == set()
    assert edition1.item_count == 17


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://www.Example.com/p/x/", "http://example.com/p/x"),
        ("https://example.com/p/x?utm_source=a#frag", "https://example.com/p/x"),
    ],
)
def test_norm_url(a: str, b: str) -> None:
    assert norm_url(a) == norm_url(b)


def test_site_of() -> None:
    assert site_of("https://WWW.Example.com:443/p/x") == "example.com"
    assert site_of("https://name.substack.com/p/x") == "name.substack.com"


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


def test_note_kind_is_gone(edition1: Edition) -> None:
    """Silence is not news (value 7): there is no item kind for saying that friends were quiet."""
    assert all(i.url and i.why for i in edition1.items)
    assert "did not publish" not in edition1.model_dump_json()
    assert "posted nothing" not in edition1.lede
    with pytest.raises(ValueError, match="kind"):
        Item(kind="note", kicker="k", title="t", body="b")  # type: ignore[arg-type]


def test_duplicate_url_is_a_warning(edition1: Edition) -> None:
    dupes = [f for f in validate(edition1) if f.rule == "duplicate"]
    assert dupes and all(f.severity == "warning" for f in dupes)


def test_section_ids_and_empty_sections(edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections[1].id = e.sections[0].id
    e.sections[2].items = []
    assert {"section-id", "empty-section"} <= rules(e)


def test_sections_are_checked_per_reader(
    edition1: Edition, candidates: Candidates, richard: ReaderHome, juniper: ReaderHome
) -> None:
    # The Loop's own sections pass for its reader, and are unknown to another reader's paper.
    assert "sections" not in rules(edition1, candidates, home=richard)
    msgs = [f.message for f in validate(edition1, candidates, juniper.reader) if f.rule == "sections"]
    assert any("'front-page' is not one of The Kettle's sections" in m for m in msgs)

    def broken(change: str) -> list[str]:
        e = edition1.model_copy(deep=True)
        if change == "title":
            e.sections[0].title = "Top stories"
        elif change == "order":
            e.sections.reverse()
        elif change == "kind":
            e.sections[0].items[0].kind = "essay"
            e.sections[0].items[0].mins = 3
        return [f.message for f in validate(e, candidates, richard.reader) if f.rule == "sections"]

    assert "it must be 'Front page'" in broken("title")[0]
    assert "out of order" in broken("order")[0]
    assert "which holds 'news' items" in broken("kind")[0]
    # leaving a section out is fine
    e = edition1.model_copy(deep=True)
    del e.sections[2]
    assert "sections" not in rules(e, candidates, home=richard)


def test_renaming_a_section_never_fails_published_editions(edition1: Edition, richard: ReaderHome) -> None:
    """A reader may rename, reorder or retype sections later; editions already published stay valid."""
    reader = richard.reader.model_copy(deep=True)
    reader.sections[0].title = "Top stories"
    reader.sections.reverse()
    assert "sections" not in {f.rule for f in validate(edition1, None, reader, richard.sources)}


def test_buzz_rules(edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections[0].items[0] = Item(
        kind="buzz", kicker="X", title="T", url="https://x.com/a/status/1", source="X", body="b", why="w"
    )
    assert {"buzz-seen", "buzz-links"} <= rules(e)
    e.sections[0].items[0].seen = "via a roundup"
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


def test_friends_rule_is_per_reader(edition1: Edition, candidates: Candidates, sources: Sources) -> None:
    """Only this reader's friends are enforced, even if the candidates hold someone else's."""
    assert "friends" in {f.rule for f in validate(edition1, candidates, None, sources)}
    not_ana = sources.model_copy(update={"friends": [f for f in sources.friends if f.handle != "ana"]})
    assert "friends" not in {f.rule for f in validate(edition1, candidates, None, not_ana)}


def _edition_linking(edition1: Edition, urls: list[str]) -> Edition:
    items = [
        Item(kind="news", kicker="k", title=f"Item {n}", url=u, source="s", body="b", why="w")
        for n, u in enumerate(urls)
    ]
    return edition1.model_copy(update={"sections": [Section(id="s", title="S", note="n", items=items)]})


def test_source_cap(edition1: Edition, candidates: Candidates) -> None:
    filler = [f"https://story{n}.example/s" for n in range(1, 7)] + [
        "https://news.example/a",
        "https://shared.example/x",
        "https://essays.example/p/essay",
        "https://digest.example/p/digest",
    ]
    two = _edition_linking(
        edition1, [*filler, "https://roundup.example/p/1", "https://www.roundup.example/p/1"]
    )
    assert "source-cap" not in rules(two, candidates)  # two from one site is allowed
    three = _edition_linking(
        edition1, [*filler, *["https://roundup.example/p/1"] * 2, "https://WWW.roundup.example/p/1#b"]
    )
    found = [f for f in validate(three, candidates) if f.rule == "source-cap"]
    assert len(found) == 1 and found[0].severity == "error"
    assert "3 items link to roundup.example" in found[0].message


def test_source_cap_exempts_multi_author_platforms(edition1: Edition, candidates: Candidates) -> None:
    lw = "https://www.lesswrong.com/posts/abc/lw-post"
    many = _edition_linking(edition1, [lw] * 6 + ["https://x.com/someone/status/123"] * 6)
    assert "source-cap" not in rules(many, candidates)


def test_source_cap_does_not_count_friends_own_posts(edition1: Edition, candidates: Candidates) -> None:
    """Value 7 wins over value 3: a friend who posts three times still has all three included."""
    c = candidates.model_copy(deep=True)
    extra = [Post(title=f"More {n}", url=f"https://ana.substack.com/p/more{n}") for n in range(3)]
    c.friends[0].new_posts += extra
    urls = ["https://ana.substack.com/p/new", *[p.url or "" for p in extra]]
    urls += [f"https://story{n}.example/s" for n in range(1, 7)] + ["https://news.example/a"] * 2
    assert rules(_edition_linking(edition1, urls), c) == set()


def test_source_cap_only_applies_at_creation(edition1: Edition, richard: ReaderHome) -> None:
    """Edition 1 has five items from one newsletter. Without candidates it is not failed retroactively."""
    assert sum(site_of(i.url or "") == "thezvi.substack.com" for i in edition1.items) > 2
    assert "source-cap" not in rules(edition1, home=richard)


def test_candidate_urls_include_links_and_cocited(candidates: Candidates) -> None:
    urls = candidate_urls(candidates)
    for u in [
        "https://ana.substack.com/p/new",
        "https://news.example/a",
        "https://shared.example/x",
        "https://www.lesswrong.com/posts/abc/lw-post",
        "https://liked.example/p/essay",
        "https://ben.substack.com/p/last",
        "https://fieldnotes.example/p/notes",
        "https://story3.example/s",
    ]:
        assert norm_url(u) in urls
