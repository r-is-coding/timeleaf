from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.conftest import EDITION1, FIXTURE_READERS, READERS, ROOT
from timeleaf import readers as rd
from timeleaf.cli import app, run_report
from timeleaf.models import Candidates, Edition
from timeleaf.readers import ReaderError, ReaderHome
from timeleaf.validate import validate

runner = CliRunner()
SITE = str(ROOT / "config/site.json")


def test_defaults_work_from_the_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`timeleaf validate` and `timeleaf build -o X` need no other arguments."""
    monkeypatch.chdir(ROOT)
    r = runner.invoke(app, ["validate"])
    assert r.exit_code == 0, r.output
    assert "WARNING [duplicate]" in r.output
    r = runner.invoke(app, ["build", "-o", str(tmp_path / "site")])
    assert r.exit_code == 0, r.output
    assert "The Loop" in (tmp_path / "site/index.html").read_text(encoding="utf-8")
    r = runner.invoke(app, ["reader", "check"])
    assert r.exit_code == 0, r.output
    assert "richard: ok" in r.output


def test_validate_reports_errors(tmp_path: Path, edition1: Edition) -> None:
    e = edition1.model_copy(deep=True)
    e.sections[0].items[0].why = ""
    p = tmp_path / "bad.json"
    p.write_text(e.model_dump_json(), encoding="utf-8")
    r = runner.invoke(app, ["validate", str(p), "--readers", str(READERS)])
    assert r.exit_code == 1
    assert "ERROR [why]" in r.output


def test_validate_schema_failure(tmp_path: Path) -> None:
    p = tmp_path / "broken.json"
    p.write_text(json.dumps({"number": 1}), encoding="utf-8")
    r = runner.invoke(app, ["validate", str(p), "--readers", str(READERS)])
    assert r.exit_code == 1


def test_validate_is_per_reader(two_readers: Path) -> None:
    args = ["--readers", str(two_readers), "--site", SITE]
    # every reader by default; a reader with no editions is not an error
    r = runner.invoke(app, ["validate", *args])
    assert r.exit_code == 0, r.output
    assert "juniper: no editions yet" in r.output and "2026-11-27.json" in r.output
    # a file is checked against the reader whose folder it is in ...
    mine = two_readers / "richard/editions/2026-11-27.json"
    assert runner.invoke(app, ["validate", str(mine), *args]).exit_code == 0
    # ... so The Loop's edition in The Kettle's folder fails on its sections
    (two_readers / "juniper/editions").mkdir()
    theirs = two_readers / "juniper/editions/2026-11-27.json"
    shutil.copy(mine, theirs)
    r = runner.invoke(app, ["validate", str(theirs), *args])
    assert r.exit_code == 1 and "ERROR [sections]" in r.output
    assert runner.invoke(app, ["validate", "--reader", "richard", *args]).exit_code == 0
    assert runner.invoke(app, ["validate", "--reader", "juniper", *args]).exit_code == 1
    assert runner.invoke(app, ["validate", "--readers", str(two_readers / "nowhere")]).exit_code == 2


def test_reader_resolution(two_readers: Path, tmp_path: Path) -> None:
    assert rd.resolve(READERS, None) == "richard"  # the only reader
    assert rd.resolve(two_readers, None, "richard") == "richard"  # the primary reader
    assert rd.resolve(two_readers, "juniper", "richard") == "juniper"
    with pytest.raises(ReaderError, match="pass --reader"):
        rd.resolve(two_readers, None, None)
    with pytest.raises(ReaderError, match="no reader 'nobody'"):
        rd.resolve(two_readers, "nobody")
    with pytest.raises(ReaderError, match="no readers"):
        rd.resolve(tmp_path, None)
    r = runner.invoke(app, ["build", "--readers", str(two_readers), "--site", SITE, "--reader", "nobody"])
    assert r.exit_code == 2 and "no reader 'nobody'" in r.output


def test_build_and_schema(tmp_path: Path) -> None:
    out = tmp_path / "site"
    r = runner.invoke(app, ["build", "-o", str(out), "--readers", str(READERS), "--site", SITE])
    assert r.exit_code == 0, r.output
    assert (out / "index.html").exists()
    r = runner.invoke(app, ["schema", "-o", str(tmp_path / "schemas")])
    assert r.exit_code == 0
    assert (
        json.loads((tmp_path / "schemas/edition.schema.json").read_text(encoding="utf-8"))["title"]
        == "Edition"
    )
    assert (tmp_path / "schemas/reader.schema.json").is_file()


def test_committed_schemas_are_current(tmp_path: Path) -> None:
    runner.invoke(app, ["schema", "-o", str(tmp_path)])
    for f in tmp_path.iterdir():
        committed = ROOT / "docs/schemas" / f.name
        assert committed.read_text(encoding="utf-8") == f.read_text(encoding="utf-8"), (
            f"{committed} is stale: run `uv run timeleaf schema`"
        )


def test_run_report(
    edition1: Edition, candidates: Candidates, richard: ReaderHome, juniper: ReaderHome
) -> None:
    args = (
        edition1,
        candidates,
        validate(edition1),
        "claude-opus-5-5",
        {"input_tokens": 1234, "output_tokens": 56},
        0.42,
    )
    md = run_report(*args, reader=richard.reader)
    assert "The Loop No. 1" in md and "| **Total** | **17** |" in md
    assert "$0.42" in md and "### Warnings" in md and "- [ ] Read every item" in md
    auto = run_report(*args, reader=juniper.reader)  # review: auto, so there is no PR to tick boxes in
    assert "The Kettle No. 1" in auto and "Before merging" not in auto


class _FakeAnthropic:
    """Stands in for anthropic.Anthropic in CLI tests; the editor call itself is patched separately."""

    class messages:
        @staticmethod
        def count_tokens(**_kw: object) -> object:
            return type("Count", (), {"input_tokens": 50_000})()


def _setup_edit(tmp_path: Path, candidates: Candidates, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A readers folder with only the fixture reader, who already has one (borrowed) edition."""
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _FakeAnthropic)
    root = tmp_path / "readers"
    shutil.copytree(FIXTURE_READERS / "juniper", root / "juniper")
    (root / "juniper/editions").mkdir()
    shutil.copy(EDITION1, root / "juniper/editions")
    cand = tmp_path / "candidates.json"
    c = candidates.model_copy(update={"generated": candidates.generated + dt.timedelta(days=7)})
    cand.write_text(c.model_dump_json(), encoding="utf-8")
    return ["edit", str(cand), "--readers", str(root)]


def test_edit_dry_run_and_cost_cap(
    tmp_path: Path, candidates: Candidates, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _setup_edit(tmp_path, candidates, monkeypatch)
    r = runner.invoke(app, [*args, "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Estimated cost: $0.80 (cap $2.00)" in r.output  # the cap is the reader's own
    r = runner.invoke(app, [*args, "--max-cost", "0.5"])
    assert r.exit_code == 2
    assert not (tmp_path / "readers/juniper/editions/2026-12-04.json").exists()


def test_edit_writes_edition_and_report(
    tmp_path: Path, candidates: Candidates, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_editor import FakeModel, good_draft, reply
    from timeleaf.edit import editor

    args = _setup_edit(tmp_path, candidates, monkeypatch)
    monkeypatch.setattr(editor, "anthropic_call", lambda _client: FakeModel(reply(good_draft())))
    r = runner.invoke(app, [*args, "--report", str(tmp_path / "report.md")])
    assert r.exit_code == 0, r.output
    target = tmp_path / "readers/juniper/editions/2026-12-04.json"
    e = Edition.model_validate_json(target.read_text(encoding="utf-8"))
    assert e.number == 2 and e.range == "27 November – 4 December 2026"
    assert "the allotment society's mailing list" in e.colophon.blind
    assert "The Kettle No. 2" in (tmp_path / "report.md").read_text(encoding="utf-8")
    r = runner.invoke(app, args)
    assert r.exit_code == 1 and "already exists" in r.output
    # the new edition passes the same checks the workflow runs next
    r = runner.invoke(app, ["validate", str(target), "--candidates", args[1], "--readers", args[3]])
    assert r.exit_code == 0, r.output


def test_edit_reports_editor_failure(
    tmp_path: Path, candidates: Candidates, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_editor import FakeModel, reply
    from timeleaf.edit import editor

    args = _setup_edit(tmp_path, candidates, monkeypatch)
    monkeypatch.setattr(editor, "anthropic_call", lambda _client: FakeModel(reply("", "refusal")))
    r = runner.invoke(app, args)
    assert r.exit_code == 1 and "Editor failed" in r.output


def _mock_network(monkeypatch: pytest.MonkeyPatch, fail: set[str] | None = None) -> None:
    from tests.conftest import mock_http, substack_routes
    from timeleaf.fetch import http as http_mod

    routes = substack_routes()
    # the canary asks for one post only
    routes["/api/v1/profile/posts?profile_user_id=10&limit=1"] = routes[
        "/api/v1/profile/posts?profile_user_id=10&limit=6"
    ]
    monkeypatch.setattr(http_mod, "Http", lambda **_kw: mock_http(routes, fail=fail))


def test_fetch_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_network(monkeypatch)
    out = tmp_path / "c.json"
    r = runner.invoke(app, ["fetch", "-o", str(out), "--readers", str(FIXTURE_READERS)])
    assert r.exit_code == 0, r.output
    assert "seed posts 4" in r.output
    assert Candidates.model_validate_json(out.read_text(encoding="utf-8")).lesswrong


def test_canary_checks_a_publication_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_network(monkeypatch)
    r = runner.invoke(app, ["canary", "--readers", str(FIXTURE_READERS)])
    assert r.exit_code == 0, r.output
    assert "All source endpoints OK" in r.output

    _mock_network(monkeypatch, fail={"fieldnotes.example/api/v1/archive?sort=new&limit=12"})
    r = runner.invoke(app, ["canary", "--readers", str(FIXTURE_READERS)])
    assert r.exit_code == 1
    assert "CANARY FAILED: Substack archive (Field Notes): no posts" in r.output


# --------------------------------------------------------------------------- timeleaf reader ...


def test_reader_add_check_list_remove(tmp_path: Path) -> None:
    root = tmp_path / "readers"
    opts = ["--readers", str(root)]
    r = runner.invoke(
        app, ["reader", "add", "wren", "--paper-name", "The Hedgerow", "--email", "wren@example.org", *opts]
    )
    assert r.exit_code == 0, r.output
    assert "do not commit it while the repository is public" in r.output
    for f in ["reader.json", "profile.md", "sources.json", "notes.md", "editions/.gitkeep"]:
        assert (root / "wren" / f).is_file(), f
    home = rd.load(root, "wren")
    assert home.reader.paper_name == "The Hedgerow" and home.reader.email == "wren@example.org"
    assert home.reader.review == "pr" and home.reader.max_cost_usd == 2.0
    assert [s.kind for s in home.reader.sections] == ["news", "essay", "friend", "edge"]

    # a fresh scaffold is not ready: the templates have to be filled in
    r = runner.invoke(app, ["reader", "check", "wren", *opts])
    assert r.exit_code == 1
    assert "profile.md is not filled in" in r.output and "at least 3" in r.output

    # never overwrites, and ids are slugs
    assert runner.invoke(app, ["reader", "add", "wren", "--paper-name", "X", *opts]).exit_code == 1
    r = runner.invoke(app, ["reader", "add", "Not A Slug", "--paper-name", "X", *opts])
    assert r.exit_code == 1 and "not a valid id" in r.output

    # fill it in from the fixture reader's answers
    for f in ["profile.md", "sources.json"]:
        shutil.copy(FIXTURE_READERS / "juniper" / f, root / "wren" / f)
    r = runner.invoke(app, ["reader", "check", "wren", *opts])
    assert r.exit_code == 0, r.output

    r = runner.invoke(app, ["reader", "list", *opts])
    assert "wren: The Hedgerow · review pr · 0 edition(s) (public site)" in r.output
    r = runner.invoke(app, ["reader", "list", "--json", *opts])
    assert json.loads(r.output) == [{"id": "wren", "paper_name": "The Hedgerow", "review": "pr"}]

    assert runner.invoke(app, ["reader", "remove", "wren", *opts], input="n\n").exit_code == 1
    assert (root / "wren").is_dir()
    r = runner.invoke(app, ["reader", "remove", "wren", "--yes", *opts])
    assert r.exit_code == 0 and not (root / "wren").exists()
    assert runner.invoke(app, ["reader", "remove", "wren", "--yes", *opts]).exit_code == 1
    assert "no readers" in runner.invoke(app, ["reader", "list", *opts]).output
    assert runner.invoke(app, ["reader", "check", *opts]).exit_code == 1


def test_reader_check_finds_problems(two_readers: Path) -> None:
    def problems(reader_id: str = "juniper", **kw: bool) -> str:
        return " | ".join(rd.check(two_readers, reader_id, **kw))

    assert problems() == "" and problems("richard", public=True) == ""
    # value 10: a paper on the public site is approved by a person
    assert 'review must be "pr"' in problems(public=True)

    folder = two_readers / "juniper"
    reader = json.loads((folder / "reader.json").read_text(encoding="utf-8"))
    sources = json.loads((folder / "sources.json").read_text(encoding="utf-8"))

    def write(name: str, data: dict[str, object]) -> None:
        (folder / name).write_text(json.dumps(data), encoding="utf-8")

    write("reader.json", reader | {"id": "someone-else"})
    assert "must match the folder name" in problems()
    write("reader.json", reader | {"sections": [s for s in reader["sections"] if s["kind"] != "friend"]})
    assert "no section in reader.json has kind 'friend'" in problems()
    write("reader.json", reader | {"sections": reader["sections"] + reader["sections"][2:3]})
    assert "section ids must be unique" in problems() and "at most one section" in problems()
    write("reader.json", reader | {"paper_name": "TODO"})
    assert "reader.json still has a TODO" in problems()
    write("reader.json", reader | {"surprise": 1})
    assert "Extra inputs are not permitted" in problems()
    write("reader.json", reader)

    write("sources.json", {"friends": [], "publications": sources["publications"], "roundups": ["Nope"]})
    assert "names 2 trusted people or publications" in problems()
    assert "roundup 'Nope' is not one of the publications" in problems()
    write("sources.json", sources)

    (folder / "editions").mkdir()
    (folder / "editions/2026-11-27.json").write_text("{}", encoding="utf-8")
    assert "editions/2026-11-27.json does not match the Edition schema" in problems()
    (folder / "profile.md").unlink()
    assert "missing profile.md" in problems()

    r = runner.invoke(app, ["reader", "check", "--readers", str(two_readers), "--site", SITE])
    assert r.exit_code == 1 and "richard: ok" in r.output and "juniper: " in r.output
    assert runner.invoke(app, ["reader", "list", "--readers", str(two_readers)]).exit_code == 1


def test_no_real_person_but_the_owner_is_in_the_repo() -> None:
    """Until the paper is behind a login the repository is public (DECISIONS note 6)."""
    assert rd.list_ids(READERS) == ["richard"]
    assert rd.load(READERS, "richard").reader.email is None
