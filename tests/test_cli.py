from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.conftest import ROOT
from timeleaf.cli import app, run_report
from timeleaf.models import Candidates, Edition
from timeleaf.validate import validate

runner = CliRunner()


def test_validate_all_editions_ok() -> None:
    r = runner.invoke(app, ["validate", "--editions", str(ROOT / "content/editions")])
    assert r.exit_code == 0, r.output
    assert "WARNING [duplicate]" in r.output


def test_validate_reports_errors(tmp_path: Path, edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections[0].items[0].why = ""
    p = tmp_path / "bad.json"
    p.write_text(e.model_dump_json(), encoding="utf-8")
    r = runner.invoke(app, ["validate", str(p)])
    assert r.exit_code == 1
    assert "ERROR [why]" in r.output


def test_validate_schema_failure(tmp_path: Path) -> None:
    p = tmp_path / "broken.json"
    p.write_text(json.dumps({"number": 1}), encoding="utf-8")
    r = runner.invoke(app, ["validate", str(p)])
    assert r.exit_code == 1


def test_build_and_schema(tmp_path: Path) -> None:
    out = tmp_path / "site"
    r = runner.invoke(
        app,
        [
            "build",
            "-o",
            str(out),
            "--editions",
            str(ROOT / "content/editions"),
            "--site",
            str(ROOT / "config/site.json"),
        ],
    )
    assert r.exit_code == 0, r.output
    assert (out / "index.html").exists()
    r = runner.invoke(app, ["schema", "-o", str(tmp_path / "schemas")])
    assert r.exit_code == 0
    assert (
        json.loads((tmp_path / "schemas/edition.schema.json").read_text(encoding="utf-8"))["title"]
        == "Edition"
    )


def test_committed_schemas_are_current(tmp_path: Path) -> None:
    runner.invoke(app, ["schema", "-o", str(tmp_path)])
    for f in tmp_path.iterdir():
        committed = ROOT / "docs/schemas" / f.name
        assert committed.read_text(encoding="utf-8") == f.read_text(encoding="utf-8"), (
            f"{committed} is stale: run `uv run timeleaf schema`"
        )


def test_run_report(edition1: Edition, candidates: Candidates) -> None:
    md = run_report(
        edition1,
        candidates,
        validate(edition1),
        "claude-opus-5-5",
        {"input_tokens": 1234, "output_tokens": 56},
        0.42,
    )
    assert "The Loop No. 1" in md and "| **Total** | **18** |" in md
    assert "$0.42" in md and "### Warnings" in md and "- [ ] Read every item" in md


class _FakeAnthropic:
    """Stands in for anthropic.Anthropic in CLI tests; the editor call itself is patched separately."""

    class messages:
        @staticmethod
        def count_tokens(**_kw: object) -> object:
            return type("Count", (), {"input_tokens": 50_000})()


def _setup_edit(tmp_path: Path, candidates: Candidates, monkeypatch: pytest.MonkeyPatch) -> Path:
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _FakeAnthropic)
    (tmp_path / "ed").mkdir()
    shutil.copy(ROOT / "content/editions/2026-11-27.json", tmp_path / "ed")
    cand = tmp_path / "candidates.json"
    c = candidates.model_copy(update={"generated": candidates.generated + dt.timedelta(days=7)})
    cand.write_text(c.model_dump_json(), encoding="utf-8")
    (tmp_path / "sources.json").write_text(
        (ROOT / "tests/fixtures/sources.json").read_text(), encoding="utf-8"
    )
    return cand


def test_edit_dry_run_and_cost_cap(
    tmp_path: Path, candidates: Candidates, monkeypatch: pytest.MonkeyPatch
) -> None:
    cand = _setup_edit(tmp_path, candidates, monkeypatch)
    args = [
        "edit",
        str(cand),
        "--editions",
        str(tmp_path / "ed"),
        "--sources",
        str(tmp_path / "sources.json"),
    ]
    r = runner.invoke(app, [*args, "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Estimated cost: $0.80" in r.output
    r = runner.invoke(app, [*args, "--max-cost", "0.5"])
    assert r.exit_code == 2
    assert not (tmp_path / "ed/2026-12-04.json").exists()


def test_edit_writes_edition_and_report(
    tmp_path: Path, candidates: Candidates, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_editor import FakeModel, good_draft, reply
    from timeleaf.edit import editor

    cand = _setup_edit(tmp_path, candidates, monkeypatch)
    monkeypatch.setattr(editor, "anthropic_call", lambda _client: FakeModel(reply(good_draft())))
    args = [
        "edit",
        str(cand),
        "--editions",
        str(tmp_path / "ed"),
        "--sources",
        str(tmp_path / "sources.json"),
    ]
    r = runner.invoke(app, [*args, "--report", str(tmp_path / "report.md")])
    assert r.exit_code == 0, r.output
    e = Edition.model_validate_json((tmp_path / "ed/2026-12-04.json").read_text(encoding="utf-8"))
    assert e.number == 2 and e.range == "27 November – 4 December 2026"
    assert "The Loop No. 2" in (tmp_path / "report.md").read_text(encoding="utf-8")
    r = runner.invoke(app, args)
    assert r.exit_code == 1 and "already exists" in r.output


def test_fetch_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.conftest import mock_http, substack_routes
    from timeleaf.fetch import http as http_mod

    monkeypatch.setattr(http_mod, "Http", lambda: mock_http(substack_routes()))
    out = tmp_path / "c.json"
    r = runner.invoke(app, ["fetch", "-o", str(out), "--sources", str(ROOT / "tests/fixtures/sources.json")])
    assert r.exit_code == 0, r.output
    assert "seed posts 2" in r.output
    assert Candidates.model_validate_json(out.read_text(encoding="utf-8")).lesswrong
