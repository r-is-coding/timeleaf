"""Data contracts between the pipeline stages (ADR 0004).

Reader + Sources -> fetch -> Candidates -> edit -> Edition -> build -> HTML

Everything that belongs to one reader lives in ``readers/<id>/`` (see ``timeleaf.readers``).

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


ItemKind = Literal["news", "essay", "friend", "edge", "buzz"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- sources


class Friend(_Model):
    name: str
    handle: str
    recommendations: bool = False
    rec_days: int = 7


class Publication(_Model):
    """A Substack publication read through its own archive, whether or not the reader subscribes to it."""

    name: str
    url: HttpUrlStr = Field(description="The publication's home, e.g. https://newsletter.example")


class Sources(_Model):
    schema_version: Literal[1] = 1
    me: str | None = Field(
        default=None,
        description="The reader's Substack handle, if they have one; their subscriptions are seeds.",
    )
    friends: list[Friend] = Field(default_factory=list)
    publications: list[Publication] = Field(
        default_factory=list, description="Publications fetched directly, like seeds"
    )
    roundups: list[str] = Field(
        default_factory=list,
        description="Names of publications whose links count as votes and whose excerpts keep their links",
    )
    extra_seed_handles: list[str] = Field(default_factory=list)
    signal_handles: list[str] = Field(default_factory=list)
    lesswrong: bool = Field(default=True, description="Read the week's top LessWrong posts")


# --------------------------------------------------------------------------- reader

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=40)]


class SectionSpec(_Model):
    """One section of a reader's paper. The editor uses these ids, titles and notes exactly."""

    id: Slug
    title: str
    note: str
    kind: ItemKind = Field(description="The kind of item this section holds")


class Reader(_Model):
    """``readers/<id>/reader.json``: one reader and the shape of their paper."""

    schema_version: Literal[1] = 1
    id: Slug = Field(description="Same as the folder name")
    paper_name: str = Field(min_length=1)
    email: str | None = Field(default=None, description="The address the reader will log in with")
    timezone: str = "Europe/Tallinn"
    publish_day: Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] = (
        "friday"
    )
    sections: list[SectionSpec] = Field(min_length=1)
    review: Literal["pr", "auto"] = Field(
        default="pr",
        description="pr: a person approves each edition in a pull request. "
        "auto: the edition goes straight to its one reader after the automatic checks "
        "(only for papers that are not public).",
    )
    max_cost_usd: float = Field(default=2.0, gt=0, description="Cap on the model cost of one edition")
    blind_spots: list[str] = Field(
        default_factory=list,
        description="Things this reader's paper cannot see, beyond the ones the code knows about, "
        "each phrased to follow 'This edition cannot see ...'",
    )

    def section(self, section_id: str) -> SectionSpec | None:
        return next((s for s in self.sections if s.id == section_id), None)


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
    checked: str = Field(description="Written by code from the request ledger")
    blind: str = Field(description="What the edition cannot see. Written by code (timeleaf.blind)")
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
