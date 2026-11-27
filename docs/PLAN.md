# Timeleaf — Implementation Plan

**Status:** Approved for build · **Version:** 1.0 · **Date:** 2026-11-27 · **Owner:** @r-is-coding
**Production URL:** https://timeleaf.ee · **Repo:** `r-is-coding/timeleaf`

This is the plan of record for turning the working prototype of *The Loop* (a weekly personal newspaper) into a production website at timeleaf.ee. It is written so a developer who has not seen any earlier conversation can start on Milestone 0 today.

Related documents:
- [`docs/PLAN-buzz.md`](PLAN-buzz.md) — feature plan for "The Buzz" section (Milestone 4).
- [`docs/adr/`](adr/) — Architecture Decision Records. Read them before proposing to change a decision.
- [`prototype/`](../prototype/) — the original working scripts. Frozen reference; do not develop there.

---

## 1. Product summary

**The reader** works in AI safety advocacy, has left social media, and wants to stay informed on AI safety and policy (plus rationalist / post-rationalist / contemplative writing) through people they trust rather than a feed.

**The product** is one finite edition per week, about 15–18 items, ending with *"That is all for this week."* Every item says *why it is here* and who pointed at it. A colophon states what was checked, what failed, and what the edition cannot see.

**How an edition is made** (already proven by the prototype):

```
 sources.json ──► FETCH ──► candidates.json ──► EDIT (Claude) ──► editions/DATE.json ──► BUILD ──► static HTML
                 (Substack,                      (selects, writes,                        (render)
                  LessWrong)                      explains "why")
```

### Product rules (fixed — see PLAN-buzz §1; do not reopen without the owner)

1. Weekly, finite, capped at ~15–18 items.
2. Every item has a "why it is here" line naming who pointed at it.
3. News is compressed. Essays get a pitch and a reading time, never a summary.
4. Public static website.
5. No like buttons or engagement metrics. Feedback is given in words.
6. Colophon is honest about coverage and failures.
7. Everything posted by the three named friends appears, always.

### Goals of this project

| # | Goal | Measured by |
|---|------|-------------|
| G1 | A new edition appears at timeleaf.ee every week with ≤ 10 minutes of human time | Time from PR opened to merged; editions published / weeks |
| G2 | Nothing is published that a human did not approve | Branch protection; every edition arrives as a PR |
| G3 | The model cannot invent sources | 100% of edition URLs trace back to the candidates file (automated check) |
| G4 | Cheap and boring to run | ≤ US$5 / week all-in; no servers; no database |
| G5 | Fast, accessible, private | Lighthouse ≥ 95 in all categories; WCAG 2.2 AA; zero third-party requests |

### Non-goals (v1)

- Multiple readers / accounts / personalisation for others.
- Comments, likes, or any client-side app.
- A CMS. Content is JSON in git; GitHub's web editor is the CMS.
- Reading X directly (that is Buzz Stage 1, after v1).

---

## 2. Architecture

### 2.1 Overview

```
                         GitHub (r-is-coding/timeleaf)
 ┌────────────────────────────────────────────────────────────────────────────┐
 │                                                                            │
 │  weekly-edition.yml (cron Fri 05:00 UTC, or manual)                         │
 │   1. timeleaf fetch   ──► candidates.json ──► uploaded as workflow artifact │
 │   2. timeleaf edit    ──► Claude API (structured output = Edition schema)   │
 │   3. timeleaf validate (schema + editorial rules + URL provenance)          │
 │      └─ on failure: one repair round-trip to Claude, then fail loudly       │
 │   4. timeleaf build   ──► preview artifact                                  │
 │   5. open PR "Edition N — DATE" (branch edition/DATE) with run summary      │
 │                                                                            │
 │  Reader reviews PR ─ edits JSON in GitHub UI if needed ─ merges            │
 │                                                                            │
 │  deploy.yml (push to main)                                                  │
 │   build ALL editions ─► upload-pages-artifact ─► deploy-pages               │
 └──────────────────────────────────────┬─────────────────────────────────────┘
                                        ▼
                         GitHub Pages ── https://timeleaf.ee
```

There is no runtime server, no database and no JavaScript requirement. Git is the database; the edition JSON files are the source of truth; the HTML is a disposable build product.

### 2.2 Key decisions (summary — full reasoning in ADRs)

| Decision | Choice | ADR |
|---|---|---|
| Hosting | GitHub Pages, deployed by GitHub Actions, custom domain timeleaf.ee | [0001](adr/0001-static-site-on-github-pages.md) |
| Language / site generator | Python 3.12 package with Jinja2 templates; no JS framework | [0002](adr/0002-python-jinja-static-generator.md) |
| Editor | Claude API (`claude-opus-5-5`) with structured outputs; human approves via PR | [0003](adr/0003-llm-editor-with-human-approval.md) |
| Content contract | Versioned JSON schemas (Pydantic) for sources, candidates and editions | [0004](adr/0004-json-schemas-as-contract.md) |

### 2.3 Repository layout (target)

```
timeleaf/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # lint, type-check, test, build on every PR
│   │   ├── weekly-edition.yml   # cron: fetch → edit → validate → PR
│   │   ├── deploy.yml           # push to main → build → GitHub Pages
│   │   └── canary.yml           # daily: are the source endpoints still alive?
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   └── pull_request_template.md
├── config/
│   └── sources.json             # friends, seeds, roundups, signal handles
├── content/
│   └── editions/YYYY-MM-DD.json # one file per published edition (source of truth)
├── src/timeleaf/
│   ├── cli.py                   # `timeleaf fetch|edit|validate|build|serve`
│   ├── models.py                # Pydantic: Sources, Candidates, Edition
│   ├── fetch/
│   │   ├── http.py              # httpx client, retries, timeouts, health ledger
│   │   ├── substack.py
│   │   └── lesswrong.py
│   ├── edit/
│   │   ├── prompt.md            # editor system prompt (versioned, reviewed like code)
│   │   └── editor.py            # Claude API call, repair loop, cost accounting
│   ├── validate.py              # editorial + provenance rules
│   └── build/
│       ├── render.py
│       ├── templates/           # base, edition, archive, about, 404, feed.xml
│       └── static/              # style.css, self-hosted fonts, favicon
├── tests/
│   ├── fixtures/                # recorded API responses (trimmed), sample candidates
│   ├── unit/
│   └── golden/                  # snapshot of rendered edition 1
├── docs/                        # this plan, ADRs, runbook, PLAN-buzz
├── prototype/                   # frozen original scripts (reference only)
├── pyproject.toml  uv.lock  .pre-commit-config.yaml  .gitignore  README.md
```

`_site/` (build output) and `candidates*.json` are git-ignored. Candidates contain long excerpts of other people's posts, including paywalled ones; they are kept as 90-day workflow artifacts, never committed to a public repo.

### 2.4 Components

#### Fetch (`timeleaf fetch --days 7 -o candidates.json`)
Port of `prototype/fetch.py`, split by source, same behaviour. Endpoints are listed in PLAN-buzz Appendix A.

- `httpx` with explicit timeouts (connect 10 s, read 30 s), 3 retries with exponential backoff + jitter, and a polite rate limit (≤ 2 req/s per host).
- Identify honestly: `User-Agent: timeleaf/<version> (+https://timeleaf.ee/about)`. If Substack rejects that, fall back to a browser UA and record the fact in the run summary.
- Every request goes through one client that records successes and failures into a `health` ledger. The colophon is generated from this ledger, **not** written by the model.
- Output is validated against the `Candidates` model before it is written.
- Deterministic ordering (sort by date then URL) so diffs between runs are meaningful.
- Fallback per publication: if the Substack API fails, try the public RSS feed (`<pub>/feed`).

#### Edit (`timeleaf edit candidates.json -o content/editions/DATE.json`)
Replaces the manual "Claude reads candidates" step.

- Model `claude-opus-5-5`, `output_config.effort: "high"`, streaming with `max_tokens: 64000`.
- **Structured outputs**: `output_config.format` is the JSON schema of `Edition` (generated from the Pydantic model), so the response always parses.
- Refusal handling: beta `server-side-fallback-2026-07-01` with `fallbacks: "default"`; always check `stop_reason` before using output.
- System prompt = `edit/prompt.md` (the product rules, section definitions, voice, and examples from edition 1). Stable, so it is cache-marked; the repair round-trip reuses the cache.
- The model writes: selection, sections, kickers, titles, bodies, `why` lines, lede. The code writes: `number`, `date`, `range`, colophon facts.
- **Repair loop**: if `validate` fails, send the list of violations back once. If it still fails, the workflow fails and opens an issue; nothing is half-published.
- Log `usage` and cost; abort before the call if the estimated input (`count_tokens`) would exceed the per-run cap (default US$3).
- Candidate content is **untrusted input** (prompt injection is possible inside any blog post). Mitigations: the model has no tools, output is schema-constrained, every URL must exist in candidates, and a human approves the PR.

Estimated cost: ~60–120k input tokens + ~10–20k output (incl. thinking) ≈ **US$0.50–1.00 per edition**.

#### Validate (`timeleaf validate content/editions/DATE.json --candidates candidates.json`)
Pure functions, fully unit-tested. Runs in the weekly workflow and in CI on every PR that touches `content/`.

| Rule | Severity |
|---|---|
| Parses against `Edition` schema | error |
| Total items between 12 and 18 | error |
| Every item has a non-empty `why` | error |
| Every item URL and every `more[].url` appears in candidates (provenance) | error (in weekly run; skipped in CI when candidates absent) |
| Every friend's `new_posts` URL appears in the edition | error |
| Only `http(s)` URLs | error |
| Essay items (`kind: essay`) have `mins` | error |
| No duplicate URLs across items | error |
| Body length ≤ 900 chars; essay body ≤ 400 chars | warning |
| Buzz items have `seen` and ≥ 2 `more` links (from M4) | error |

#### Build (`timeleaf build -o _site`)
Renders **all** editions from `content/editions/` every time (deterministic, idempotent, < 1 s).

Pages and files:
- `/` — latest edition.
- `/editions/YYYY-MM-DD/` — permanent page per edition (directory + `index.html` for clean URLs).
- `/archive/` — list of all editions with their ledes.
- `/about/` — what this is, how it is made (including that an AI drafts it and a person approves it), how to give feedback, contact.
- `/feed.xml` — Atom feed, one entry per edition (lets the reader use any feed reader or email-from-RSS service).
- `/404.html`, `/sitemap.xml`, `/robots.txt`, favicon.

Template requirements:
- Jinja2 with **autoescape on**. The model's text is never rendered as raw HTML.
- Port `prototype/style.css` unchanged at first (it already has light/dark tokens and a mobile layout); then fix the items in §2.5.
- Semantic HTML: one `h1` per page, `<main>`, `<article>` per item, skip link, `lang="en"`.
- `<meta>` description, canonical URL, Open Graph tags per edition.
- Content Security Policy via `<meta http-equiv>` (GitHub Pages cannot set headers): `default-src 'self'; img-src 'self' data:; style-src 'self'; base-uri 'none'; form-action 'self' https://formspree.io`.
- Zero JavaScript in v1.

#### Deploy
`deploy.yml` on push to `main`: `uv sync` → `timeleaf build` → `actions/upload-pages-artifact` → `actions/deploy-pages`. Custom domain is configured in repo **Settings → Pages** (with Actions-based deploys the `CNAME` file is not used). "Enforce HTTPS" on.

### 2.5 Changes from the prototype that are required, not optional

| Prototype | Problem | Fix |
|---|---|---|
| Google Fonts `<link>` | Sends every visitor's IP to Google — a known GDPR problem for an EU site | Self-host the three fonts as WOFF2 subsets in `static/fonts/` |
| `<meta name="claude:viewport-fit-sides">`, tags outside `<head>` | Artefact-preview leftovers, invalid HTML | Proper document in `base.html.j2` |
| `index.html` and edition page are identical copies | Duplicate content, no canonical | Index renders latest edition with `rel=canonical` to its permalink |
| Colophon prose written by the model | Model could misreport what was checked | Generate from `health` ledger; model only writes the "blind" paragraph |
| `fetch.py` reads `__file__.rsplit("/")` | Breaks on Windows | `pathlib` + config path argument |
| No tests, no schema | Silent breakage | §2.4 Validate, §5 Testing |

---

## 3. Data model

Defined in `src/timeleaf/models.py` (Pydantic v2). JSON Schemas are generated from the models and committed to `docs/schemas/` so they are reviewable. Every file has `schema_version`; bump it on breaking change and write a migration in `timeleaf migrate`.

```python
class Link(BaseModel):
    label: str
    url: HttpUrl

class Item(BaseModel):
    kind: Literal["news", "essay", "friend", "edge", "buzz"]
    kicker: str                  # e.g. "US politics"
    title: str
    url: HttpUrl
    source: str                  # author / publication
    mins: int | None = None      # reading time; required for essays
    body: str
    why: str                     # "Why it is here"
    more: list[Link] = []
    seen: str | None = None      # Buzz only: "direct" | "via <source>"

class Section(BaseModel):
    id: str                      # slug: front-page, policy-desk, movement, worth-your-time, friends, edges, buzz
    title: str
    note: str
    items: list[Item]

class Colophon(BaseModel):
    checked: str                 # generated from health ledger
    blind: str                   # what this edition cannot see
    requests_ok: int
    requests_failed: list[str]
    model: str | None = None
    cost_usd: float | None = None

class Edition(BaseModel):
    schema_version: Literal[1] = 1
    number: int
    date: date                   # publication date (Friday)
    range: str                   # "20–27 November 2026"
    lede: str
    sections: list[Section]
    colophon: Colophon
```

Migration of edition 1: add `schema_version`, section `id`s, item `kind`s and the numeric colophon fields. Do this by script in M1; keep the visible text identical.

---

## 4. Infrastructure and operations

### 4.1 Domain: timeleaf.ee

1. Confirm the registrar (an EIS-accredited `.ee` registrar) and who holds the login. Turn on registrar 2FA and DNSSEC.
2. **Verify the domain for GitHub Pages first** (GitHub → Settings → Pages → Verified domains). This adds a TXT record `_github-pages-challenge-r-is-coding.timeleaf.ee` and prevents domain takeover.
3. DNS records:

   | Name | Type | Value |
   |---|---|---|
   | `@` | A | 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153 |
   | `@` | AAAA | 2606:50c0:8000::153, 2606:50c0:8001::153, 2606:50c0:8002::153, 2606:50c0:8003::153 |
   | `www` | CNAME | `r-is-coding.github.io.` |
   | `@` | CAA | `0 issue "letsencrypt.org"` |

4. Set custom domain `timeleaf.ee` in Pages settings; wait for the certificate; enable **Enforce HTTPS**. `www` redirects to the apex automatically.
5. Email is out of scope; add SPF `v=spf1 -all` and a null MX so the domain cannot be spoofed.

### 4.2 GitHub repository settings

- **Visibility:** created **private**. GitHub Pages from a private repo needs GitHub Pro (or an org on Team). Either upgrade, or make the repo public before M0 ends — see open question Q2. If public: nothing secret may be in the repo (there isn't), and candidate files stay out of git (§2.3).
- Branch protection on `main`: PR required, CI must pass, linear history, no force-push. The owner can merge their own edition PRs.
- `CODEOWNERS`: `* @r-is-coding`.
- Actions: workflow default permissions read-only; each job requests only what it needs (`contents: write`, `pull-requests: write`, `pages: write`, `id-token: write`). Third-party actions pinned to a commit SHA. Dependabot for `pip`/`uv` and `github-actions`, weekly.
- Secrets (Settings → Secrets → Actions, environment `edition`): `ANTHROPIC_API_KEY`. Later (Buzz Stage 1): `X_API_TOKEN`. Never in code, never echoed in logs.
- **PR-creation token:** PRs opened with the default `GITHUB_TOKEN` do not trigger other workflows, so CI would not run on edition PRs. Use a small GitHub App (preferred) or a fine-grained PAT stored as `EDITION_BOT_TOKEN`, scoped to this repo with contents + pull-requests write.
- Scheduled workflows in public repos are disabled after 60 days without repository activity. Weekly edition merges keep it alive; the runbook says how to re-enable.

### 4.3 Workflows

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | PR, push to main | `ruff check`, `ruff format --check`, `mypy --strict`, `pytest`, `timeleaf validate` on changed editions, `timeleaf build`, HTML validation (`html5validator`), link check on built site (internal links only) |
| `weekly-edition.yml` | `cron: "0 5 * * 5"` (Fri 07:00 Tallinn) + `workflow_dispatch` with inputs `days`, `dry_run` | fetch → edit → validate → build preview → open PR with summary; on failure open/update an issue labelled `edition-failed` |
| `deploy.yml` | push to `main` touching `content/`, `src/`, `config/` | build → deploy to Pages; `concurrency: pages` |
| `canary.yml` | daily | hits each source endpoint once, asserts response shape; opens an issue on 2 consecutive failures |

The edition PR description contains: item count per section, the lede, validation warnings, request health, model, tokens and cost, and a link to the preview artifact. The reader can edit the JSON directly in the GitHub web editor before merging.

### 4.4 Observability

- Each workflow writes a Markdown **job summary** (counts, failures, cost).
- Failures become GitHub issues (deduplicated by label) → the owner gets GitHub's email notification. No other monitoring stack.
- Uptime: GitHub Pages is the SLA; optionally add a free external uptime check on `https://timeleaf.ee/feed.xml`.

### 4.5 Cost

| Item | Monthly |
|---|---|
| GitHub Pages + Actions (well within free minutes) | $0 (or $4 GitHub Pro if repo stays private) |
| Claude API, 4–5 editions incl. repairs and manual reruns | ~$3–6 |
| Domain timeleaf.ee | ~$1–2 (annual fee / 12) |
| **Total** | **< $12** |

Hard limits: per-run cap in code (US$3) and a monthly spend limit set on the Anthropic workspace.

---

## 5. Engineering standards

- **Python 3.12**, dependencies managed with **uv** (`pyproject.toml` + `uv.lock`). Runtime deps kept small: `httpx`, `pydantic`, `jinja2`, `anthropic`, `typer`.
- **Lint/format:** ruff (rules `E,F,I,B,UP,S,SIM,RUF`). **Types:** mypy `--strict` on `src/`.
- **pre-commit** runs ruff, mypy, end-of-file/trailing-whitespace, `check-json`, and `gitleaks`.
- **Tests (pytest):**
  - Unit tests for every parser using recorded, trimmed fixtures in `tests/fixtures/` — no network in unit tests.
  - Validator tests: one passing and one failing case per rule.
  - **Golden test:** edition 1 renders to a committed snapshot; intentional template changes update the snapshot in the same PR.
  - Editor: test the request builder and repair loop with a fake client. Prompt changes are evaluated by re-running the editor on the last 3 stored candidate artifacts and comparing validator results and a human read (documented in `docs/runbook.md`).
  - Coverage target 85% for `fetch/`, `validate.py`, `build/`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `content:` for editions). Small PRs, one concern each.
- **Docs:** any change to a decision in §2.2 needs a new ADR. `README.md` covers local setup in ≤ 5 commands.
- **Local dev loop:**
  ```bash
  uv sync
  uv run timeleaf build && uv run timeleaf serve      # http://localhost:8000
  uv run timeleaf fetch --days 7 -o candidates.json   # needs network
  uv run timeleaf edit candidates.json --dry-run      # prints cost estimate, no API call
  ```

### Quality bars for the site

- Lighthouse ≥ 95 for Performance, Accessibility, Best Practices, SEO (mobile).
- WCAG 2.2 AA: contrast checked for both themes, visible focus, skip link, no information by colour alone.
- Page weight ≤ 150 KB including fonts; zero third-party requests; no cookies, so no cookie banner.
- Valid HTML (no errors from the Nu validator).

---

## 6. Security, privacy and content policy

- **People named on the site.** Three friends appear by first name and handle in every edition. **Get their explicit OK before go-live** (Q4). Offer to show a handle only.
- **Copyright.** Link to originals, keep quotes short, never republish full text; candidate bodies stay out of git.
- **Prompt injection.** Treated as a given (§2.4 Edit). Defences are structural: no tools, schema-constrained output, URL provenance check, human approval.
- **XSS.** Autoescaped templates, `http(s)`-only URLs, CSP meta tag.
- **Secrets.** Only in GitHub Actions secrets; `gitleaks` in pre-commit and CI.
- **Supply chain.** Lockfile, Dependabot, SHA-pinned actions, least-privilege tokens.
- **Search engines.** Default is *indexable*; if the owner prefers the site to be public but quiet, set `noindex` site-wide and `Disallow: /` (Q3).
- **Transparency.** The About page and the colophon say that an AI drafts the edition and a person approves it.

---

## 7. Delivery plan

Estimates are for one developer. Each milestone ends in something deployed.

### M0 — Foundations (1–2 days)
- [ ] Decide Q1–Q3 (naming, repo visibility, indexing).
- [ ] `pyproject.toml`, uv, ruff, mypy, pytest, pre-commit, `.gitignore`, `README.md`.
- [ ] `ci.yml` and `deploy.yml`; branch protection; CODEOWNERS; Dependabot.
- [ ] Domain verified, DNS set, HTTPS enforced. A placeholder page is live at https://timeleaf.ee.

**Done when:** a PR runs CI green and merging it deploys to timeleaf.ee over HTTPS.

### M1 — Port the prototype (3–4 days)
- [ ] `models.py` + generated JSON schemas; migrate edition 1 to schema v1.
- [ ] `fetch/` package ported from `prototype/fetch.py` with fixtures and tests; health ledger.
- [ ] `build/` with Jinja templates; style ported; fonts self-hosted; §2.5 fixes.
- [ ] `validate.py` with all v1 rules and tests.
- [ ] Golden test for edition 1.

**Done when:** `timeleaf fetch` produces candidates equivalent to the prototype's, edition 1 is live at `/editions/2026-11-27/`, and it looks the same as the prototype in both colour schemes.

### M2 — Site completeness (2–3 days)
- [ ] Archive, About, 404, Atom feed, sitemap, robots, favicon, Open Graph.
- [ ] CSP; HTML validation and internal link check in CI.
- [ ] Lighthouse and accessibility pass; fix findings.
- [ ] Feedback in words: a short form on About (Formspree, already used on rcrd.nl) or a `mailto:` (Q8).

**Done when:** quality bars in §5 are met and checked in CI where automatable.

### M3 — Automated weekly edition (3–5 days)
- [ ] `edit/prompt.md` written from the product rules and edition 1 as the worked example.
- [ ] `edit/editor.py`: structured outputs, streaming, refusal fallback, repair loop, cost cap, usage logging.
- [ ] `weekly-edition.yml` with bot token, PR body summary, failure issues.
- [ ] `canary.yml`.
- [ ] `docs/runbook.md`: rerun, edit, skip a week, rotate key, re-enable cron, publish manually from a laptop if Actions is blocked.
- [ ] One **shadow week**: the workflow runs and opens a PR; the owner compares it to a hand-made edition before trusting it.

**Done when:** two consecutive Friday PRs are opened unattended, pass validation, and are merged with ≤ 10 minutes of editing each.

### M4 — The Buzz, Stage 0 (2–3 days)
Implement exactly [PLAN-buzz.md](PLAN-buzz.md) §4 Stage 0 and §5: extract tweet links, handles and section headings from roundup bodies; `buzz.secondhand` in candidates; `buzz` section with `seen: via …`; build `circle_ai.json` from 8–10 weeks of roundups.

**Done when:** PLAN-buzz §7 Stage 0 criteria are met, and the edition stays within the item cap.

### M5 — Hardening (2 days)
- [ ] RSS fallbacks per publication; retry/backoff tuning from real canary data.
- [ ] Coverage targets met; mypy strict clean.
- [ ] Prompt evaluation procedure exercised once.
- [ ] Review this plan; record any changed decisions as ADRs.

**Total: ~13–19 developer-days (≈ 3–4 weeks calendar).**

### Later (not scheduled)
- Buzz Stage 1–2 (needs answers to PLAN-buzz §8).
- More sources outside Substack/LessWrong: Transformer, AI Safety Newsletter, EA Forum (RSS/GraphQL).
- Email delivery of each edition (RSS-to-email service, or Buttondown API).
- "Revise" command: comment `/revise drop item 4, add X` on the edition PR to trigger a second editor pass.

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Substack's undocumented API changes or blocks GitHub runner IPs | Medium | High | Daily canary; RSS fallback; documented laptop run (`timeleaf fetch` locally, push candidates as PR) |
| Model invents or misattributes a source | Low | High | URL provenance check; human approval; colophon from code |
| Model misses a friend's post | Low | Medium | Hard validator rule |
| Prompt injection inside a fetched post | Low | Medium | No tools, schema output, URL allowlist, human review |
| Cron disabled after 60 days without activity | Medium | Low | Weekly merges; runbook step to re-enable; failure issue |
| Cost creep | Low | Low | Per-run cap; workspace monthly limit |
| Friends object to being named publicly | Unknown | Medium | Ask before go-live (Q4) |
| Single maintainer | High | Medium | Runbook; everything in git; no hidden state |

---

## 9. Open questions for the owner

Blocking items are marked ⛔ with the milestone they block.

| # | Question | Default if no answer |
|---|---|---|
| Q1 | Naming: is **Timeleaf** the site and **The Loop** the weekly paper inside it? | Yes: masthead says "The Loop", site title "The Loop · Timeleaf" |
| Q2 ⛔ M0 | Repo public (free Pages) or private with GitHub Pro ($4/mo)? | Make public before deploy; candidates never committed |
| Q3 ⛔ M0 | Should search engines index the site? | Indexable |
| Q4 ⛔ go-live | Have Gamithra, Llela and Sese agreed to appear by name? | Do not go live with names until they have |
| Q5 ⛔ M0 | Which registrar holds timeleaf.ee, and who can edit DNS? | — |
| Q6 | Weekly Claude API budget? | Cap US$3/run, US$20/month |
| Q7 | Publication day/time? | Friday 07:00 Tallinn |
| Q8 | Feedback channel: form (Formspree), email, or GitHub issue? | Formspree form on /about |

---

## 10. Glossary

- **Edition** — one week's newspaper; one JSON file in `content/editions/`.
- **Candidates** — everything fetched for one week, before selection.
- **Seed** — a publication the reader subscribes to; its posts and links are candidates.
- **Roundup** — a seed that summarises others (e.g. Zvi's *Don't Worry About the Vase*); its links count as votes.
- **Signal** — a trusted person whose likes and restacks surface items.
- **Co-cited** — a URL linked by two or more independent sources in the window.
- **Colophon** — the closing note on what was checked and what was not.
