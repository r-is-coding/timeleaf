from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.conftest import ROOT
from timeleaf.build.render import MARKER, SiteConfig, _duration, build, contents, load_editions
from timeleaf.models import Edition

GOLDEN = Path(__file__).parent / "golden" / "edition-2026-11-27.html"


@pytest.fixture
def site() -> SiteConfig:
    return SiteConfig.model_validate_json((ROOT / "config/site.json").read_text(encoding="utf-8"))


@pytest.fixture
def built(tmp_path: Path, site: SiteConfig) -> Path:
    out = tmp_path / "_site"
    build(ROOT / "content/editions", out, site)
    return out


class Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for k, v in attrs:
            if k in ("href", "src", "action") and v:
                self.refs.append(v)


def refs(path: Path) -> list[str]:
    p = Refs()
    p.feed(path.read_text(encoding="utf-8"))
    return p.refs


def test_pages_exist(built: Path) -> None:
    for f in [
        "index.html",
        "editions/2026-11-27/index.html",
        "archive/index.html",
        "about/index.html",
        "404.html",
        "feed.xml",
        "sitemap.xml",
        "robots.txt",
        "static/style.css",
        "static/favicon.svg",
        "static/fonts/source-serif-4-latin-400.woff2",
        "static/fonts/fraunces-latin-opsz-wght.woff2",
        "static/fonts/LICENSE-OFL.txt",
        MARKER,
    ]:
        assert (built / f).is_file(), f


def test_internal_links_resolve(built: Path) -> None:
    for page in built.rglob("*.html"):
        for ref in refs(page):
            if not ref.startswith("/"):
                continue
            path = ref.split("?")[0].split("#")[0]
            target = built / path.lstrip("/")
            if path.endswith("/"):
                target = target / "index.html"
            assert target.is_file(), f"{page.relative_to(built)} links to missing {ref}"


def test_css_font_urls_resolve(built: Path) -> None:
    css = (built / "static/style.css").read_text(encoding="utf-8")
    fonts = re.findall(r"url\((fonts/[^)]+)\)", css)
    assert len(fonts) == 8
    assert not re.search(r"mono", css, re.I)  # docs/DESIGN.md: no monospace
    for f in fonts:
        assert (built / "static" / f).is_file(), f


def test_no_third_party_requests(built: Path) -> None:
    """Only <a href> may point off-site; nothing the browser loads automatically."""
    for page in built.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        for m in re.finditer(r"<(link|script|img|iframe)\b[^>]*", html):
            assert "http" not in m.group(0) or 'rel="canonical"' in m.group(0), m.group(0)
        assert "fonts.googleapis" not in html
        assert "<script" not in html


def test_head_has_csp_canonical_and_lang(built: Path) -> None:
    html = (built / "index.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert '<html lang="en">' in html
    assert "Content-Security-Policy" in html and "script-src 'none'" in html
    assert '<link rel="canonical" href="https://timeleaf.ee/editions/2026-11-27/">' in html
    assert html.count("<h1") == 1


def test_every_shipped_font_is_used(built: Path) -> None:
    css = (built / "static/style.css").read_text(encoding="utf-8")
    for f in (built / "static/fonts").glob("*.woff2"):
        assert f"fonts/{f.name}" in css, f"{f.name} is shipped but never referenced"


def test_contents_numbers_items_across_the_edition(edition1: Edition) -> None:
    c = contents(edition1)
    assert c.count == edition1.item_count == len(c.entries)
    assert [x.n for x in c.entries] == list(range(1, c.count + 1))
    assert [x.anchor for x in c.entries] == [f"item-{n}" for n in range(1, c.count + 1)]
    assert [s.id for s, _ in c.sections] == [s.id for s in edition1.sections]
    assert [x.item for x in c.entries] == edition1.items


def test_contents_reading_times(edition1: Edition) -> None:
    c = contents(edition1)
    for x in c.entries:
        if x.item.mins:
            assert x.mins == x.item.mins
        else:  # estimated from the body at 230 words a minute, never zero
            assert x.mins == max(1, -(-len(x.item.body.split()) // 230))
    assert c.linked_mins == sum(x.mins for x in c.entries)
    assert 1 <= c.paper_mins < c.linked_mins
    long = edition1.model_copy(deep=True)
    long.sections[0].items[0].mins = None
    long.sections[0].items[0].body = "word " * 700
    assert contents(long).entries[0].mins == 4
    assert contents(long).paper_mins > c.paper_mins


def test_duration_filter() -> None:
    assert _duration(40) == "40 min"
    assert _duration(60) == "1 h"
    assert _duration(223) == "3 h 45 min"


def test_edition_has_index_totals_and_orientation(built: Path, edition1: Edition) -> None:
    html = (built / "index.html").read_text(encoding="utf-8")
    c = contents(edition1)
    assert '<nav class="index" id="index" aria-labelledby="index-h">' in html
    assert f"<b>{c.count} items</b>" in html and f"<b>{c.paper_mins} min</b>" in html
    for x in c.entries:
        assert html.count(f'id="{x.anchor}"') == 1
        assert html.count(f'href="#{x.anchor}"') == 1
        assert f"{x.n} of {c.count}</span>" in html
    assert html.count("Why it is here") == sum(1 for i in edition1.items if i.why)
    assert "That is all for this week." in html


def test_fragment_links_resolve(built: Path) -> None:
    for page in built.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        ids = re.findall(r'\sid="([^"]+)"', html)
        assert len(ids) == len(set(ids)), f"duplicate ids in {page.relative_to(built)}"
        for ref in refs(page):
            if ref.startswith("#"):
                assert ref[1:] in ids, f"{page.relative_to(built)} jumps to missing {ref}"


def test_no_inline_styles(built: Path) -> None:
    """The CSP allows style-src 'self' only."""
    for page in built.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert "<style" not in html and " style=" not in html


def test_edition_with_a_single_item_renders(tmp_path: Path, site: SiteConfig, edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections = e.sections[:1]
    e.sections[0].items = e.sections[0].items[:1]
    (tmp_path / "ed").mkdir()
    (tmp_path / "ed/2026-11-27.json").write_text(e.model_dump_json(), encoding="utf-8")
    build(tmp_path / "ed", tmp_path / "out", site)
    html = (tmp_path / "out/index.html").read_text(encoding="utf-8")
    assert "<b>1 item</b>" in html and 'id="item-1"' in html
    assert html.count("<h1") == 1


def test_model_text_is_escaped(tmp_path: Path, site: SiteConfig, edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.lede = '<script>alert("x")</script>'
    e.sections[0].items[0].title = "<img src=x onerror=alert(1)>"
    (tmp_path / "ed").mkdir()
    (tmp_path / "ed/2026-11-27.json").write_text(e.model_dump_json(), encoding="utf-8")
    build(tmp_path / "ed", tmp_path / "out", site)
    html = (tmp_path / "out/index.html").read_text(encoding="utf-8")
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert "<img src=x" not in html


def test_feed_and_sitemap_are_valid_xml(built: Path) -> None:
    ns = {"a": "http://www.w3.org/2005/Atom"}
    feed = ET.parse(built / "feed.xml").getroot()
    entries = feed.findall("a:entry", ns)
    assert len(entries) == 1
    assert entries[0].findtext("a:id", namespaces=ns) == "https://timeleaf.ee/editions/2026-11-27/"
    assert "&lt;" not in (entries[0].findtext("a:content", namespaces=ns) or "")  # unescaped once parsed
    sm = ET.parse(built / "sitemap.xml").getroot()
    locs = [e.text for e in sm.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert "https://timeleaf.ee/archive/" in locs


def test_noindex_option(tmp_path: Path, site: SiteConfig) -> None:
    quiet = site.model_copy(update={"indexable": False})
    build(ROOT / "content/editions", tmp_path / "o", quiet)
    assert "noindex" in (tmp_path / "o/index.html").read_text(encoding="utf-8")
    assert "Disallow: /" in (tmp_path / "o/robots.txt").read_text(encoding="utf-8")


def test_multiple_editions_link_to_each_other(tmp_path: Path, site: SiteConfig, edition1: Edition) -> None:
    ed = tmp_path / "ed"
    ed.mkdir()
    shutil.copy(ROOT / "content/editions/2026-11-27.json", ed)
    e2 = edition1.model_copy(update={"number": 2, "date": dt.date(2026, 12, 4)})
    (ed / "2026-12-04.json").write_text(e2.model_dump_json(), encoding="utf-8")
    build(ed, tmp_path / "o", site)
    first = (tmp_path / "o/editions/2026-11-27/index.html").read_text(encoding="utf-8")
    assert 'href="/editions/2026-12-04/" rel="next"' in first
    index = (tmp_path / "o/index.html").read_text(encoding="utf-8")
    assert "No. 2" in index and 'rel="prev"' in index
    assert [e.number for e in load_editions(ed)] == [1, 2]


def test_duplicate_numbers_rejected(tmp_path: Path, edition1: Edition) -> None:
    (tmp_path / "a.json").write_text(edition1.model_dump_json(), encoding="utf-8")
    (tmp_path / "b.json").write_text(edition1.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate edition numbers"):
        load_editions(tmp_path)


def test_refuses_to_clear_foreign_directory(tmp_path: Path, site: SiteConfig) -> None:
    out = tmp_path / "precious"
    out.mkdir()
    (out / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build(ROOT / "content/editions", out, site)
    assert (out / "keep.txt").exists()


def test_build_is_idempotent(built: Path, site: SiteConfig) -> None:
    before = (built / "index.html").read_bytes()
    build(ROOT / "content/editions", built, site)
    assert (built / "index.html").read_bytes() == before


def test_golden_edition_page(built: Path) -> None:
    """Rendered edition 1 must match the committed snapshot. Set UPDATE_GOLDEN=1 to accept a change."""
    html = (built / "editions/2026-11-27/index.html").read_text(encoding="utf-8")
    if os.environ.get("UPDATE_GOLDEN") == "1" or not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(html, encoding="utf-8", newline="\n")
    assert html == GOLDEN.read_text(encoding="utf-8")


def _luminance(colour: str) -> float:
    parts = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in parts)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def palettes() -> list[dict[str, str]]:
    """The day and night token sets, read from the stylesheet itself."""
    css = (ROOT / "src/timeleaf/build/static/style.css").read_text(encoding="utf-8")

    def tokens(selector: str) -> dict[str, str]:
        blocks = re.findall(re.escape(selector) + r"\{([^}]*)\}", css)
        found = [t for t in (dict(re.findall(r"--(\w+):(#[0-9a-f]{6})", b)) for b in blocks) if t]
        assert len(found) == 1, selector
        return found[0]

    day = tokens("\n:root")
    night = tokens('@media (prefers-color-scheme:dark){:root:not([data-theme="light"])')
    forced = tokens('\n:root[data-theme="dark"]')
    assert night == forced, "the two night-edition blocks must stay identical"
    assert set(day) == set(night)
    return [day, night]


def test_palette_meets_wcag_in_both_modes() -> None:
    """docs/DESIGN.md: AA (4.5) for all text on both surfaces; AAA (7) for ink and muted text on paper."""
    for t in palettes():
        for surface in (t["paper"], t["wash"]):
            for text in ("ink", "muted", "accent"):
                assert contrast(t[text], surface) >= 4.5, (text, surface)
        assert contrast(t["ink"], t["paper"]) >= 7
        assert contrast(t["muted"], t["paper"]) >= 7
        assert contrast(t["paper"], t["ink"]) >= 7  # buttons and the skip link: paper on ink
