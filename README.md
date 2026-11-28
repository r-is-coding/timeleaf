# Timeleaf

Source for **[timeleaf.ee](https://timeleaf.ee)**. Timeleaf makes each reader their own finite weekly paper, built from what the people they trust pointed at, not from a feed. The first paper is *The Loop*: AI safety, AI policy and the writing around them.

Each Friday a workflow fetches candidates (Substack, LessWrong), Claude drafts the edition, validators check it, and it arrives as a pull request. **Merging the PR publishes it.**

```
readers/<id>/ ─► timeleaf fetch ─► candidates.json ─► timeleaf edit (Claude) ─► readers/<id>/editions/DATE.json ─► timeleaf build ─► timeleaf.ee
```

What it is for and what it must never do: **[docs/PRINCIPLES.md](docs/PRINCIPLES.md)**.

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
| `timeleaf validate [FILES] [--candidates C]` | Schema + editorial rules + the reader's sections (+ URL provenance, friends and the source cap with candidates) |
| `timeleaf build` / `serve` | Render `_site/` / serve it locally |
| `timeleaf canary` | Check the source endpoints still work |
| `timeleaf schema` | Regenerate `docs/schemas/` |
| `timeleaf reader list` / `check [ID]` | Who has a paper / is their folder complete and valid |
| `timeleaf reader add ID --paper-name NAME` / `remove ID` | Scaffold a reader's folder / delete it |

`fetch`, `edit`, `validate`, `build` and `canary` take `--reader ID`. Without it they use the only reader, or `primary_reader` in `config/site.json`.

## Layout

```
readers/<id>/      everything about one reader: reader.json (paper name, sections, review mode),
                   profile.md (who they are), sources.json (whom to read), notes.md (their feedback),
                   editions/ (one JSON file per edition: the source of truth)
config/site.json   the site: domain, indexing, feedback form, primary_reader
src/timeleaf/      fetch/ · edit/ (prompt.md + Claude call) · validate.py · blind.py · readers.py · build/ (Jinja templates, CSS, fonts)
tests/             no network; fixtures (an invented second reader) + golden snapshot of edition 1
docs/              PRINCIPLES.md · PLAN.md · runbook.md · onboarding.md · proposals/ · adr/ · schemas/
prototype/         the original scripts, frozen for reference
```

A reader's folder is private to that reader and the owner of Timeleaf. While this repository is public it holds only the owner's.

## Docs

- **[docs/PRINCIPLES.md](docs/PRINCIPLES.md)**: intent, values, user stories.
- **[docs/PLAN.md](docs/PLAN.md)**: architecture, milestones, standards, open questions.
- **[docs/runbook.md](docs/runbook.md)**: the weekly cycle, readers, failures, secrets, changing things.
- **[docs/onboarding.md](docs/onboarding.md)**: the questionnaire a new reader fills in.
- [docs/proposals/](docs/proposals/): proposals and the owner's decisions.
- [docs/adr/](docs/adr/): architecture decisions.
- [docs/PLAN-buzz.md](docs/PLAN-buzz.md): "The Buzz" section (Milestone 4).

Fonts: Source Serif 4, Bricolage Grotesque and IBM Plex Mono, self-hosted under the SIL Open Font License 1.1.
