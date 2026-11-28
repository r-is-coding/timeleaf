"""Command line: `timeleaf fetch | edit | validate | build | serve | canary | schema | reader ...`.

Commands that are about one reader take ``--reader <id>``. Without it they use the only reader, or
``primary_reader`` from config/site.json when there are several.
"""

from __future__ import annotations

import datetime as dt
import functools
import http.server
import json
import os
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from timeleaf import readers as rd
from timeleaf.build.render import SiteConfig, load_editions
from timeleaf.build.render import build as build_site
from timeleaf.models import Candidates, Draft, Edition, Reader, Sources
from timeleaf.readers import ReaderError, ReaderHome
from timeleaf.validate import Finding, errors
from timeleaf.validate import validate as validate_edition

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)
reader_app = typer.Typer(no_args_is_help=True, help="Add, list, check and remove readers (readers/<id>/).")
app.add_typer(reader_app, name="reader")

SITE = Path("config/site.json")

Opt = typer.Option
ReaderOpt = Annotated[str | None, Opt("--reader", help="Reader id (default: the only or primary reader)")]
ReadersOpt = Annotated[Path, Opt("--readers", help="Folder that holds one folder per reader")]
SiteOpt = Annotated[Path, Opt("--site", help="Site config")]


def _gh_annotate(f: Finding, file: Path) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{f.severity} file={file.as_posix()}::{f.message}")


def _site(path: Path) -> SiteConfig | None:
    return SiteConfig.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


def _primary(site: Path) -> str | None:
    cfg = _site(site)
    return cfg.primary_reader if cfg else None


def _home(root: Path, reader_id: str | None, site: Path) -> ReaderHome:
    try:
        return rd.load(root, rd.resolve(root, reader_id, _primary(site)))
    except ReaderError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from e


@app.command()
def fetch(
    out: Annotated[Path, Opt("-o", "--out", help="Where to write candidates JSON")] = Path("candidates.json"),
    days: Annotated[int, Opt(help="Window in days")] = 7,
    reader: ReaderOpt = None,
    readers: ReadersOpt = rd.READERS,
    site: SiteOpt = SITE,
) -> None:
    """Collect one reader's candidates for the week from Substack and LessWrong."""
    from timeleaf.fetch.collect import collect
    from timeleaf.fetch.http import Http

    home = _home(readers, reader, site)
    http = Http()
    try:
        res = collect(home.sources, http, days=days)
    finally:
        http.close()
    out.write_text(res.model_dump_json(indent=1), encoding="utf-8")
    h = res.health
    typer.echo(
        f"friends {len(res.friends)} | seed posts {len(res.seeds)} | signals {len(res.signals)} | "
        f"LW {len(res.lesswrong)} | co-cited {len(res.co_cited)} | ok {h.ok} failed {len(h.failed)}"
    )
    for f in h.failed:
        typer.echo(f"FAILED {f}", err=True)
    if h.ok == 0:
        raise typer.Exit(1)


@app.command()
def edit(
    candidates: Annotated[Path, typer.Argument(help="Candidates JSON from `timeleaf fetch`")],
    date: Annotated[
        str | None, Opt(help="Edition date YYYY-MM-DD (default: day the candidates were fetched)")
    ] = None,
    reader: ReaderOpt = None,
    readers: ReadersOpt = rd.READERS,
    site: SiteOpt = SITE,
    out: Annotated[Path | None, Opt("-o", "--out")] = None,
    max_cost: Annotated[
        float | None, Opt(help="Abort if the estimated cost in US$ is above this (default: the reader's cap)")
    ] = None,
    report: Annotated[Path | None, Opt(help="Write a Markdown run summary here (for the PR body)")] = None,
    dry_run: Annotated[bool, Opt(help="Only estimate the cost; do not call the model")] = False,
    force: Annotated[bool, Opt(help="Overwrite an existing edition file")] = False,
) -> None:
    """Draft a reader's edition with Claude, validate it, and write it to readers/<id>/editions/."""
    import anthropic

    from timeleaf.edit.editor import EditorError, anthropic_call, estimate_cost
    from timeleaf.edit.editor import edit as run_edit

    home = _home(readers, reader, site)
    c = Candidates.model_validate_json(candidates.read_text(encoding="utf-8"))
    day = dt.date.fromisoformat(date) if date else c.generated.date()
    target = out or home.editions / f"{day.isoformat()}.json"
    if target.exists() and not force:
        typer.echo(f"{target} already exists (use --force to overwrite)", err=True)
        raise typer.Exit(1)
    previous = [e for e in load_editions(home.editions) if e.date < day] if home.editions.is_dir() else []
    prev = previous[-1] if previous else None
    cap = max_cost if max_cost is not None else home.reader.max_cost_usd
    client = anthropic.Anthropic()

    estimate = estimate_cost(client, c, home, prev, day)
    typer.echo(f"Estimated cost: ${estimate:.2f} (cap ${cap:.2f})")
    if estimate > cap:
        typer.echo("Estimated cost is above the cap; not calling the model.", err=True)
        raise typer.Exit(2)
    if dry_run:
        return
    try:
        edition, stats = run_edit(c, home, prev, day, anthropic_call(client))
    except EditorError as e:
        typer.echo(f"Editor failed: {e}", err=True)
        raise typer.Exit(1) from e
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(edition.model_dump_json(indent=1) + "\n", encoding="utf-8", newline="\n")
    typer.echo(
        f"Wrote {target}: {edition.item_count} items, {stats.calls} call(s), ${stats.cost_usd:.2f}, "
        f"{len(stats.findings)} warning(s)"
    )
    if report:
        report.write_text(
            run_report(
                edition, c, stats.findings, stats.model, stats.usage, stats.cost_usd, reader=home.reader
            ),
            encoding="utf-8",
        )


def run_report(
    e: Edition,
    c: Candidates,
    findings: list[Finding],
    model: str,
    usage: dict[str, int],
    cost: float,
    *,
    reader: Reader,
) -> str:
    lines = [
        f"## {reader.paper_name} No. {e.number} · {e.range}",
        "",
        f"> {e.lede}",
        "",
        "| Section | Items |",
        "|---|---|",
        *[f"| {s.title} | {len(s.items)} |" for s in e.sections],
        f"| **Total** | **{e.item_count}** |",
        "",
        "### Run",
        f"- Requests: {c.health.ok} ok, {len(c.health.failed)} failed"
        + (" (fell back to a browser User-Agent)" if c.health.user_agent_fallback else ""),
        f"- Candidates: {len(c.seeds)} seed posts, {len(c.lesswrong)} LessWrong, {len(c.signals)} signals, "
        f"{sum(len(f.new_posts) for f in c.friends)} new friend posts",
        f"- Model: `{model}` · tokens in {usage.get('input_tokens', 0):,}"
        f" / out {usage.get('output_tokens', 0):,}"
        f" · cache read {usage.get('cache_read_input_tokens', 0):,} · **${cost:.2f}**",
    ]
    if c.health.failed:
        lines += [
            "",
            "<details><summary>Failed requests</summary>",
            "",
            *[f"- {f}" for f in c.health.failed],
            "",
            "</details>",
        ]
    warns = [f for f in findings if f.severity == "warning"]
    if warns:
        lines += ["", "### Warnings", *[f"- {f.message}" for f in warns]]
    if reader.review == "pr":
        lines += [
            "",
            "### Before merging",
            "- [ ] Read every item; edit the JSON in this PR if needed",
            "- [ ] Friends' posts are all there",
            "- [ ] Nothing here you would not want public",
        ]
    return "\n".join(lines) + "\n"


def _reader_of(path: Path, root: Path) -> str | None:
    """The reader an edition file belongs to, if it sits in readers/<id>/editions/."""
    parts = path.resolve().parts
    base = root.resolve().parts
    if parts[: len(base)] == base and len(parts) == len(base) + 3 and parts[-2] == "editions":
        return parts[len(base)]
    return None


@app.command()
def validate(
    files: Annotated[list[Path] | None, typer.Argument(help="Edition files (default: all)")] = None,
    candidates: Annotated[
        Path | None, Opt(help="Also check URL provenance, friends and the source cap")
    ] = None,
    reader: ReaderOpt = None,
    readers: ReadersOpt = rd.READERS,
    site: SiteOpt = SITE,
) -> None:
    """Check editions against the schema, the editorial rules and their reader's sections.

    With no arguments, every reader's editions are checked.
    """
    work: list[tuple[ReaderHome, list[Path]]] = []
    if files:
        by_reader: dict[str | None, list[Path]] = {}
        for p in files:
            by_reader.setdefault(reader or _reader_of(p, readers), []).append(p)
        work = [(_home(readers, rid, site), paths) for rid, paths in by_reader.items()]
    elif reader or candidates:
        home = _home(readers, reader, site)
        work = [(home, sorted(home.editions.glob("*.json")))]
    else:
        for rid in rd.list_ids(readers):
            home = _home(readers, rid, site)
            work.append((home, sorted(home.editions.glob("*.json"))))
        if not work:
            typer.echo(f"no readers in {readers}", err=True)
            raise typer.Exit(2)
    cand = Candidates.model_validate_json(candidates.read_text(encoding="utf-8")) if candidates else None
    failed = False
    for home, paths in work:
        if not paths:
            typer.echo(f"{home.id}: no editions yet")
        for p in paths:
            try:
                e = Edition.model_validate_json(p.read_text(encoding="utf-8"))
            except ValueError as ex:
                typer.echo(f"{p}: does not match the Edition schema:\n{ex}", err=True)
                failed = True
                continue
            findings = validate_edition(e, cand, home.reader, home.sources)
            for f in findings:
                typer.echo(f"{p}: {f}")
                _gh_annotate(f, p)
            failed |= bool(errors(findings))
            if not findings:
                typer.echo(f"{p}: ok ({e.item_count} items)")
    if failed:
        raise typer.Exit(1)


@app.command()
def build(
    out: Annotated[Path, Opt("-o", "--out")] = Path("_site"),
    reader: ReaderOpt = None,
    readers: ReadersOpt = rd.READERS,
    site: SiteOpt = SITE,
) -> None:
    """Render one reader's paper into a static site. Without --reader this is the public site.

    Only that reader's folder is read: no other reader's paper is ever part of the build.
    """
    cfg = SiteConfig.model_validate_json(site.read_text(encoding="utf-8"))
    home = _home(readers, reader, site)
    pages = build_site(home.editions, out, cfg, paper_name=home.reader.paper_name)
    typer.echo(f"Built {len(pages)} pages of {home.reader.paper_name} into {out}")


@app.command()
def serve(
    directory: Annotated[Path, Opt("-d", "--dir")] = Path("_site"),
    port: Annotated[int, Opt()] = 8000,
) -> None:
    """Serve the built site locally."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        typer.echo(f"Serving {directory} at http://127.0.0.1:{port}/ (Ctrl+C to stop)")
        httpd.serve_forever()


@app.command()
def canary(reader: ReaderOpt = None, readers: ReadersOpt = rd.READERS, site: SiteOpt = SITE) -> None:
    """Check that every source endpoint still answers with the shape we depend on."""
    from timeleaf.fetch import lesswrong
    from timeleaf.fetch.http import Http
    from timeleaf.fetch.substack import Substack

    src = _home(readers, reader, site).sources
    http = Http(retries=2)
    ss = Substack(http)
    problems: list[str] = []
    if src.me:
        me = ss.profile(src.me)
        if not me or "subscriptions" not in me:
            problems.append("Substack public_profile: no profile or no 'subscriptions'")
    if src.friends:
        friend = ss.profile(src.friends[0].handle)
        if not friend or "id" not in friend:
            problems.append("Substack public_profile (friend): no 'id'")
        else:
            posts = ss.posts_by(friend["id"], 1)
            if not posts:
                problems.append("Substack profile/posts: no posts")
            elif "body_html" not in ss.full(posts[0]):
                problems.append("Substack posts/by-id: no 'body_html'")
            if not http.json(f"https://substack.com/api/v1/reader/feed/profile/{friend['id']}"):
                problems.append("Substack reader/feed/profile: no response")
    if src.publications:
        pub = src.publications[0]
        archive = ss.archive(pub.url)
        if not archive:
            problems.append(f"Substack archive ({pub.name}): no posts")
        elif "body_html" not in ss.full(archive[0]):
            problems.append(f"Substack posts/by-id ({pub.name}): no 'body_html'")
    if src.lesswrong and not lesswrong.top_posts(http, dt.date.today() - dt.timedelta(days=14), limit=3):
        problems.append("LessWrong graphql: no results")
    http.close()
    for p in problems:
        typer.echo(f"CANARY FAILED: {p}", err=True)
    for f in http.health.failed:
        typer.echo(f"request failed: {f}", err=True)
    if problems:
        raise typer.Exit(1)
    typer.echo(f"All source endpoints OK ({http.health.ok} requests)")


@app.command()
def schema(out: Annotated[Path, Opt("-o", "--out")] = Path("docs/schemas")) -> None:
    """Write the JSON Schemas for the data contracts (ADR 0004)."""
    out.mkdir(parents=True, exist_ok=True)
    models: dict[str, type[BaseModel]] = {
        "reader": Reader,
        "sources": Sources,
        "candidates": Candidates,
        "edition": Edition,
        "draft": Draft,
    }
    for name, model in models.items():
        (out / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    typer.echo(f"Wrote schemas to {out}")


# --------------------------------------------------------------------------- readers


@reader_app.command("add")
def reader_add(
    reader_id: Annotated[str, typer.Argument(metavar="ID", help="Short id: lower-case letters, digits, -")],
    paper_name: Annotated[str, Opt("--paper-name", help="What the reader calls their paper")],
    email: Annotated[str | None, Opt(help="The address they will log in with")] = None,
    timezone: Annotated[str, Opt()] = "Europe/Tallinn",
    substack: Annotated[str | None, Opt(help="Their Substack handle, if they have one")] = None,
    readers: ReadersOpt = rd.READERS,
) -> None:
    """Create readers/<id>/ with templates to fill in from the questionnaire (docs/onboarding.md)."""
    try:
        folder = rd.scaffold(
            readers, reader_id, paper_name, email=email, timezone=timezone, substack=substack
        )
    except ReaderError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"Created {folder}")
    typer.echo("Next: fill in profile.md and sources.json from the reader's answers, then run")
    typer.echo(f"  timeleaf reader check {reader_id}")
    typer.echo("This is personal data: do not commit it while the repository is public.")


@reader_app.command("list")
def reader_list(
    as_json: Annotated[bool, Opt("--json", help="Machine-readable, for the workflows")] = False,
    readers: ReadersOpt = rd.READERS,
    site: SiteOpt = SITE,
) -> None:
    """List the readers."""
    ids = rd.list_ids(readers)
    try:
        homes = [rd.load(readers, i) for i in ids]
    except ReaderError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    if as_json:
        rows = [{"id": h.id, "paper_name": h.reader.paper_name, "review": h.reader.review} for h in homes]
        typer.echo(json.dumps(rows))
        return
    primary = _public_reader(readers, site)
    for h in homes:
        n = len(list(h.editions.glob("*.json")))
        mark = " (public site)" if h.id == primary else ""
        typer.echo(f"{h.id}: {h.reader.paper_name} · review {h.reader.review} · {n} edition(s){mark}")
    if not homes:
        typer.echo(f"no readers in {readers}")


def _public_reader(root: Path, site: Path) -> str | None:
    """The reader whose paper `timeleaf build` renders by default, i.e. the public site."""
    try:
        return rd.resolve(root, None, _primary(site))
    except ReaderError:
        return None


@reader_app.command("check")
def reader_check(
    reader_id: Annotated[str | None, typer.Argument(metavar="[ID]", help="Default: every reader")] = None,
    readers: ReadersOpt = rd.READERS,
    site: SiteOpt = SITE,
) -> None:
    """Check that a reader's folder is complete and valid."""
    ids = [reader_id] if reader_id else rd.list_ids(readers)
    if not ids:
        typer.echo(f"no readers in {readers}", err=True)
        raise typer.Exit(1)
    public = _public_reader(readers, site)
    failed = False
    for i in ids:
        problems = rd.check(readers, i, public=(i == public))
        for p in problems:
            typer.echo(f"{i}: {p}", err=True)
        if not problems:
            typer.echo(f"{i}: ok")
        failed |= bool(problems)
    if failed:
        raise typer.Exit(1)


@reader_app.command("remove")
def reader_remove(
    reader_id: Annotated[str, typer.Argument(metavar="ID")],
    yes: Annotated[bool, Opt("--yes", help="Do not ask for confirmation")] = False,
    readers: ReadersOpt = rd.READERS,
) -> None:
    """Delete a reader's folder: their profile, sources, notes and every edition."""
    if reader_id not in rd.list_ids(readers):
        typer.echo(f"no reader {reader_id!r} in {readers}", err=True)
        raise typer.Exit(1)
    if not yes:
        typer.confirm(f"Delete {readers / reader_id} and everything in it?", abort=True)
    folder = rd.remove(readers, reader_id)
    typer.echo(f"Deleted {folder}")
    typer.echo("Commit the deletion. See docs/runbook.md (Removing a reader) for git history and backups.")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
