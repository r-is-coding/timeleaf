# Runbook

How to run, fix and change Timeleaf. Commands assume the repo root and [uv](https://docs.astral.sh/uv/).

Everything about one reader is in `readers/<id>/`. Commands take `--reader <id>`; without it they use the only reader, or `primary_reader` from `config/site.json` when there are several. Today there is one reader, `richard`, whose paper is *The Loop*.

## Local setup

```bash
uv sync                                  # Python 3.12 + dependencies (from uv.lock)
uv run pre-commit install                # optional: lint, format, mypy and secret scan on commit
uv run pytest                            # tests, no network
uv run timeleaf build && uv run timeleaf serve   # http://127.0.0.1:8000
```

## The weekly cycle

1. **Friday 05:00 UTC** `weekly-edition.yml` runs once for each reader: fetch → Claude drafts → validate. What happens next depends on `review` in the reader's `reader.json`.
2. **`review: "pr"`** (*The Loop*): it opens PR **"The Loop · Edition N · DATE"** labelled `edition`.
   1. **Review the PR.** Read the run summary in the PR body, open the preview (artifact `preview-<id>-DATE` from the run), and read every item.
   2. **Edit if needed** directly in GitHub: open `readers/<id>/editions/DATE.json` in the PR → pencil icon → commit to the same branch. CI re-validates.
   3. **Merge.** `deploy.yml` publishes to https://timeleaf.ee within a couple of minutes.
3. **`review: "auto"`**: the edition is committed straight to `main`, with no PR. This is only for a paper that is not public (PRINCIPLES value 10). No reader uses it yet, and `timeleaf reader check` refuses it for the paper on the public site. *The Loop* switches to it once it is behind a login. Note that `main` must then accept pushes from the workflow's token (branch protection).

To skip a week, close the PR without merging.

## Common tasks

| Task | How |
|---|---|
| Run an edition now | Actions → *Weekly edition* → *Run workflow* (optionally for one **reader**) |
| See what it would cost without spending | Same, with **dry_run** ticked |
| Make an edition on a laptop | `uv run timeleaf fetch -o candidates.json` → `uv run timeleaf edit candidates.json` (needs `ANTHROPIC_API_KEY` or `ant auth login`) → `uv run timeleaf validate readers/<id>/editions/DATE.json --candidates candidates.json` → commit on a branch, open a PR |
| Re-draft an edition | Delete the PR branch (`edition/<id>-DATE`), run the workflow again (or locally `timeleaf edit … --force`) |
| Fix a typo in a published edition | PR that edits `readers/<id>/editions/DATE.json`; merge |
| Change friends, publications, roundups or signals | Edit `readers/<id>/sources.json` in a PR |
| Add a newsletter the reader does not subscribe to | Add `{"name", "url"}` to `publications` in `sources.json`; add the name to `roundups` if it is a round-up |
| Pass on the reader's feedback | Add it at the top of `readers/<id>/notes.md`, dated, in their words. The editor reads it every week |
| Change who the reader is or what they want | Edit `readers/<id>/profile.md` |
| Change a paper's name, sections or cost cap | Edit `readers/<id>/reader.json` |
| Change the editor's instructions for everyone | Edit `src/timeleaf/edit/prompt.md` in a PR; see *Changing the prompt* |
| Hide the site from search engines | Set `"indexable": false` in `config/site.json` |
| Turn on the feedback form | Create a Formspree form, set `"feedback_form_action": "https://formspree.io/f/<id>"` in `config/site.json` |

## Readers

```bash
uv run timeleaf reader list                 # who has a paper
uv run timeleaf reader check [<id>]         # is the folder complete and valid? (CI runs this for everyone)
uv run timeleaf reader add <id> --paper-name "..." [--email ...] [--substack <handle>]
uv run timeleaf reader remove <id>          # deletes readers/<id>/
```

**Adding a reader.** The new reader fills in the questionnaire in [onboarding.md](onboarding.md); the second half of that page says how to turn the answers into a folder. **Do not commit anyone's folder but the owner's while this repository is public** (docs/proposals/DECISIONS.md, review note 6): a reader's profile, sources and paper are private to them and the owner (PRINCIPLES value 12).

**What is public.** `timeleaf build` without `--reader` renders the primary reader's paper, and only that, at the site root; that is what `deploy.yml` publishes. `timeleaf build --reader <id> -o <dir>` renders another reader's paper for a local look. It is never deployed.

**Removing a reader.**
1. `uv run timeleaf reader remove <id>`, commit, merge. The folder, with every edition, is gone from the current files.
2. The old commits still contain it. To erase it from history as well: `git filter-repo --path readers/<id> --invert-paths`, force-push, and ask GitHub Support to drop cached views of the old commits. Delete the reader's `candidates-<id>-*` and `preview-<id>-*` workflow artifacts (Actions → the run → Artifacts), or wait for them to expire (90 and 30 days). Also delete their `edition/<id>-*` branches and any `edition-failed` issue comments that name them. Edition pull requests (`refs/pull/N/head` and their descriptions) can only be removed by GitHub Support; for private papers, which publish without pull requests, there are none.
3. Once papers are behind a login: remove their address from the Cloudflare Access policy.
4. Tell them it is done.

## When something fails

**`edition-failed` issue opened.** It names the reader. Open the linked run.
- *Fetch failed / 0 requests ok*: Substack may be blocking GitHub's IP ranges. Check the canary. Run the fetch on a laptop and continue locally (table above).
- *Estimated cost is above the cap*: candidates are unusually large. Re-run with a shorter window, or locally with `--max-cost`. The cap is `max_cost_usd` in the reader's `reader.json`.
- *Editor failed validation after repair*: the log lists the rule broken (`provenance`, `friends`, `source-cap`, `sections`, `item-cap`, …). Re-run once; if it repeats, the prompt or the candidates need a look. `source-cap` repeating means the week's candidates lean on one newsletter: add publications to `sources.json`.
- *Refusal*: the model declined. Re-run; the server-side fallback should already have tried another model. If it repeats, find the candidate that triggers it.
- *`ANTHROPIC_API_KEY` missing / 401*: add or rotate the secret (below).
- *`reader check` failed* (in the first job): a reader's folder is incomplete or invalid; the log says what.

**`canary-failed` issue opened.** An endpoint changed shape or blocks us. Run `uv run timeleaf canary` locally to see which: it checks the Substack profile, posts, post-by-id and activity endpoints, one publication archive, and LessWrong. Update `src/timeleaf/fetch/substack.py` and the fixtures in `tests/fixtures/`.

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

`src/timeleaf/edit/prompt.md` is the same for every reader: the values in [PRINCIPLES.md](PRINCIPLES.md) as instructions, with slots for one reader's profile, notes and sections. Nothing about a particular reader belongs in it (a test checks). What one reader wants goes in their `profile.md` or `notes.md`.

1. Download the last three `candidates-*` artifacts from past runs.
2. On a branch, for each: `uv run timeleaf edit candidates.json --date <that date> -o /tmp/new-<date>.json`.
3. Compare with the published edition for that week: validator warnings, item mix, voice. Write down what changed in the PR.
4. Merge only if it is better on at least two of three and worse on none.

## Changing what an edition "cannot see"

The paragraph is written by code. Sources Timeleaf knows about are in the registry in `src/timeleaf/blind.py`: when one becomes readable (X, the EA Forum), change its entry there. Things only one reader would miss go in `blind_spots` in their `reader.json`. Published editions keep the paragraph they were published with.

## Changing templates or styles

Run `UPDATE_GOLDEN=1 uv run pytest` and review the diff of `tests/golden/` in the PR: it shows exactly what readers will see change.

## Changing the data model

Edit `src/timeleaf/models.py`, run `uv run timeleaf schema`, commit `docs/schemas/`. A breaking change bumps `schema_version` and needs a migration of the files in `readers/*/`.
