from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest

from timeleaf.edit import editor
from timeleaf.edit.editor import EditorError, Reply, cost, date_range, edit, strict_schema, user_message
from timeleaf.models import Candidates, Draft, Edition, Sources

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
        "why": "Zvi linked it",
        "more": [],
        "seen": None,
    }
    return base | kw


def good_draft() -> dict[str, Any]:
    news = [
        item(u)
        for u in [
            "https://news.example/a",
            "https://shared.example/x",
            "https://www.lesswrong.com/posts/abc/lw-post",
            "https://roundup.example/p/1",
        ]
    ]
    news += [item("https://roundup.example/p/1", title=f"Story {n}") for n in range(8)]
    return {
        "lede": "A quiet week.",
        "sections": [
            {"id": "front-page", "title": "Front page", "note": "n", "items": news},
            {
                "id": "worth-your-time",
                "title": "Worth your time",
                "note": "n",
                "items": [item("https://essays.example/p/essay", "essay")],
            },
            {
                "id": "friends",
                "title": "From your friends",
                "note": "n",
                "items": [item("https://ana.substack.com/p/new", "friend")],
            },
        ],
        "blind": "It cannot see X.",
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

    def __call__(self, system: str, messages: list[dict[str, Any]]) -> Reply:
        assert "editor of The Loop" in system
        self.seen.append(list(messages))
        return self.replies.pop(0)


def test_strict_schema_is_closed_and_complete() -> None:
    s = strict_schema(Draft)
    for node in [s, *s["$defs"].values()]:
        assert node["additionalProperties"] is False
        assert set(node["required"]) == set(node["properties"])
        assert "title" not in {k for k, v in node.items() if isinstance(v, str)}
    assert "title" in s["$defs"]["DraftItem"]["properties"]


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


def test_user_message_contains_context(candidates: Candidates, sources: Sources, edition1: Edition) -> None:
    msg = user_message(candidates, sources, edition1, DATE)
    assert "2026-11-20 to 2026-11-27" in msg
    assert "Ana (@ana)" in msg and "<last_week>" in msg and "<candidates>" in msg
    assert '"health"' not in msg
    assert "There is no previous edition." in user_message(candidates, sources, None, DATE)


def test_edit_happy_path(candidates: Candidates, sources: Sources, edition1: Edition) -> None:
    model = FakeModel(reply(good_draft()))
    e, stats = edit(candidates, sources, edition1, DATE, model)
    assert e.number == 2 and e.date == DATE and e.range == "20–27 November 2026"
    assert e.item_count == 14
    assert e.colophon.model == "Claude Opus 5.5"
    assert e.colophon.cost_usd == 0.6
    assert "none failed" in e.colophon.checked and "14 items made the edition" in e.colophon.checked
    assert stats.calls == 1


def test_edit_first_edition_is_number_one(candidates: Candidates, sources: Sources) -> None:
    e, _ = edit(candidates, sources, None, DATE, FakeModel(reply(good_draft())))
    assert e.number == 1


def test_edit_repairs_invented_url(candidates: Candidates, sources: Sources) -> None:
    bad = good_draft()
    bad["sections"][0]["items"][0]["url"] = "https://invented.example/nope"
    model = FakeModel(reply(bad), reply(good_draft()))
    e, stats = edit(candidates, sources, None, DATE, model)
    assert stats.calls == 2
    repair = model.seen[1][-1]["content"]
    assert "provenance" in repair and "invented.example" in repair
    assert model.seen[1][-2]["role"] == "assistant"
    assert e.colophon.cost_usd == 1.2


def test_edit_repairs_schema_mismatch(candidates: Candidates, sources: Sources) -> None:
    model = FakeModel(reply('{"lede": "x"}'), reply(good_draft()))
    _, stats = edit(candidates, sources, None, DATE, model)
    assert stats.calls == 2
    assert "did not match the schema" in model.seen[1][-1]["content"]


def test_edit_gives_up_after_one_repair(candidates: Candidates, sources: Sources) -> None:
    bad = good_draft()
    bad["sections"][2]["items"] = [item("https://ben.substack.com/p/last", "friend")]  # Ana's post missing
    with pytest.raises(EditorError, match="friends"):
        edit(candidates, sources, None, DATE, FakeModel(reply(bad), reply(bad)))


@pytest.mark.parametrize(("stop", "msg"), [("refusal", "declined"), ("max_tokens", "ran out")])
def test_edit_stop_reasons(candidates: Candidates, sources: Sources, stop: str, msg: str) -> None:
    with pytest.raises(EditorError, match=msg):
        edit(candidates, sources, None, DATE, FakeModel(reply("", stop)))


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
