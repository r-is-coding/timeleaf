# Runbook

How to run, fix and change Timeleaf. Commands assume the repo root and [uv](https://docs.astral.sh/uv/).

## Local setup

```bash
uv sync                                  # Python 3.12 + dependencies (from uv.lock)
uv run pre-commit install                # optional: lint, format, mypy and secret scan on commit
uv run pytest                            # tests, no network
uv run timeleaf build && uv run timeleaf serve   # http://127.0.0.1:8000
```

## The weekly cycle

1. **Friday 05:00 UTC** `weekly-edition.yml` runs: fetch → Claude drafts → validate → opens PR **"Edition N · DATE"** labelled `edition`.
2. **Review the PR.** Read the run summary in the PR body, open the preview (artifact `preview-DATE` from the run), and read every item.
3. **Edit if needed** directly in GitHub: open `content/editions/DATE.json` in the PR → pencil icon → commit to the same branch. CI re-validates.
4. **Merge.** `deploy.yml` publishes to https://timeleaf.ee within a couple of minutes.

To skip a week, close the PR without merging.

## Common tasks

| Task | How |
|---|---|
| Run an edition now | Actions → *Weekly edition* → *Run workflow* |
| See what it would cost without spending | Same, with **dry_run** ticked |
| Make an edition on a laptop | `uv run timeleaf fetch -o candidates.json` → `uv run timeleaf edit candidates.json` (needs `ANTHROPIC_API_KEY` or `ant auth login`) → `uv run timeleaf validate content/editions/DATE.json --candidates candidates.json` → commit on a branch, open a PR |
| Re-draft an edition | Delete the PR branch, run the workflow again (or locally `timeleaf edit … --force`) |
| Fix a typo in a published edition | PR that edits `content/editions/DATE.json`; merge |
| Change friends, seeds or signals | Edit `config/sources.json` in a PR |
| Change the editor's instructions | Edit `src/timeleaf/edit/prompt.md` in a PR; see *Changing the prompt* |
| Hide the site from search engines | Set `"indexable": false` in `config/site.json` |
| Turn on the feedback form | Create a Formspree form, set `"feedback_form_action": "https://formspree.io/f/<id>"` in `config/site.json` |

## When something fails

**`edition-failed` issue opened.** Open the linked run.
- *Fetch failed / 0 requests ok*: Substack may be blocking GitHub's IP ranges. Check the canary. Run the fetch on a laptop and continue locally (table above).
- *Estimated cost is above the cap*: candidates are unusually large. Re-run with a shorter window, or locally with `--max-cost`.
- *Editor failed validation after repair*: the log lists the rule broken (`provenance`, `friends`, `item-cap`, …). Re-run once; if it repeats, the prompt or the candidates need a look.
- *Refusal*: the model declined. Re-run; the server-side fallback should already have tried another model. If it repeats, find the candidate that triggers it.
- *`ANTHROPIC_API_KEY` missing / 401*: add or rotate the secret (below).

**`canary-failed` issue opened.** An endpoint changed shape or blocks us. Run `uv run timeleaf canary` locally to see which. Update `src/timeleaf/fetch/substack.py` and the fixtures in `tests/fixtures/`.

**Scheduled runs stopped.** GitHub disables cron workflows in public repos after 60 days without commits. Actions → *Weekly edition* → *Enable workflow*.

**Site down or certificate error.** Settings → Pages: custom domain must be `timeleaf.ee`, *Enforce HTTPS* on. Check DNS records against docs/PLAN.md §4.1.

## Secrets

| Secret | Where | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | Settings → Environments → `edition` | weekly-edition.yml |
| `EDITION_BOT_TOKEN` (optional) | Settings → Environments → `edition` | weekly-edition.yml, to open PRs that trigger CI |

Rotate: create the new key, update the secret, run the workflow with *dry_run*, then revoke the old key. Never paste keys into issues, PRs or chat.

`EDITION_BOT_TOKEN`: a fine-grained personal access token limited to this repository with *Contents: read and write* and *Pull requests: read and write* (or a GitHub App with the same permissions). Without it, PRs are still opened, but CI does not run on them automatically; close and reopen the PR to trigger it.

## Changing the prompt

1. Download the last three `candidates-*` artifacts from past runs.
2. On a branch, for each: `uv run timeleaf edit candidates.json --date <that date> -o /tmp/new-<date>.json`.
3. Compare with the published edition for that week: validator warnings, item mix, voice. Write down what changed in the PR.
4. Merge only if it is better on at least two of three and worse on none.

## Changing templates or styles

Run `UPDATE_GOLDEN=1 uv run pytest` and review the diff of `tests/golden/` in the PR: it shows exactly what readers will see change.

## Changing the data model

Edit `src/timeleaf/models.py`, run `uv run timeleaf schema`, commit `docs/schemas/`. A breaking change bumps `schema_version` and needs a migration of the files in `content/editions/`.
