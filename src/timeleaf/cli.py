"""Command line: `timeleaf fetch | edit | validate | build | serve | canary | schema`."""

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

from timeleaf.build.render import SiteConfig, load_editions
from timeleaf.build.render import build as build_site
from timeleaf.models import Candidates, Draft, Edition, Sources
from timeleaf.validate import Finding, errors
from timeleaf.validate import validate as validate_edition

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)

SOURCES = Path("config/sources.json")
SITE = Path("config/site.json")
EDITIONS = Path("content/editions")

Opt = typer.Option


def _gh_annotate(f: Finding, file: Path) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{f.severity} file={file.as_posix()}::{f.message}")


def _load_sources(path: Path) -> Sources:
    return Sources.model_validate_json(path.read_text(encoding="utf-8"))


@app.command()
def fetch(
    out: Annotated[Path, Opt("-o", "--out", help="Where to write candidates JSON")] = Path("candidates.json"),
    days: Annotated[int, Opt(help="Window in days")] = 7,
    sources: Annotated[Path, Opt(help="Sources config")] = SOURCES,
) -> None:
    """Collect the week's candidates from Substack and LessWrong."""
    from timeleaf.fetch.collect import collect
    from timeleaf.fetch.http import Http

    http = Http()
    try:
        res = collect(_load_sources(sources), http, days=days)
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
    sources: Annotated[Path, Opt()] = SOURCES,
    editions: Annotated[Path, Opt()] = EDITIONS,
    out: Annotated[Path | None, Opt("-o", "--out")] = None,
    max_cost: Annotated[float, Opt(help="Abort if the estimated cost in US$ is above this")] = 3.0,
    report: Annotated[Path | None, Opt(help="Write a Markdown run summary here (for the PR body)")] = None,
    dry_run: Annotated[bool, Opt(help="Only estimate the cost; do not call the model")] = False,
    force: Annotated[bool, Opt(help="Overwrite an existing edition file")] = False,
) -> None:
    """Draft an edition with Claude, validate it, and write it to content/editions/."""
    import anthropic

    from timeleaf.edit.editor import EditorError, anthropic_call, estimate_cost
    from timeleaf.edit.editor import edit as run_edit

    c = Candidates.model_validate_json(candidates.read_text(encoding="utf-8"))
    day = dt.date.fromisoformat(date) if date else c.generated.date()
    target = out or editions / f"{day.isoformat()}.json"
    if target.exists() and not force:
        typer.echo(f"{target} already exists (use --force to overwrite)", err=True)
        raise typer.Exit(1)
    previous = [e for e in load_editions(editions) if e.date < day] if any(editions.glob("*.json")) else []
    prev = previous[-1] if previous else None
    src = _load_sources(sources)
    client = anthropic.Anthropic()

    estimate = estimate_cost(client, c, src, prev, day)
    typer.echo(f"Estimated cost: ${estimate:.2f} (cap ${max_cost:.2f})")
    if estimate > max_cost:
        typer.echo("Estimated cost is above the cap; not calling the model.", err=True)
        raise typer.Exit(2)
    if dry_run:
        return
    try:
        edition, stats = run_edit(c, src, prev, day, anthropic_call(client))
    except EditorError as e:
        typer.echo(f"Editor failed: {e}", err=True)
        raise typer.Exit(1) from e
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(edition.model_dump_json(indent=1) + "\n", encoding="utf-8")
    typer.echo(
        f"Wrote {target}: {edition.item_count} items, {stats.calls} call(s), ${stats.cost_usd:.2f}, "
        f"{len(stats.findings)} warning(s)"
    )
    if report:
        report.write_text(
            run_report(edition, c, stats.findings, stats.model, stats.usage, stats.cost_usd), encoding="utf-8"
        )


def run_report(
    e: Edition, c: Candidates, findings: list[Finding], model: str, usage: dict[str, int], cost: float
) -> str:
    lines = [
        f"## The Loop No. {e.number} · {e.range}",
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
    lines += [
        "",
        "### Before merging",
        "- [ ] Read every item; edit the JSON in this PR if needed",
        "- [ ] Friends' posts are all there",
        "- [ ] Nothing here you would not want public",
    ]
    return "\n".join(lines) + "\n"


@app.command()
def validate(
    files: Annotated[list[Path] | None, typer.Argument(help="Edition files (default: all)")] = None,
    candidates: Annotated[Path | None, Opt(help="Also check URL provenance and friends")] = None,
    editions: Annotated[Path, Opt()] = EDITIONS,
) -> None:
    """Check editions against the schema and the editorial rules."""
    paths = files or sorted(editions.glob("*.json"))
    cand = Candidates.model_validate_json(candidates.read_text(encoding="utf-8")) if candidates else None
    failed = False
    for p in paths:
        try:
            e = Edition.model_validate_json(p.read_text(encoding="utf-8"))
        except ValueError as ex:
            typer.echo(f"{p}: does not match the Edition schema:\n{ex}", err=True)
            failed = True
            continue
        findings = validate_edition(e, cand)
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
    editions: Annotated[Path, Opt()] = EDITIONS,
    site: Annotated[Path, Opt()] = SITE,
) -> None:
    """Render all editions into a static site."""
    cfg = SiteConfig.model_validate_json(site.read_text(encoding="utf-8"))
    pages = build_site(editions, out, cfg)
    typer.echo(f"Built {len(pages)} pages into {out}")


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
def canary(sources: Annotated[Path, Opt()] = SOURCES) -> None:
    """Check that every source endpoint still answers with the shape we depend on."""
    from timeleaf.fetch import lesswrong
    from timeleaf.fetch.http import Http
    from timeleaf.fetch.substack import Substack

    src = _load_sources(sources)
    http = Http(retries=2)
    ss = Substack(http)
    problems: list[str] = []
    me = ss.profile(src.me)
    if not me or "subscriptions" not in me:
        problems.append("Substack public_profile: no profile or no 'subscriptions'")
    friend = ss.profile(src.friends[0].handle) if src.friends else None
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
    if not lesswrong.top_posts(http, dt.date.today() - dt.timedelta(days=14), limit=3):
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
        "sources": Sources,
        "candidates": Candidates,
        "edition": Edition,
        "draft": Draft,
    }
    for name, model in models.items():
        (out / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    typer.echo(f"Wrote schemas to {out}")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
