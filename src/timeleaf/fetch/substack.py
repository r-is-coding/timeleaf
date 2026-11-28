"""Substack public API (undocumented; endpoints verified 2026-11-27, see docs/PLAN-buzz.md Appendix A)."""

from __future__ import annotations

import datetime as dt
import html
import re
from typing import Any

from timeleaf.fetch.http import Http
from timeleaf.models import Post

API = "https://substack.com/api/v1"

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_HEADING = re.compile(r"<h[1-4][^>]*>(.*?)</h[1-4]>", re.S)
_HREF = re.compile(r'href="(https?://[^"#?]+)')
_SKIP_LINK = re.compile(r"substackcdn|/subscribe|twitter\.com/intent|\.(png|jpe?g|gif|webp)$", re.I)
_ANCHOR = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S | re.I)
_OPEN_LINK = re.compile(r"\s*\[https?://[^\]]*$")
ACTIVITY_TYPES = {"post_like", "post_restack", "restack", "note"}


def text(fragment: str | None, limit: int) -> str:
    t = html.unescape(_TAG.sub(" ", fragment or ""))
    return _SPACE.sub(" ", t).strip()[:limit]


def text_with_links(fragment: str | None, limit: int) -> str:
    """Like ``text``, but keeps each link next to its words: ``<a href="U">words</a>`` -> ``words [U]``.

    Roundups are an index (PRINCIPLES value 3): the editor has to see which link belongs to which story.
    URLs are written exactly as ``links`` returns them, and the junk links it skips are skipped here too.
    """

    def keep(m: re.Match[str]) -> str:
        href = _HREF.search(m.group(1))
        if not href or _SKIP_LINK.search(href.group(1)):
            return m.group(2)
        return f"{m.group(2)} [{href.group(1).rstrip('/')}]"

    out = text(_ANCHOR.sub(keep, fragment or ""), limit)
    # Never leave half a URL at the cut: the editor may only copy URLs, and a truncated one is wrong.
    return _OPEN_LINK.sub("", out)


def parse_when(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def headings(p: dict[str, Any]) -> list[str]:
    return [text(h, 120) for h in _HEADING.findall(p.get("body_html") or "")][:60]


def links(p: dict[str, Any]) -> list[str]:
    out = {u.rstrip("/") for u in _HREF.findall(p.get("body_html") or "") if not _SKIP_LINK.search(u)}
    return sorted(out)


def slim(p: dict[str, Any], limit: int = 1500, *, inline_links: bool = False) -> Post:
    excerpt = text_with_links if inline_links else text
    return Post(
        title=p.get("title"),
        subtitle=p.get("subtitle"),
        url=p.get("canonical_url"),
        date=(p.get("post_date") or "")[:10],
        words=p.get("wordcount"),
        likes=p.get("reaction_count"),
        paywalled=p.get("audience") == "only_paid",
        authors=[b.get("name") for b in p.get("publishedBylines", []) if b.get("name")],
        excerpt=excerpt(p.get("body_html") or p.get("truncated_body_text") or p.get("description"), limit),
    )


class Substack:
    def __init__(self, http: Http) -> None:
        self.http = http
        self._profiles: dict[str, dict[str, Any] | None] = {}

    def profile(self, handle: str) -> dict[str, Any] | None:
        """Cached per run: a person can be both a friend and a signal."""
        if handle not in self._profiles:
            j = self.http.json(f"{API}/user/{handle}/public_profile")
            self._profiles[handle] = j if isinstance(j, dict) else None
        return self._profiles[handle]

    def posts_by(self, uid: int, limit: int = 8) -> list[dict[str, Any]]:
        j = self.http.json(f"{API}/profile/posts?profile_user_id={uid}&limit={limit}")
        posts = (j or {}).get("posts", []) if isinstance(j, dict) else []
        return [p for p in posts if isinstance(p, dict)]

    def archive(self, base_url: str, limit: int = 12) -> list[dict[str, Any]]:
        """A publication's newest posts, from its own host. No login and no subscription needed.

        Some hosts answer ``{"posts": [...]}`` and others a bare list (checked 2026-11-27).
        """
        j = self.http.json(f"{base_url.rstrip('/')}/api/v1/archive?sort=new&limit={limit}")
        posts = j.get("posts", []) if isinstance(j, dict) else j if isinstance(j, list) else []
        return [p for p in posts if isinstance(p, dict) and p.get("id")]

    def full(self, p: dict[str, Any]) -> dict[str, Any]:
        """The posts list only carries a teaser; fetch the whole post."""
        j = self.http.json(f"{API}/posts/by-id/{p['id']}")
        post = j.get("post") if isinstance(j, dict) else None
        return post if isinstance(post, dict) else p

    def activity(self, uid: int, since: dt.datetime) -> list[Post]:
        """Posts a person liked or restacked since ``since``: their recommendations."""
        base = f"{API}/reader/feed/profile/{uid}"
        items: list[dict[str, Any]] = []
        for url in (base, base + "?types%5B%5D=like"):
            j = self.http.json(url)
            if isinstance(j, dict):
                items += [i for i in j.get("items", []) if isinstance(i, dict)]
        out: list[Post] = []
        seen: set[Any] = set()
        for it in items:
            ctx, p = it.get("context") or {}, it.get("post")
            if not p or ctx.get("type") not in ACTIVITY_TYPES or not ctx.get("timestamp"):
                continue
            if parse_when(ctx["timestamp"]) < since or p.get("id") in seen:
                continue
            if ctx.get("type") == "note" and uid in [b.get("id") for b in p.get("publishedBylines", [])]:
                continue  # their own note about their own post is not a recommendation
            seen.add(p.get("id"))
            d = slim(p, 500)
            d.how = ctx["type"]
            d.when = ctx["timestamp"][:10]
            d.publication = (it.get("publication") or {}).get("name")
            out.append(d)
        return out
