# Timeleaf

Source for **[timeleaf.ee](https://timeleaf.ee)**, home of *The Loop*: a finite weekly newspaper on AI safety, AI policy and the writing around them, built from what trusted people pointed at, not from a feed.

Each Friday a workflow fetches candidates (Substack, LessWrong), Claude drafts the edition, validators check it, and it arrives as a pull request. **Merging the PR publishes it.**

```
config/sources.json ─► timeleaf fetch ─► candidates.json ─► timeleaf edit (Claude) ─► content/editions/DATE.json ─► timeleaf build ─► timeleaf.ee
```

## Quick start

```bash
uv sync
uv run pytest
uv run timeleaf build && uv run timeleaf serve     # http://127.0.0.1:8000
```

| Command | Does |
|---|---|
| `timeleaf fetch -o candidates.json` | Collect the week's candidates (network) |
| `timeleaf edit candidates.json` | Draft, validate and write an edition with Claude (`--dry-run` estimates the cost) |
| `timeleaf validate [FILES] [--candidates C]` | Schema + editorial rules (+ URL provenance with candidates) |
| `timeleaf build` / `serve` | Render `_site/` / serve it locally |
| `timeleaf canary` | Check the source endpoints still work |
| `timeleaf schema` | Regenerate `docs/schemas/` |

## Layout

```
config/            sources.json (who to read), site.json (domain, indexing, feedback form)
content/editions/  one JSON file per published edition: the source of truth
src/timeleaf/      fetch/ · edit/ (prompt.md + Claude call) · validate.py · build/ (Jinja templates, CSS, fonts)
tests/             no network; fixtures + golden snapshot of edition 1
docs/              PLAN.md · runbook.md · adr/ · schemas/ · PLAN-buzz.md
prototype/         the original scripts, frozen for reference
```

## Docs

- **[docs/PLAN.md](docs/PLAN.md)**: architecture, milestones, standards, open questions.
- **[docs/runbook.md](docs/runbook.md)**: the weekly cycle, failures, secrets, changing things.
- [docs/adr/](docs/adr/): architecture decisions.
- [docs/PLAN-buzz.md](docs/PLAN-buzz.md): "The Buzz" section (Milestone 4).

Fonts: Source Serif 4, Bricolage Grotesque and IBM Plex Mono, self-hosted under the SIL Open Font License 1.1.
