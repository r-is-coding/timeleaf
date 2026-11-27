"""Editorial and provenance rules for an edition (docs/PLAN.md §2.4, Validate).

Pure functions: they take models and return findings. Errors block publishing; warnings are shown in the PR.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from timeleaf.models import Candidates, Edition

MIN_ITEMS = 12
MAX_ITEMS = 18
MAX_BODY = 900
MAX_ESSAY_BODY = 400


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


def validate(edition: Edition, candidates: Candidates | None = None) -> list[Finding]:
    out: list[Finding] = []

    def err(rule: str, msg: str) -> None:
        out.append(Finding("error", rule, msg))

    def warn(rule: str, msg: str) -> None:
        out.append(Finding("warning", rule, msg))

    n = edition.item_count
    if not MIN_ITEMS <= n <= MAX_ITEMS:
        err("item-cap", f"{n} items; the edition must have {MIN_ITEMS}-{MAX_ITEMS}")

    ids = Counter(s.id for s in edition.sections)
    for sid, count in ids.items():
        if count > 1:
            err("section-id", f"section id {sid!r} used {count} times")
    for s in edition.sections:
        if not s.items:
            err("empty-section", f"section {s.title!r} has no items")

    seen: dict[str, str] = {}
    for item in edition.items:
        label = item.title[:60]
        if item.kind == "note":
            continue
        if not item.url:
            err("url", f"{label!r} has no link; only 'note' items may omit it")
            continue
        if not (item.why or "").strip():
            err("why", f"{label!r} has no 'why it is here' line")
        if not (item.source or "").strip():
            err("source", f"{label!r} has no source")
        if item.kind == "essay" and not item.mins:
            err("essay-mins", f"essay {label!r} has no reading time")
        key = norm_url(item.url)
        if key in seen:
            warn("duplicate", f"{label!r} links the same URL as {seen[key]!r}")
        seen[key] = label
        if item.kind == "buzz":
            if not item.seen:
                err("buzz-seen", f"buzz item {label!r} must say how it was seen ('direct' or 'via ...')")
            if len(item.more) < 2:
                err("buzz-links", f"buzz item {label!r} needs at least two linked posts")
        limit = MAX_ESSAY_BODY if item.kind == "essay" else MAX_BODY
        if len(item.body) > limit:
            warn("body-length", f"{label!r} body is {len(item.body)} chars (limit {limit})")

    if candidates is not None:
        known = candidate_urls(candidates)
        for item in edition.items:
            for url in [*([item.url] if item.url else []), *(m.url for m in item.more)]:
                if norm_url(url) not in known:
                    err("provenance", f"{url} (in {item.title[:50]!r}) is not in the fetched candidates")
        present = {norm_url(i.url) for i in edition.items if i.url}
        for f in candidates.friends:
            for p in f.new_posts:
                if p.url and norm_url(p.url) not in present:
                    err("friends", f"{f.name}'s new post {p.title!r} is missing; friends always appear")
    return out


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "error"]
