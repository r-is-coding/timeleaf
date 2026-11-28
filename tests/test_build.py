from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.conftest import EDITION1, READERS, ROOT
from timeleaf.build.render import MARKER, SiteConfig, build, load_editions
from timeleaf.models import Candidates, Edition

EDITIONS = READERS / "richard/editions"
GOLDEN = Path(__file__).parent / "golden" / "edition-2026-11-27.html"


def test_paper_name_comes_from_the_reader_not_site_json(tmp_path: Path, site: SiteConfig) -> None:
    assert "publication" not in SiteConfig.model_fields
    with pytest.raises(ValueError, match="publication"):
        SiteConfig.model_validate({**site.model_dump(), "publication": "The Loop"})
    build(EDITIONS, tmp_path / "o", site, paper_name="The Kettle")
    html = (tmp_path / "o/index.html").read_text(encoding="utf-8")
    assert "<h1>The Kettle</h1>" in html and "The Loop" not in html


def test_no_edition_mentions_quiet_friends(built: Path) -> None:
    """Value 7: silence is not news."""
    for page in [*built.rglob("*.html"), built / "feed.xml"]:
        text = page.read_text(encoding="utf-8")
        assert "did not publish" not in text and "posted nothing" not in text
        assert 'class="item note"' not in text


def test_another_readers_data_never_reaches_the_public_build(
    two_readers: Path, tmp_path: Path, candidates: Candidates
) -> None:
    """Value 12: private by default. The public site is the primary reader's paper and nothing else."""
    from typer.testing import CliRunner

    from tests.test_editor import DATE, FakeModel, good_draft, reply
    from timeleaf import readers as rd
    from timeleaf.cli import app
    from timeleaf.edit.editor import edit

    # Give the second reader a real edition of their own, so there is something that could leak.
    juniper = rd.load(two_readers, "juniper")
    theirs, _ = edit(candidates, juniper, None, DATE, FakeModel(reply(good_draft())))
    juniper.editions.mkdir(exist_ok=True)
    (juniper.editions / "2026-11-27.json").write_text(theirs.model_dump_json(), encoding="utf-8")

    out = tmp_path / "public"
    args = ["--readers", str(two_readers), "--site", str(ROOT / "config/site.json")]
    r = CliRunner().invoke(app, ["build", "-o", str(out), *args])
    assert r.exit_code == 0, r.output
    assert "The Loop" in r.output

    secrets = {
        juniper.id,
        juniper.reader.paper_name,
        juniper.reader.email or "",
        *juniper.reader.blind_spots,
        *(s.id for s in juniper.reader.sections if s.id not in {"friends", "edges"}),
        *(s.title for s in juniper.reader.sections),
        *(s.note for s in juniper.reader.sections),
        *(f"{f.handle}.substack.com" for f in juniper.sources.friends),
        *(f"@{f.handle}" for f in juniper.sources.friends),
        *(p.name for p in juniper.sources.publications),
        *(p.url.rstrip("/") for p in juniper.sources.publications),
        *juniper.sources.roundups,
        *(i.title for i in theirs.items),
        *(i.url or "" for i in theirs.items),
        "market garden",
        "polytunnels",
    }
    secrets.discard("")
    assert len(secrets) > 40
    files = [p for p in out.rglob("*") if p.is_file() and p.suffix != ".woff2"]
    assert len(files) > 8
    for f in files:
        text = f.read_text(encoding="utf-8").lower()
        for s in secrets:
            assert s.lower() not in text, f"{s!r} from another reader is in {f.relative_to(out)}"
        assert str(f.relative_to(out)).lower().find("juniper") == -1
    # and nothing under a per-reader path exists either: the URLs are exactly today's
    assert not (out / "juniper").exists() and not (out / "richard").exists()

    # The other way round works too: their paper can be built on its own, for them only.
    r = CliRunner().invoke(app, ["build", "-o", str(tmp_path / "theirs"), "--reader", "juniper", *args])
    assert r.exit_code == 0, r.output
    page = (tmp_path / "theirs/index.html").read_text(encoding="utf-8")
    assert "<h1>The Kettle</h1>" in page and "The Loop" not in page and "PauseAI" not in page


@pytest.fixture
def site() -> SiteConfig:
    return SiteConfig.model_validate_json((ROOT / "config/site.json").read_text(encoding="utf-8"))


@pytest.fixture
def built(tmp_path: Path, site: SiteConfig) -> Path:
    out = tmp_path / "_site"
    build(EDITIONS, out, site, paper_name="The Loop")
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
    assert len(fonts) == 12
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
    assert html.count("<h1>") == 1


def test_model_text_is_escaped(tmp_path: Path, site: SiteConfig, edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.lede = '<script>alert("x")</script>'
    e.sections[0].items[0].title = "<img src=x onerror=alert(1)>"
    (tmp_path / "ed").mkdir()
    (tmp_path / "ed/2026-11-27.json").write_text(e.model_dump_json(), encoding="utf-8")
    build(tmp_path / "ed", tmp_path / "out", site, paper_name="The Loop")
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
    build(EDITIONS, tmp_path / "o", quiet, paper_name="The Loop")
    assert "noindex" in (tmp_path / "o/index.html").read_text(encoding="utf-8")
    assert "Disallow: /" in (tmp_path / "o/robots.txt").read_text(encoding="utf-8")


def test_multiple_editions_link_to_each_other(tmp_path: Path, site: SiteConfig, edition1: Edition) -> None:
    ed = tmp_path / "ed"
    ed.mkdir()
    shutil.copy(EDITION1, ed)
    e2 = edition1.model_copy(update={"number": 2, "date": dt.date(2026, 12, 4)})
    (ed / "2026-12-04.json").write_text(e2.model_dump_json(), encoding="utf-8")
    build(ed, tmp_path / "o", site, paper_name="The Loop")
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
        build(EDITIONS, out, site, paper_name="The Loop")
    assert (out / "keep.txt").exists()


def test_build_is_idempotent(built: Path, site: SiteConfig) -> None:
    before = (built / "index.html").read_bytes()
    build(EDITIONS, built, site, paper_name="The Loop")
    assert (built / "index.html").read_bytes() == before


def test_golden_edition_page(built: Path) -> None:
    """Rendered edition 1 must match the committed snapshot. Set UPDATE_GOLDEN=1 to accept a change."""
    html = (built / "editions/2026-11-27/index.html").read_text(encoding="utf-8")
    if os.environ.get("UPDATE_GOLDEN") == "1" or not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(html, encoding="utf-8", newline="\n")
    assert html == GOLDEN.read_text(encoding="utf-8")
