"""The colophon's "what it cannot see" paragraph, written by code (PRINCIPLES value 8, proposal 0001 P4).

The model used to write this paragraph and it drifted from reality. Now it is derived from a registry of
the sources Timeleaf knows about and whether this reader's paper reads them, plus the blind spots the
reader's own ``reader.json`` lists. When a source becomes readable, change its entry here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from timeleaf.models import Reader, Sources


@dataclass(frozen=True)
class KnownSource:
    label: str  # as it reads after "This edition cannot see ..."
    platform: bool  # a place many people publish, named in "sites other than ..."
    has: Callable[[Sources], bool]  # does this reader's paper read it?


REGISTRY: tuple[KnownSource, ...] = (
    KnownSource("Substack", platform=True, has=lambda s: True),
    KnownSource("LessWrong", platform=True, has=lambda s: s.lesswrong),
    # Not readable yet: X needs a paid API (PLAN-buzz), the EA Forum answers automated requests
    # with a bot check (checked 2026-11-27).
    KnownSource("X", platform=False, has=lambda s: False),
    KnownSource("the EA Forum", platform=False, has=lambda s: False),
)

UNCHECKED = (
    "News items are reported as the linked authors describe them and were not checked against "
    "primary sources."
)


def _join(parts: list[str], last: str) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    if len(parts) == 2:
        return f"{parts[0]} {last} {parts[1]}"
    return ", ".join(parts[:-1]) + f", {last} {parts[-1]}"


def platforms(sources: Sources) -> list[str]:
    """The platforms this reader's paper reads, e.g. ["Substack", "LessWrong"]."""
    return [k.label for k in REGISTRY if k.platform and k.has(sources)]


def blind_text(sources: Sources, reader: Reader) -> str:
    missing = [k.label for k in REGISTRY if not k.has(sources)]
    cannot = [
        *missing,
        *(b.strip().rstrip(".") for b in reader.blind_spots if b.strip()),
        "sites other than " + _join(platforms(sources), "and"),
    ]
    return f"This edition cannot see {_join(cannot, 'or')}. {UNCHECKED}"
