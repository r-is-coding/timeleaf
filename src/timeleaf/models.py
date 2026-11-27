"""Data contracts between the pipeline stages (ADR 0004).

Sources  -> fetch -> Candidates -> edit -> Edition -> build -> HTML

Every persisted file carries ``schema_version``. Bump it on a breaking change.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _http_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"not an http(s) URL: {value!r}")
    return value


HttpUrlStr = Annotated[str, AfterValidator(_http_url)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- sources


class Friend(_Model):
    name: str
    handle: str
    recommendations: bool = False
    rec_days: int = 7


class Sources(_Model):
    schema_version: Literal[1] = 1
    me: str = Field(description="The reader's Substack handle; their subscriptions are the seeds.")
    friends: list[Friend]
    roundups: list[str] = Field(
        default_factory=list, description="Publication names whose links count as votes"
    )
    extra_seed_handles: list[str] = Field(default_factory=list)
    signal_handles: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- candidates


class Post(_Model):
    title: str | None = None
    subtitle: str | None = None
    url: str | None = None
    date: str = ""
    words: int | None = None
    likes: int | None = None
    paywalled: bool = False
    authors: list[str] = Field(default_factory=list)
    excerpt: str = ""
    publication: str | None = None
    headings: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    # activity items (likes / restacks)
    how: str | None = None
    when: str | None = None
    via: str | None = None


class FriendCandidates(_Model):
    name: str
    handle: str
    new_posts: list[Post] = Field(default_factory=list)
    latest_post: Post | None = None
    recommended: list[Post] = Field(default_factory=list)


class LessWrongPost(_Model):
    title: str
    url: str
    karma: int
    comments: int
    author: str | None = None
    date: str
    words: int | None = None
    tags: list[str] = Field(default_factory=list)
    excerpt: str = ""


class CoCited(_Model):
    url: str
    by: list[str]


class Health(_Model):
    ok: int = 0
    failed: list[str] = Field(default_factory=list)
    user_agent_fallback: bool = False

    @property
    def total(self) -> int:
        return self.ok + len(self.failed)


class Candidates(_Model):
    schema_version: Literal[1] = 1
    generated: dt.datetime
    window_days: int
    friends: list[FriendCandidates] = Field(default_factory=list)
    seeds: list[Post] = Field(default_factory=list)
    signals: list[Post] = Field(default_factory=list)
    lesswrong: list[LessWrongPost] = Field(default_factory=list)
    co_cited: list[CoCited] = Field(default_factory=list)
    health: Health = Field(default_factory=Health)


# --------------------------------------------------------------------------- edition

# "note" is a short editorial line with no link, e.g. "Your friends did not publish this week".
ItemKind = Literal["news", "essay", "friend", "edge", "buzz", "note"]


class Link(_Model):
    label: str
    url: HttpUrlStr


class Item(_Model):
    kind: ItemKind
    kicker: str
    title: str
    url: HttpUrlStr | None = None
    source: str | None = None
    mins: int | None = None
    body: str
    why: str | None = None
    more: list[Link] = Field(default_factory=list)
    seen: str | None = None


class Section(_Model):
    id: str
    title: str
    note: str
    items: list[Item]


class Colophon(_Model):
    checked: str
    blind: str
    requests_ok: int = 0
    requests_failed: list[str] = Field(default_factory=list)
    model: str | None = None
    cost_usd: float | None = None


class Edition(_Model):
    schema_version: Literal[1] = 1
    number: int
    date: dt.date
    range: str
    lede: str
    sections: list[Section]
    colophon: Colophon

    @property
    def item_count(self) -> int:
        return sum(len(s.items) for s in self.sections)

    @property
    def items(self) -> list[Item]:
        return [i for s in self.sections for i in s.items]


# --------------------------------------------------------------------------- editor output


class DraftLink(_Model):
    label: str
    url: str


class DraftItem(_Model):
    kind: ItemKind
    kicker: str
    title: str
    url: str | None
    source: str | None
    mins: int | None
    body: str
    why: str | None
    more: list[DraftLink]
    seen: str | None


class DraftSection(_Model):
    id: str
    title: str
    note: str
    items: list[DraftItem]


class Draft(_Model):
    """What the model writes. Numbers, dates and run facts are filled in by code."""

    lede: str
    sections: list[DraftSection]
    blind: str = Field(description="One short paragraph: what this edition cannot see.")
