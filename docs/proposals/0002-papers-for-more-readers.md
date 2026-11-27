# Proposal 0002 — A paper for every reader (starting with one friend)

**Status:** Accepted with changes, see [DECISIONS.md](DECISIONS.md) · **Date:** 2026-11-27 · **Author:** Claude (Opus 5.5) · **Reviewer:** Claude Fable, then the owner
**Builds on:** [0001](0001-feedback-round-1.md) (P1 decided as option B: private papers; Cloudflare approved)

## The request

> We want to extend it so that others could use it. First, just my friend. Let's already implement something so my friend could put in their own interests and create their own weekly Timeleaf (newspaper).

## Goal

A friend gets **their own** weekly paper: built from their interests and the people they trust, with the same values ([PRINCIPLES.md](../PRINCIPLES.md)), private to them, and readable entirely inside Timeleaf.

**Naming.** *Timeleaf* is the service. Each reader's paper has its own name; *The Loop* is the owner's. This also settles open question Q1 in PLAN.md.

## What is reader-specific today (and has to move)

| Today | Where it lives | Moves to |
|---|---|---|
| Who the reader is ("works at PauseAI…") and their interests | Hard-coded in `src/timeleaf/edit/prompt.md` | `readers/<id>/profile.md`, in the reader's own words |
| Substack handle, friends, signals, roundups | `config/sources.json` | `readers/<id>/sources.json` |
| Sections and their notes ("Five things you would be asked about at work") | Hard-coded in the prompt | `readers/<id>/reader.json` |
| Paper name ("The Loop"), masthead | `config/site.json` | `readers/<id>/reader.json` |
| Editions | `content/editions/` | `readers/<id>/editions/` |
| Feedback ("less Zvi", "don't show silent friends") | Only in chat | `readers/<id>/notes.md`, sent to the editor every week |

## Design

### Data layout

```
readers/
  richard/
    reader.json     # id, paper name, email, time zone, publish day, sections, review mode, cost cap
    profile.md      # who I am, what I want to understand, what to skip, reading time: in my own words
    sources.json    # Substack handle (optional), friends, trusted people, publications, roundups, LessWrong on/off
    notes.md        # the reader's feedback over time, newest first; the editor reads it every week
    editions/2026-11-27.json
  <friend>/
    ...
config/
  shelf.json        # shared pool of vetted publications, tagged by topic (for readers with few sources)
```

The prompt becomes **generic editor instructions** (the values) plus three per-reader inserts: `profile.md`, `notes.md`, and the section table from `reader.json`.

### Onboarding (v1: owner-assisted)

1. The friend answers a short questionnaire (`docs/onboarding.md`, also sendable as a message):
   - a name for their paper;
   - the email they will log in with;
   - Substack handle and X handle, both optional;
   - **in a few paragraphs:** what they do, what they want to understand better, what they never want to see, and how long they want to spend reading each week;
   - **at least three** people or publications whose judgement they trust (value 2 needs this);
   - friends whose every post must appear.
2. The owner runs `timeleaf reader add <id>`, which creates the folder from the answers and validates it.
3. **Calibration week:** a first edition is generated. The friend replies with feedback in words, which goes into `notes.md`, and the second edition uses it.

If the friend has few sources of their own, the editor also draws from `config/shelf.json` (a curated, topic-tagged list, starting with the owner's sources), chosen by their profile. Items from the shelf say so in the "why" line ("from the shared shelf: AI policy").

*v2 (later):* self-service sign-up and profile editing on the site, and a feedback box under each edition that writes to `notes.md`. This needs a small backend (Cloudflare Worker + D1).

### Privacy and hosting (P1 option B, for several readers)

- **The repo goes private again.** Reader profiles, emails, interests and full texts are personal data and must not sit in a public repo. Cloudflare Pages deploys from private repos for free. GitHub Pages is retired. New **ADR 0005** supersedes ADR 0001.
- **Cloudflare Pages** hosts `timeleaf.ee`:
  - `/` is public: a short landing page saying what Timeleaf is (no editions);
  - `/<id>/` holds each reader's paper, protected by a **Cloudflare Access** policy that admits only that reader's email (one-time code by email, roughly 30-day session).
- **The owner does not read friends' papers by default.** Access policies are per reader. The owner can still see the repo, and the privacy note says so plainly.
- **Privacy note** on the landing page: what is stored (profile, email, editions), who processes it (GitHub, Cloudflare, Anthropic for drafting), and how to be removed (`timeleaf reader remove <id>` deletes the folder and the Access policy).
- **DNS:** a Cloudflare Pages site on the bare domain `timeleaf.ee` needs the domain's DNS hosted at Cloudflare. That means moving the nameservers from Elkdata to Cloudflare (free) and copying the email records (MX, SPF, DKIM, DMARC, autodiscover) across so Elkdata email keeps working. *Alternative without moving DNS:* serve the site at `www.timeleaf.ee` (a CNAME to Cloudflare) and redirect the bare domain with Elkdata's "Domeeni suunamine" feature, if it supports HTTPS. This needs checking.

### Approval (changes value 10)

Today the owner approves each edition through a GitHub pull request. That doesn't work for a friend: they aren't on GitHub, and the owner shouldn't read their paper first.

**Proposal:** value 10 becomes *"Nothing goes public without a person approving it. A private paper goes straight to its one reader, after the automatic checks; the reader's feedback is the correction loop."* Each `reader.json` sets `review: "pr"` or `"auto"`. The friend uses `auto`; the owner chooses for *The Loop* (Q8).

### Weekly pipeline

```
fetch ONCE (union of all readers' sources; each URL fetched once)
  └─ for each reader (matrix, in parallel):
       edit (their profile + notes + sections) → validate (their friends, their caps) → write edition
build all papers → deploy to Cloudflare Pages (wrangler)
(optional) one email per reader: "Your paper is ready"
```

- Each reader has their own cost cap (default $2 per edition), plus a monthly limit on the Anthropic workspace.
- A failure for one reader doesn't block the others. Failures go to the owner as GitHub issues and are never emailed to the friend.
- **Optional notification (Q7):** one calm email per week, *"No. 3 of <paper> is ready"*, linking to the paper. It would be sent through a transactional email service such as Resend (free tier), from `paper@timeleaf.ee`.

### Code changes (for the implementer)

- `models.py`: new `Reader` model (id, paper_name, email, timezone, publish_day, sections, review, max_cost_usd); `Sources` gains `publications` (from 0001 P4); `Edition` gains `reader_id`.
- `edit/prompt.md`: split into generic instructions plus per-reader inserts; sections are rendered from `reader.json`.
- `validate.py`: sections and friends checked per reader.
- `build/`: per-reader subsites under `/<id>/`, a landing page, the paper name in each masthead, and the P1 reading room per reader.
- `cli.py`: `--reader <id>` on fetch/edit/validate/build; `reader add | list | remove`.
- Workflows: per-reader matrix, `wrangler pages deploy`, secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`; `deploy.yml` replaced.
- Migration: `config/sources.json` and `content/editions/` → `readers/richard/`; the reader-specific text in `prompt.md` → `readers/richard/profile.md`.
- Tests: two fixture readers. One reader's data must never appear in another's build, so add a test that greps each build for the other reader's id, sources and titles.

## Phases

| Phase | What | Effort | Visible result |
|---|---|---|---|
| 0 | Proposal 0001 parts P3, P5, P2 + P4 | ~2 days | Better *Loop*, more sources |
| 1 | Multi-reader refactor, with the owner as the only reader | 1.5 days | No visible change; everything reader-specific is in `readers/richard/` |
| 2 | Hosting move: private repo, Cloudflare Pages + Access, landing page, DNS | 1–2 days, plus the owner's DNS steps | *The Loop* behind a login at timeleaf.ee/richard/ |
| 3 | Onboard the friend: questionnaire, `reader add`, calibration week | 0.5 day, plus the friend's time | The friend's first paper |
| 4 | Reading room (0001 P1 design) for all readers | 2–3 days | Full texts and pictures inside Timeleaf |

Phases 1–3 deliver "my friend has their own paper" in about 3–4 days of work after phase 0. Phase 4 could also come before phase 3 if the friend should get full texts from their first edition.

## Changes to PRINCIPLES.md (included in this PR's draft)

- **Intent:** from "one reader" to "each reader, one private paper".
- **Value 10:** as above.
- **Value 12 (new): Private by default.** A reader's interests, sources and paper are theirs. No one else sees them, the owner included, unless the reader shares.
- **New user stories:** a friend sets up a paper in under 15 minutes of their time; a reader changes what they get by writing feedback in words.

## Acceptance

- The friend receives a weekly paper at `timeleaf.ee/<id>/` that only their email can open.
- Their paper reflects their profile: on the calibration read-through, they recognise it as theirs.
- The owner's paper is unchanged in quality and content, apart from 0001's changes.
- The isolation test passes: no reader's data appears in another reader's build.
- The total weekly cost for two readers is ≤ $4.

## Questions for the owner

- **Q4.** About the friend: do they use Substack, X, LessWrong? What do they care about? (Or send them the questionnaire once it exists.)
- **Q5.** Who pays for the friend's API use (about $0.50–1 per week), and what cap?
- **Q6.** Should you be able to read your friend's paper? Proposed default: no.
- **Q7.** A weekly "your paper is ready" email: yes or no?
- **Q8.** *The Loop*: keep approving it via pull request, or let it publish automatically like your friend's?
- **Q9.** Move timeleaf.ee's DNS to Cloudflare (your Elkdata email keeps working; records are copied), or try the `www` plus redirect alternative first?
