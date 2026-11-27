"""The editor step: Claude drafts an edition from candidates (ADR 0003).

The model writes the editorial content (a ``Draft``). Code adds number, dates and the colophon facts,
validates the result, and gives the model one chance to repair any errors.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from pydantic import BaseModel, ValidationError

from timeleaf.models import Candidates, Colophon, Draft, Edition, Item, Link, Section, Sources
from timeleaf.validate import Finding, errors, validate

MODEL = "claude-opus-5-5"
MODEL_NAMES = {
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-opus-5": "Claude Opus 5",
    "claude-opus-4-8": "Claude Opus 4.8",
}
EFFORT = "high"
MAX_TOKENS = 64000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# US$ per million tokens. Check https://www.anthropic.com/pricing when changing MODEL.
PRICES = {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20}
ASSUMED_OUTPUT_TOKENS = 30000  # for the pre-flight estimate (thinking + JSON)


class EditorError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    content: Any  # raw content blocks, appended to history unchanged
    stop_reason: str | None
    model: str
    usage: dict[str, int]


@dataclass
class RunStats:
    model: str = MODEL
    calls: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def add(self, reply: Reply) -> None:
        self.calls += 1
        self.model = reply.model
        for k, v in reply.usage.items():
            self.usage[k] = self.usage.get(k, 0) + (v or 0)

    @property
    def cost_usd(self) -> float:
        return cost(self.usage)


def cost(usage: dict[str, int]) -> float:
    return round(
        (
            usage.get("input_tokens", 0) * PRICES["input"]
            + usage.get("output_tokens", 0) * PRICES["output"]
            + usage.get("cache_creation_input_tokens", 0) * PRICES["cache_write"]
            + usage.get("cache_read_input_tokens", 0) * PRICES["cache_read"]
        )
        / 1_000_000,
        4,
    )


Call = Callable[[str, list[dict[str, Any]]], Reply]


# --------------------------------------------------------------------------- prompt


def system_prompt() -> str:
    return resources.files("timeleaf.edit").joinpath("prompt.md").read_text(encoding="utf-8")


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic schema -> the subset structured outputs accept: no titles/defaults, every key required."""

    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            out = {
                k: ({name: clean(s) for name, s in v.items()} if k in ("properties", "$defs") else clean(v))
                for k, v in node.items()
                if k not in ("title", "default")
            }
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"])
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node

    result: dict[str, Any] = clean(model.model_json_schema())
    return result


def user_message(c: Candidates, sources: Sources, previous: Edition | None, date: dt.date) -> str:
    start = date - dt.timedelta(days=c.window_days)
    parts = [
        f"This edition covers {start.isoformat()} to {date.isoformat()}.",
        "Friends (every new post must appear): "
        + ", ".join(f"{f.name} (@{f.handle})" for f in sources.friends),
        "Roundup publications: " + ", ".join(sources.roundups),
    ]
    if previous:
        prev = previous.model_dump(mode="json", include={"number", "date", "lede", "sections"})
        parts.append("<last_week>\n" + json.dumps(prev, ensure_ascii=False) + "\n</last_week>")
    else:
        parts.append("There is no previous edition.")
    cand = c.model_dump(mode="json", exclude={"health"})
    parts.append("<candidates>\n" + json.dumps(cand, ensure_ascii=False) + "\n</candidates>")
    parts.append("Write this week's edition.")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- assembly


def date_range(start: dt.date, end: dt.date) -> str:
    if start.year != end.year:
        return f"{start.day} {start:%B %Y} – {end.day} {end:%B %Y}"
    if start.month != end.month:
        return f"{start.day} {start:%B} – {end.day} {end:%B %Y}"
    return f"{start.day}–{end.day} {end:%B %Y}"


def checked_text(c: Candidates, items: int) -> str:
    h = c.health
    failed = len(h.failed)
    return (
        f"{h.total} requests to Substack and LessWrong, {failed or 'none'} failed. "
        f"{len(c.seeds)} posts from your subscriptions, {len(c.lesswrong)} top LessWrong posts and "
        f"{len(c.signals)} likes or restacks from your circle were read; {items} items made the edition."
    )


def assemble(
    draft: Draft, c: Candidates, previous: Edition | None, date: dt.date, stats: RunStats
) -> Edition:
    sections = [
        Section(
            id=s.id,
            title=s.title,
            note=s.note,
            items=[
                Item(
                    kind=i.kind,
                    kicker=i.kicker,
                    title=i.title,
                    url=i.url or None,
                    source=i.source or None,
                    mins=i.mins,
                    body=i.body,
                    why=i.why or None,
                    more=[Link(label=m.label, url=m.url) for m in i.more],
                    seen=i.seen,
                )
                for i in s.items
            ],
        )
        for s in draft.sections
    ]
    n_items = sum(len(s.items) for s in sections)
    return Edition(
        number=(previous.number + 1) if previous else 1,
        date=date,
        range=date_range(date - dt.timedelta(days=c.window_days), date),
        lede=draft.lede,
        sections=sections,
        colophon=Colophon(
            checked=checked_text(c, n_items),
            blind=draft.blind,
            requests_ok=c.health.ok,
            requests_failed=c.health.failed,
            model=MODEL_NAMES.get(stats.model, stats.model),
            cost_usd=round(stats.cost_usd, 2),
        ),
    )


# --------------------------------------------------------------------------- run


def edit(
    c: Candidates,
    sources: Sources,
    previous: Edition | None,
    date: dt.date,
    call: Call,
    max_repairs: int = 1,
) -> tuple[Edition, RunStats]:
    system = system_prompt()
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message(c, sources, previous, date)}]
    stats = RunStats()
    for attempt in range(max_repairs + 1):
        reply = call(system, messages)
        stats.add(reply)
        if reply.stop_reason == "refusal":
            raise EditorError("the model declined to write this edition (stop_reason=refusal)")
        if reply.stop_reason == "max_tokens":
            raise EditorError("the model ran out of output tokens before finishing the edition")
        problems: list[str]
        edition: Edition | None = None
        try:
            draft = Draft.model_validate_json(reply.text)
            edition = assemble(draft, c, previous, date, stats)
            stats.findings = validate(edition, c)
            problems = [str(f) for f in errors(stats.findings)]
        except ValidationError as e:
            problems = [f"Output did not match the schema: {e}"]
        if not problems and edition is not None:
            return edition, stats
        if attempt == max_repairs:
            raise EditorError("edition failed validation after repair:\n" + "\n".join(problems))
        messages.append({"role": "assistant", "content": reply.content})
        messages.append(
            {
                "role": "user",
                "content": "The edition failed validation:\n"
                + "\n".join(f"- {p}" for p in problems)
                + "\n\nReturn the whole corrected edition.",
            }
        )
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- Claude API


def anthropic_call(client: Any, model: str = MODEL, effort: str = EFFORT) -> Call:
    """A ``Call`` backed by the Claude API: streaming, structured output, server-side refusal fallback."""
    schema = strict_schema(Draft)

    def call(system: str, messages: list[dict[str, Any]]) -> Reply:
        with client.beta.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
        text = "".join(b.text for b in msg.content if b.type == "text")
        u = msg.usage
        usage = {
            k: getattr(u, k, 0) or 0
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            )
        }
        return Reply(
            text=text, content=msg.content, stop_reason=msg.stop_reason, model=msg.model, usage=usage
        )

    return call


def estimate_cost(
    client: Any, c: Candidates, sources: Sources, previous: Edition | None, date: dt.date
) -> float:
    count = client.messages.count_tokens(
        model=MODEL,
        system=system_prompt(),
        messages=[{"role": "user", "content": user_message(c, sources, previous, date)}],
    )
    return cost({"input_tokens": count.input_tokens, "output_tokens": ASSUMED_OUTPUT_TOKENS})
