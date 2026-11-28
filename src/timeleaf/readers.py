"""One folder per reader: ``readers/<id>/`` (proposal 0002, phase 1).

    reader.json   who the paper is for and its shape (the ``Reader`` model)
    profile.md    the reader, in their own words
    sources.json  whom the paper reads (the ``Sources`` model)
    notes.md      the reader's standing feedback, newest first
    editions/     one JSON file per edition

Nothing outside a reader's folder is specific to that reader (PRINCIPLES value 12: private by default).
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from timeleaf.models import Edition, Reader, SectionSpec, Sources

READERS = Path("readers")
ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TODO = "TODO"
MIN_TRUSTED = 3


class ReaderError(ValueError):
    pass


@dataclass(frozen=True)
class ReaderHome:
    """A reader's folder, loaded and validated."""

    dir: Path
    reader: Reader
    sources: Sources
    profile: str
    notes: str

    @property
    def id(self) -> str:
        return self.reader.id

    @property
    def editions(self) -> Path:
        return self.dir / "editions"


def list_ids(root: Path = READERS) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "reader.json").is_file())


def resolve(root: Path, reader_id: str | None, primary: str | None = None) -> str:
    """Which reader a command is about: the one named, else the only one, else the primary."""
    ids = list_ids(root)
    if reader_id is not None:
        if reader_id not in ids:
            raise ReaderError(f"no reader {reader_id!r} in {root} (have: {', '.join(ids) or 'none'})")
        return reader_id
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise ReaderError(f"no readers in {root}; create one with `timeleaf reader add <id>`")
    if primary in ids:
        return str(primary)
    raise ReaderError(
        f"{len(ids)} readers in {root} ({', '.join(ids)}); "
        "pass --reader <id> or set primary_reader in config/site.json"
    )


def load(root: Path, reader_id: str) -> ReaderHome:
    folder = root / reader_id
    try:
        reader = Reader.model_validate_json((folder / "reader.json").read_text(encoding="utf-8"))
        sources = Sources.model_validate_json((folder / "sources.json").read_text(encoding="utf-8"))
        profile = (folder / "profile.md").read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ReaderError(f"reader {reader_id!r}: missing {Path(e.filename).name}") from e
    except ValidationError as e:
        raise ReaderError(f"reader {reader_id!r}: {e}") from e
    if reader.id != reader_id:
        raise ReaderError(f"reader.json in {folder} has id {reader.id!r}; it must match the folder name")
    notes_file = folder / "notes.md"
    notes = notes_file.read_text(encoding="utf-8") if notes_file.is_file() else ""
    return ReaderHome(dir=folder, reader=reader, sources=sources, profile=profile, notes=notes)


def check(root: Path, reader_id: str, *, public: bool = False) -> list[str]:
    """Everything wrong with a reader's folder, in words. An empty list means it is ready.

    ``public`` says this reader's paper is the one built into the public site.
    """
    try:
        home = load(root, reader_id)
    except ReaderError as e:
        return [str(e)]
    problems: list[str] = []
    r, s = home.reader, home.sources
    if TODO in home.profile or len(home.profile.split()) < 30:
        problems.append("profile.md is not filled in (a few paragraphs, and no TODO left)")
    if TODO in (home.dir / "reader.json").read_text(encoding="utf-8"):
        problems.append("reader.json still has a TODO")
    ids = [x.id for x in r.sections]
    if len(set(ids)) != len(ids):
        problems.append("reader.json: section ids must be unique")
    friend_sections = [x for x in r.sections if x.kind == "friend"]
    if s.friends and not friend_sections:
        problems.append("sources.json lists friends, but no section in reader.json has kind 'friend'")
    if len(friend_sections) > 1:
        problems.append("reader.json: at most one section may have kind 'friend'")
    # Value 2 (trust over popularity) needs people to trust. A Substack handle brings its subscriptions.
    people = {f.handle for f in s.friends} | set(s.signal_handles) | set(s.extra_seed_handles)
    trusted = len(people) + len(s.publications)
    if not s.me and trusted < MIN_TRUSTED:
        problems.append(
            f"sources.json names {trusted} trusted people or publications; at least {MIN_TRUSTED} are "
            "needed (friends, signal_handles, extra_seed_handles, publications), or a Substack handle in 'me'"
        )
    known = {p.name for p in s.publications}
    for name in s.roundups:
        if not s.me and name not in known:
            problems.append(f"sources.json: roundup {name!r} is not one of the publications")
    # Value 10: nothing goes public without a person approving it.
    if public and r.review != "pr":
        problems.append(
            'review must be "pr" while this paper is built into the public site (PRINCIPLES value 10)'
        )
    if home.editions.is_dir():
        for p in sorted(home.editions.glob("*.json")):
            try:
                Edition.model_validate_json(p.read_text(encoding="utf-8"))
            except ValidationError:
                problems.append(f"editions/{p.name} does not match the Edition schema")
    return problems


# --------------------------------------------------------------------------- scaffold

DEFAULT_SECTIONS = [
    SectionSpec(
        id="front-page", title="Front page", note="What you most need to know this week.", kind="news"
    ),
    SectionSpec(
        id="worth-your-time",
        title="Worth your time",
        note="Essays. No summaries, only a reason to read.",
        kind="essay",
    ),
    SectionSpec(
        id="friends",
        title="From your friends",
        note="Everything they post appears here, always.",
        kind="friend",
    ),
    SectionSpec(id="edges", title="From the edges", note="Things your circle pointed at.", kind="edge"),
]

PROFILE_TEMPLATE = """# About me

<!-- {todo}: replace every paragraph below with your own words, then delete these comments.
     Only you and the owner of Timeleaf can see this file. See docs/onboarding.md. -->

## What I do

{todo}

## What I want to understand better

{todo}

## What I never want to see

{todo}

## How long I want to read each week

{todo}
"""

NOTES_TEMPLATE = """# Notes to the editor

Standing feedback from the reader, in their words, newest first. The editor reads all of it every week.
"""


def scaffold(
    root: Path,
    reader_id: str,
    paper_name: str,
    *,
    email: str | None = None,
    timezone: str = "Europe/Tallinn",
    substack: str | None = None,
) -> Path:
    """Create ``readers/<id>/`` with templates to fill in. Never overwrites."""
    if not ID.match(reader_id):
        raise ReaderError(f"{reader_id!r} is not a valid id: use lower-case letters, digits and hyphens")
    folder = root / reader_id
    if folder.exists():
        raise ReaderError(f"{folder} already exists")
    reader = Reader(
        id=reader_id,
        paper_name=paper_name,
        email=email,
        timezone=timezone,
        sections=[x.model_copy() for x in DEFAULT_SECTIONS],
        review="pr",
    )
    sources = Sources(me=substack)
    (folder / "editions").mkdir(parents=True)

    def write(name: str, text: str) -> None:
        (folder / name).write_text(text, encoding="utf-8", newline="\n")

    write("reader.json", json.dumps(reader.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n")
    write("sources.json", json.dumps(sources.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n")
    write("profile.md", PROFILE_TEMPLATE.format(todo=TODO))
    write("notes.md", NOTES_TEMPLATE)
    write("editions/.gitkeep", "")
    return folder


def remove(root: Path, reader_id: str) -> Path:
    """Delete a reader's folder: profile, sources, notes and every edition."""
    if reader_id not in list_ids(root):
        raise ReaderError(f"no reader {reader_id!r} in {root}")
    folder = root / reader_id
    shutil.rmtree(folder)
    return folder
