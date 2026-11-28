from __future__ import annotations

import datetime as dt
import json
from importlib import resources
from typing import Any

import pytest

from timeleaf.blind import blind_text
from timeleaf.edit import editor
from timeleaf.edit.editor import (
    EditorError,
    Reply,
    cost,
    date_range,
    edit,
    strict_schema,
    system_prompt,
    user_message,
)
from timeleaf.models import Candidates, Draft, Edition, Sources
from timeleaf.readers import ReaderHome

DATE = dt.date(2026, 11, 27)


def item(url: str, kind: str = "news", **kw: Any) -> dict[str, Any]:
    base = {
        "kind": kind,
        "kicker": "Beat",
        "title": f"About {url}",
        "url": url,
        "source": "Someone",
        "mins": 5 if kind == "essay" else None,
        "body": "Body.",
        "why": "Ana liked it",
        "more": [],
        "seen": None,
    }
    return base | kw


def good_draft() -> dict[str, Any]:
    """A valid edition of The Kettle (the fixture reader), 14 items, no site used more than twice."""
    news = [
        item(u)
        for u in [
            "https://news.example/a",
            "https://shared.example/x",
            "https://www.lesswrong.com/posts/abc/lw-post",
            "https://roundup.example/p/1",
            "https://fieldnotes.example/p/notes",
            "https://digest.example/p/digest",
            *[f"https://story{n}.example/s" for n in range(1, 6)],
        ]
    ]
    return {
        "lede": "A quiet week.",
        "sections": [
            {"id": "headlines", "title": "Headlines", "note": "n", "items": news},
            {
                "id": "long-reads",
                "title": "Long reads",
                "note": "n",
                "items": [item("https://essays.example/p/essay", "essay")],
            },
            {
                "id": "friends",
                "title": "From the allotment",
                "note": "n",
                "items": [item("https://ana.substack.com/p/new", "friend")],
            },
            {
                "id": "edges",
                "title": "Over the hedge",
                "note": "n",
                "items": [item("https://liked.example/p/essay", "edge")],
            },
        ],
    }


def reply(payload: Any, stop: str = "end_turn") -> Reply:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return Reply(
        text=text,
        content=[{"type": "text", "text": text}],
        stop_reason=stop,
        model="claude-opus-5-5",
        usage={"input_tokens": 100_000, "output_tokens": 10_000},
    )


class FakeModel:
    def __init__(self, *replies: Reply) -> None:
        self.replies = list(replies)
        self.seen: list[list[dict[str, Any]]] = []
        self.systems: list[str] = []

    def __call__(self, system: str, messages: list[dict[str, Any]]) -> Reply:
        assert "You are the editor of The Kettle" in system
        self.systems.append(system)
        self.seen.append(list(messages))
        return self.replies.pop(0)


def test_strict_schema_is_closed_and_complete() -> None:
    s = strict_schema(Draft)
    for node in [s, *s["$defs"].values()]:
        assert node["additionalProperties"] is False
        assert set(node["required"]) == set(node["properties"])
        assert "title" not in {k for k, v in node.items() if isinstance(v, str)}
    assert "title" in s["$defs"]["DraftItem"]["properties"]
    # The model writes the lede and the sections; the colophon, including "blind", is written by code.
    assert set(s["properties"]) == {"lede", "sections"}
    assert "note" not in s["$defs"]["DraftItem"]["properties"]["kind"]["enum"]


@pytest.mark.parametrize(
    ("start", "end", "out"),
    [
        (dt.date(2026, 11, 20), dt.date(2026, 11, 27), "20–27 November 2026"),
        (dt.date(2026, 11, 28), dt.date(2026, 12, 5), "28 November – 5 December 2026"),
        (dt.date(2026, 12, 29), dt.date(2027, 1, 5), "29 December 2026 – 5 January 2027"),
    ],
)
def test_date_range(start: dt.date, end: dt.date, out: str) -> None:
    assert date_range(start, end) == out


def test_cost() -> None:
    assert cost({"input_tokens": 1_000_000, "output_tokens": 100_000}) == 6.0
    assert cost({"cache_read_input_tokens": 1_000_000}) == 0.2


# --------------------------------------------------------------------------- prompt


def test_generic_prompt_names_no_reader() -> None:
    """prompt.md holds the values; everything about a particular reader comes from their folder."""
    template = resources.files("timeleaf.edit").joinpath("prompt.md").read_text(encoding="utf-8")
    for word in ["Zvi", "PauseAI", "The Loop", "Gamithra", "Llela", "Sese", "`note`", "blind"]:
        assert word not in template, word
    for slot in ["{{PAPER_NAME}}", "{{PROFILE}}", "{{NOTES}}", "{{SECTIONS}}"]:
        assert template.count(slot) == 1


def test_system_prompt_is_built_from_the_reader(richard: ReaderHome, juniper: ReaderHome) -> None:
    loop, kettle = system_prompt(richard), system_prompt(juniper)
    assert "You are the editor of The Loop" in loop
    assert "works at PauseAI" in loop and "Rely less on Zvi" in loop
    assert (
        "| `policy-desk` | Policy desk | Short. Read here, click only if you need the detail. | `news` |"
        in loop
    )
    assert "| `long-reads` | Long reads | For the armchair. | `essay` |" in kettle
    assert "market garden" in kettle and "polytunnels" in kettle
    # one reader's prompt holds nothing of the other's
    for theirs in ["PauseAI", "The Loop", "policy-desk", "Zvi"]:
        assert theirs not in kettle
    for theirs in ["Kettle", "market garden", "long-reads", "polytunnels"]:
        assert theirs not in loop
    # every slot is filled, and a reader's own text is not searched for slots
    assert "{{SECTIONS}}" not in kettle and "{{PAPER_NAME}}" not in kettle
    assert "{{PROFILE}} is not a placeholder here" in kettle


def test_system_prompt_is_stable_per_reader(richard: ReaderHome) -> None:
    """It is cache-marked, so it must not vary between calls: nothing from the week goes into it."""
    assert system_prompt(richard) == system_prompt(richard)
    assert "<candidates>" not in system_prompt(richard)


def test_prompt_states_the_editorial_rules(richard: ReaderHome) -> None:
    p = system_prompt(richard)
    assert "Silence is not news" in p
    assert "index, not a destination" in p
    assert "At most 2 items link to the same site" in p
    order = [
        p.index(s) for s in ["the reader's friends:", "the reader's signals", "breadth:", "a single roundup"]
    ]
    assert order == sorted(order)


def test_user_message_contains_context(candidates: Candidates, sources: Sources, edition1: Edition) -> None:
    msg = user_message(candidates, sources, edition1, DATE)
    assert "2026-11-20 to 2026-11-27" in msg
    assert "Ana (@ana)" in msg and "<last_week>" in msg and "<candidates>" in msg
    assert "Roundup publications: Roundup Weekly, Field Notes" in msg
    assert '"health"' not in msg
    assert "There is no previous edition." in user_message(candidates, sources, None, DATE)


# --------------------------------------------------------------------------- blind spots


def test_blind_text_is_written_by_code(richard: ReaderHome, juniper: ReaderHome) -> None:
    assert blind_text(richard.sources, richard.reader) == (
        "This edition cannot see X, the EA Forum, PauseAI's internal channels, or sites other than "
        "Substack and LessWrong. News items are reported as the linked authors describe them and were "
        "not checked against primary sources."
    )
    kettle = blind_text(juniper.sources, juniper.reader)
    assert "the allotment society's mailing list" in kettle and "PauseAI" not in kettle


def test_blind_text_follows_the_readers_sources(juniper: ReaderHome) -> None:
    no_lw = juniper.sources.model_copy(update={"lesswrong": False})
    plain = juniper.reader.model_copy(update={"blind_spots": []})
    assert blind_text(no_lw, plain).startswith(
        "This edition cannot see LessWrong, X, the EA Forum, or sites other than Substack. "
    )


# --------------------------------------------------------------------------- edit


def test_edit_happy_path(candidates: Candidates, juniper: ReaderHome, edition1: Edition) -> None:
    model = FakeModel(reply(good_draft()))
    e, stats = edit(candidates, juniper, edition1, DATE, model)
    assert e.number == 2 and e.date == DATE and e.range == "20–27 November 2026"
    assert e.item_count == 14
    assert e.colophon.model == "Claude Opus 5.5"
    assert e.colophon.cost_usd == 0.6
    assert "none failed" in e.colophon.checked and "14 items made the edition" in e.colophon.checked
    assert e.colophon.blind == blind_text(juniper.sources, juniper.reader)
    assert stats.calls == 1


def test_edit_first_edition_is_number_one(candidates: Candidates, juniper: ReaderHome) -> None:
    e, _ = edit(candidates, juniper, None, DATE, FakeModel(reply(good_draft())))
    assert e.number == 1


def test_checked_text_without_lesswrong(candidates: Candidates, juniper: ReaderHome) -> None:
    s = juniper.sources.model_copy(update={"lesswrong": False})
    assert editor.checked_text(candidates, 14, s).startswith(
        "20 requests to Substack, none failed. 4 posts from the newsletters you follow and 1 likes"
    )


def test_edit_repairs_invented_url(candidates: Candidates, juniper: ReaderHome) -> None:
    bad = good_draft()
    bad["sections"][0]["items"][0]["url"] = "https://invented.example/nope"
    model = FakeModel(reply(bad), reply(good_draft()))
    e, stats = edit(candidates, juniper, None, DATE, model)
    assert stats.calls == 2
    repair = model.seen[1][-1]["content"]
    assert "provenance" in repair and "invented.example" in repair
    assert model.seen[1][-2]["role"] == "assistant"
    assert model.systems[0] == model.systems[1]  # the repair call reuses the cached system prompt
    assert e.colophon.cost_usd == 1.2


def test_edit_repairs_leaning_on_one_roundup(candidates: Candidates, juniper: ReaderHome) -> None:
    bad = good_draft()
    for i in bad["sections"][0]["items"][:3]:
        i["url"] = "https://roundup.example/p/1"
    model = FakeModel(reply(bad), reply(good_draft()))
    _, stats = edit(candidates, juniper, None, DATE, model)
    assert stats.calls == 2
    assert "source-cap" in model.seen[1][-1]["content"]


def test_edit_rejects_another_readers_sections(candidates: Candidates, juniper: ReaderHome) -> None:
    bad = good_draft()
    bad["sections"][0] |= {"id": "front-page", "title": "Front page"}
    with pytest.raises(EditorError, match="'front-page' is not one of The Kettle's sections"):
        edit(candidates, juniper, None, DATE, FakeModel(reply(bad), reply(bad)))


def test_edit_rejects_the_old_note_kind_and_blind_field(candidates: Candidates, juniper: ReaderHome) -> None:
    note = good_draft()
    note["sections"][2]["items"].append(item("https://ben.substack.com/p/last", "note", why=None))
    blind = good_draft() | {"blind": "It cannot see X."}
    model = FakeModel(reply(note), reply(blind))
    with pytest.raises(EditorError, match="did not match the schema"):
        edit(candidates, juniper, None, DATE, model)
    assert "did not match the schema" in model.seen[1][-1]["content"]


def test_edit_repairs_schema_mismatch(candidates: Candidates, juniper: ReaderHome) -> None:
    model = FakeModel(reply('{"lede": "x"}'), reply(good_draft()))
    _, stats = edit(candidates, juniper, None, DATE, model)
    assert stats.calls == 2
    assert "did not match the schema" in model.seen[1][-1]["content"]


def test_edit_gives_up_after_one_repair(candidates: Candidates, juniper: ReaderHome) -> None:
    bad = good_draft()
    bad["sections"][2]["items"] = [item("https://ben.substack.com/p/last", "friend")]  # Ana's post missing
    with pytest.raises(EditorError, match="friends"):
        edit(candidates, juniper, None, DATE, FakeModel(reply(bad), reply(bad)))


@pytest.mark.parametrize(("stop", "msg"), [("refusal", "declined"), ("max_tokens", "ran out")])
def test_edit_stop_reasons(candidates: Candidates, juniper: ReaderHome, stop: str, msg: str) -> None:
    with pytest.raises(EditorError, match=msg):
        edit(candidates, juniper, None, DATE, FakeModel(reply("", stop)))


def test_anthropic_call_shapes_request() -> None:
    captured: dict[str, Any] = {}

    class Block:
        def __init__(self, type_: str, text: str = "") -> None:
            self.type, self.text = type_, text

    class Msg:
        content = [Block("thinking"), Block("text", '{"a": 1}')]
        stop_reason = "end_turn"
        model = "claude-opus-5-5"

        class usage:
            input_tokens, output_tokens = 10, 5
            cache_creation_input_tokens, cache_read_input_tokens = 0, None

    class Stream:
        def __enter__(self) -> Stream:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get_final_message(self) -> Msg:
            return Msg()

    class Client:
        class beta:
            class messages:
                @staticmethod
                def stream(**kw: Any) -> Stream:
                    captured.update(kw)
                    return Stream()

    r = editor.anthropic_call(Client())("SYS", [{"role": "user", "content": "hi"}])
    assert r.text == '{"a": 1}' and r.usage["cache_read_input_tokens"] == 0
    assert captured["model"] == "claude-opus-5-5"
    assert captured["fallbacks"] == "default" and captured["betas"] == [editor.FALLBACK_BETA]
    assert captured["output_config"]["effort"] == "high"
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "thinking" not in captured and "temperature" not in captured
