"""Collect one week's candidates from every source into a single Candidates document."""

from __future__ import annotations

import datetime as dt
from typing import Any

from timeleaf.fetch import lesswrong
from timeleaf.fetch.http import Http
from timeleaf.fetch.substack import Substack, headings, links, slim
from timeleaf.models import Candidates, CoCited, FriendCandidates, Post, Sources

MIN_SEED_WORDS = 300  # skips open threads and admin notes
ROUNDUP_EXCERPT = 20000  # long, with links kept inline, so each story can be traced to its source
SEED_EXCERPT = 3500
FRIEND_EXCERPT = 4000


def collect(sources: Sources, http: Http, days: int = 7, now: dt.datetime | None = None) -> Candidates:
    now = now or dt.datetime.now(dt.UTC)
    cut = now - dt.timedelta(days=days)
    cut_iso = cut.isoformat()[:19]
    ss = Substack(http)
    res = Candidates(generated=now, window_days=days)
    votes: dict[str, set[str]] = {}

    # Friends: everything they post appears, always.
    for f in sources.friends:
        pr = ss.profile(f.handle)
        if not pr:
            continue
        posts: list[Post] = []
        for i, p in enumerate(ss.posts_by(pr["id"], 6)):
            fresh = (p.get("post_date") or "") >= cut_iso
            posts.append(slim(ss.full(p) if i == 0 or fresh else p, FRIEND_EXCERPT))
        entry = FriendCandidates(
            name=f.name,
            handle=f.handle,
            new_posts=[p for p in posts if p.date >= cut.date().isoformat()],
            latest_post=posts[0] if posts else None,
        )
        if f.recommendations:
            entry.recommended = ss.activity(pr["id"], now - dt.timedelta(days=f.rec_days))
        res.friends.append(entry)

    # Seeds: the reader's subscriptions, any extra handles, and the publications named in the config.
    me = (ss.profile(sources.me) if sources.me else None) or {}
    seeds: dict[int, str] = {
        s["publication"]["author_id"]: s["publication"]["name"]
        for s in me.get("subscriptions", [])
        if (s.get("publication") or {}).get("author_id")
    }
    for h in sources.extra_seed_handles:
        pr = ss.profile(h)
        if pr:
            seeds[pr["id"]] = (pr.get("primaryPublication") or {}).get("name") or pr.get("name") or h
    seen_urls = {p.url for fr in res.friends for p in fr.new_posts}

    def add_seed(p: dict[str, Any], name: str) -> None:
        if (p.get("post_date") or "") < cut_iso or (p.get("wordcount") or 0) < MIN_SEED_WORDS:
            return
        if p.get("canonical_url") in seen_urls:
            return  # a friend's post, or one already read through a subscription
        full = ss.full(p)
        roundup = name in sources.roundups
        d = slim(full, ROUNDUP_EXCERPT if roundup else SEED_EXCERPT, inline_links=roundup)
        if d.url in seen_urls:
            return
        seen_urls.add(d.url)
        d.publication = name
        d.headings = headings(full)
        d.links = links(full)
        res.seeds.append(d)
        for u in d.links:
            votes.setdefault(u, set()).add(name)

    for uid, name in seeds.items():
        for p in ss.posts_by(uid, 8):
            add_seed(p, name)
    for pub in sources.publications:
        for p in ss.archive(pub.url):
            add_seed(p, pub.name)

    # Signals: likes and restacks from trusted people, over a longer window.
    for h in sources.signal_handles:
        pr = ss.profile(h)
        if not pr:
            continue
        for a in ss.activity(pr["id"], now - dt.timedelta(days=days * 2)):
            a.via = pr.get("name") or h
            res.signals.append(a)

    if sources.lesswrong:
        res.lesswrong = lesswrong.top_posts(http, cut.date())
    for lw in res.lesswrong:
        votes.setdefault(lw.url.rstrip("/"), set()).add("LessWrong top")

    res.seeds.sort(key=lambda p: (p.date, p.url or ""))
    res.co_cited = sorted(
        (CoCited(url=u, by=sorted(v)) for u, v in votes.items() if len(v) >= 2),
        key=lambda c: (-len(c.by), c.url),
    )
    res.health = http.health
    return res
