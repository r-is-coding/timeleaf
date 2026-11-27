# Timeleaf

Source for **[timeleaf.ee](https://timeleaf.ee)**, home of *The Loop*: a finite weekly newspaper on AI safety, AI policy and the writing around them, built from what trusted people pointed at, not from a feed.

Each week a workflow fetches candidates (Substack, LessWrong), Claude drafts the edition, validators check it, and it arrives as a pull request. Merging the PR publishes it.

## Start here

- **[docs/PLAN.md](docs/PLAN.md)** — the implementation plan: architecture, milestones, standards, open questions.
- [docs/adr/](docs/adr/) — architecture decisions.
- [docs/PLAN-buzz.md](docs/PLAN-buzz.md) — plan for "The Buzz" section.
- [prototype/](prototype/) — the original working scripts (frozen reference).
- [content/editions/](content/editions/) — published editions (source of truth).

## Status

Planning complete. Development starts at **Milestone 0** in the plan. Until M1 lands, the prototype can be run with:

```bash
cd prototype
python fetch.py candidates.json 7
python build.py ../content/editions/2026-11-27.json
```
