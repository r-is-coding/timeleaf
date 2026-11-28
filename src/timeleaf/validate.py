"""Editorial and provenance rules for an edition (docs/PLAN.md §2.4, Validate).

Pure functions: they take models and return findings. Errors block publishing; warnings are shown in the PR.

Each rule enforces a part of docs/PRINCIPLES.md that a program can check. The comment above a rule names
the value it protects ("V1" is value 1, and so on).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from timeleaf.models import Candidates, Edition, Reader, Sources

# V1 Finite: one edition is about 15-18 items, and then it ends.
MIN_ITEMS = 12
MAX_ITEMS = 18
# V5 Respect attention: news is compressed; essays get a pitch, never a summary.
MAX_BODY = 900
MAX_ESSAY_BODY = 400
# V3 Breadth over one voice: no single site supplies more than this many items.
MAX_PER_SITE = 2
# Places where many unrelated authors publish; the cap is about voices, not platforms.
MULTI_AUTHOR_SITES = frozenset(
    {
        "lesswrong.com",
        "forum.effectivealtruism.org",
        "substack.com",  # substack.com itself; a publication at <name>.substack.com is one site
        "arxiv.org",
        "x.com",
        "twitter.com",
        "youtube.com",
    }
)


@dataclass(frozen=True)
class Finding:
    severity: Literal["error", "warning"]
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity.upper()} [{self.rule}] {self.message}"


def norm_url(url: str) -> str:
    """Compare URLs by host and path: ignore scheme, www, query, fragment and trailing slash."""
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}"


def site_of(url: str) -> str:
    """The site a URL is on: its host, lower-cased, without ``www.``."""
    return (urlsplit(url.strip()).hostname or "").removeprefix("www.")


def candidate_urls(c: Candidates) -> set[str]:
    urls: set[str] = set()

    def add(u: str | None) -> None:
        if u:
            urls.add(norm_url(u))

    for f in c.friends:
        for p in [*f.new_posts, *f.recommended, *([f.latest_post] if f.latest_post else [])]:
            add(p.url)
    for p in [*c.seeds, *c.signals]:
        add(p.url)
        for link in p.links:
            add(link)
    for lw in c.lesswrong:
        add(lw.url)
    for cc in c.co_cited:
        add(cc.url)
    return urls


def validate(
    edition: Edition,
    candidates: Candidates | None = None,
    reader: Reader | None = None,
    sources: Sources | None = None,
) -> list[Finding]:
    """Check one edition.

    ``reader`` adds the rules about that reader's own paper (its sections). ``candidates`` adds the rules
    that only make sense at the moment an edition is created (provenance, friends, source-cap), so
    published editions are never failed retroactively. ``sources`` limits the friends rule to this
    reader's friends.
    """
    out: list[Finding] = []

    def err(rule: str, msg: str) -> None:
        out.append(Finding("error", rule, msg))

    def warn(rule: str, msg: str) -> None:
        out.append(Finding("warning", rule, msg))

    # V1 Finite.
    n = edition.item_count
    if not MIN_ITEMS <= n <= MAX_ITEMS:
        err("item-cap", f"{n} items; the edition must have {MIN_ITEMS}-{MAX_ITEMS}")

    # V14 Simple: every section is distinct and earns its place.
    ids = Counter(s.id for s in edition.sections)
    for sid, count in ids.items():
        if count > 1:
            err("section-id", f"section id {sid!r} used {count} times")
    for s in edition.sections:
        if not s.items:
            err("empty-section", f"section {s.title!r} has no items")

    # US-12 "it feels like my paper": the sections are the ones this reader chose, in their order.
    if reader is not None:
        order = [spec.id for spec in reader.sections]
        last = -1
        for s in edition.sections:
            spec = reader.section(s.id)
            if spec is None:
                err("sections", f"section {s.id!r} is not one of {reader.paper_name}'s sections")
                continue
            if s.title != spec.title:
                err("sections", f"section {s.id!r} is titled {s.title!r}; it must be {spec.title!r}")
            pos = order.index(s.id)
            if pos < last:
                err("sections", f"section {s.id!r} is out of order; the order is {', '.join(order)}")
            last = max(last, pos)
            for item in s.items:
                if item.kind != spec.kind:
                    err(
                        "sections",
                        f"{item.title[:60]!r} is a {item.kind!r} item in section {s.id!r}, "
                        f"which holds {spec.kind!r} items",
                    )

    seen: dict[str, str] = {}
    for item in edition.items:
        label = item.title[:60]
        # V11 Respect writers: credit and link the original.
        if not item.url:
            err("url", f"{label!r} has no link; every item links to its original")
            continue
        # V4 Say why, in terms the reader recognises.
        if not (item.why or "").strip():
            err("why", f"{label!r} has no 'why it is here' line")
        # V11 Respect writers.
        if not (item.source or "").strip():
            err("source", f"{label!r} has no source")
        # V5 Respect attention: an essay comes with its reading time.
        if item.kind == "essay" and not item.mins:
            err("essay-mins", f"essay {label!r} has no reading time")
        # V1 Finite: the same piece twice wastes one of a small number of places.
        key = norm_url(item.url)
        if key in seen:
            warn("duplicate", f"{label!r} links the same URL as {seen[key]!r}")
        seen[key] = label
        # V8 Honest about blind spots: a conversation says how it was seen, and shows its evidence.
        if item.kind == "buzz":
            if not item.seen:
                err("buzz-seen", f"buzz item {label!r} must say how it was seen ('direct' or 'via ...')")
            if len(item.more) < 2:
                err("buzz-links", f"buzz item {label!r} needs at least two linked posts")
        # V5 Respect attention.
        limit = MAX_ESSAY_BODY if item.kind == "essay" else MAX_BODY
        if len(item.body) > limit:
            warn("body-length", f"{label!r} body is {len(item.body)} chars (limit {limit})")

    if candidates is not None:
        # V11 Respect writers, and the model cannot invent sources (PLAN goal G3).
        known = candidate_urls(candidates)
        for item in edition.items:
            for url in [*([item.url] if item.url else []), *(m.url for m in item.more)]:
                if norm_url(url) not in known:
                    err("provenance", f"{url} (in {item.title[:50]!r}) is not in the fetched candidates")

        # V7 Friends always appear.
        present = {norm_url(i.url) for i in edition.items if i.url}
        mine = {f.handle for f in sources.friends} if sources is not None else None
        for f in candidates.friends:
            if mine is not None and f.handle not in mine:
                continue
            for p in f.new_posts:
                if p.url and norm_url(p.url) not in present:
                    err("friends", f"{f.name}'s new post {p.title!r} is missing; friends always appear")

        # V3 Breadth over one voice. Friends' own posts do not count: V7 says all of them appear.
        by_friends = {norm_url(p.url) for f in candidates.friends for p in f.new_posts if p.url}
        per_site = Counter(
            site_of(i.url) for i in edition.items if i.url and norm_url(i.url) not in by_friends
        )
        for site, count in sorted(per_site.items()):
            if count > MAX_PER_SITE and site not in MULTI_AUTHOR_SITES:
                err(
                    "source-cap",
                    f"{count} items link to {site}; at most {MAX_PER_SITE} may come from one site. "
                    "Link the primary sources instead, or drop the weakest",
                )
    return out


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "error"]
