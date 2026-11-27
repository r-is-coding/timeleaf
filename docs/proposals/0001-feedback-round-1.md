# Proposal 0001 — Reader feedback, round 1

**Status:** Proposed, for review · **Date:** 2026-11-27 · **Author:** Claude (Opus 5.5) · **Reviewer:** Claude Fable, then the reader
**Process:** reviewer comments or edits this file → reader decides the open questions → implementation on a branch, PR per proposal part.

## Decisions (reader, 2026-11-27)

- **Q1:** No one else reads *The Loop* for now, but Timeleaf should grow so others get **their own** papers, starting with one friend. → **P1 option B (private)**, extended to several readers in [proposal 0002](0002-papers-for-more-readers.md).
- **Q2:** Cloudflare is fine.
- **Q3:** Yes. Transformer and AISN are roundups; their links count as votes.

## The feedback

> 1. Could all the text and info and pictures be *inside* the app? I don't want to go to other apps with other vibes.
> 2. I feel like you're over-indexing on Zvi. I don't know him and haven't deliberately read his posts. I understand he puts together a summary of AI safety news, so I guess that's good, but otherwise I don't care that much.
> 3. "Gamithra, Llela and Sese did not publish this week": please don't show this. Not important.
> 4. Should we include Transformer, AI Safety Newsletter, EA Forum, or X as well?
> 5. Do we have a list of original intents, user stories or values to refer to?

| Part | Serves (see [PRINCIPLES.md](../PRINCIPLES.md)) | Size | Needs a decision |
|---|---|---|---|
| P1 Reading room | values 6, 11 · US-2 | L (3–4 days) | **Yes: Q1, Q2** |
| P2 Less Zvi, more breadth | values 3, 4 · US-4, US-5 | M (1 day) | No |
| P3 Silence is not news | value 7 · US-3 | S (1 hour) | No |
| P4 More sources, honest blind spots | values 3, 8 · US-5, US-7 | M (1 day) | Q3 (minor) |
| P5 Principles page | all | S (draft included) | Approve the draft |

Suggested order: P3 → P5 → P2 + P4 together (they interact) → P1.

---

## P1 — Read everything inside The Loop

### Problem
Every item links out to Substack or LessWrong, each with its own look, prompts, popups and feeds. The reader wants to read the whole piece, with pictures, in The Loop's own calm typography.

### Constraint
timeleaf.ee is **public**. Republishing full articles and their images on a public site copies other people's work without permission (value 11, US-10), and for paywalled posts it would also break Substack's terms. Personal, private copies are a different matter; read-later apps such as Pocket or Readwise work on that basis. The fetcher never logs in, so paywalled posts only ever have their free part.

So "inside the app" means **a private copy for the reader**, not a public one.

### Options

| | A. Private reading room next to the public paper | B. Make the whole paper private | C. Stay public; richer summaries only |
|---|---|---|---|
| What the reader sees | `read.timeleaf.ee`, behind a login: the same edition, but every title opens the full text inside The Loop | `timeleaf.ee` itself behind a login, with full text | Longer in-app summaries and key quotes; full text still opens outside |
| Public paper | Unchanged at timeleaf.ee (titles, summaries, outbound links) | None | Unchanged |
| Meets "one place, one vibe" | Yes | Yes | Partly |
| Hosting | GitHub Pages (public) **plus** Cloudflare Pages + Cloudflare Access (private) | Cloudflare Pages + Access only; GitHub Pages retired | No change |
| Where full texts live | Private store (a private repo `timeleaf-library`, or Cloudflare R2), never in the public repo | Same, or the repo goes private again | Nowhere |
| Friends' consent (open question Q4 in the plan) | Still needed for the public paper | No longer needed | Still needed |
| Reopens a past decision | No | Yes: "public static website" (PLAN-buzz §1) and ADR 0001 | No |
| Effort | 3–4 days | 2–3 days | 0.5 day |
| Running cost | $0 (Cloudflare free tier covers up to 50 users) | $0 | $0 |

**Decided: B**, with one private paper per reader (see proposal 0002). The text below is kept for the record.

**Recommendation (before the decision):** if anyone besides the reader is meant to read The Loop, go with **A**. If not, **B** is simpler and also removes the consent and copyright questions. **C** does not meet the request; list it only as a fallback.

### Design (applies to A and B)

- **Capture.** At edition time, for each selected item, fetch the full body:
  - Substack: `posts/by-id/<id>` → `body_html`, `cover_image`.
  - LessWrong: GraphQL `contents { html }`.
  - Other sites: a readability extraction (e.g. `trafilatura`), only for links already in the candidates.
  - Save as `library/<edition-date>/<slug>.json`: title, author, date, original URL, licence note, sanitised HTML, image list.
- **Sanitise.** This is third-party HTML, so it is untrusted. Use an allow-list sanitiser (`nh3`): paragraphs, headings, lists, blockquote, figure/figcaption, img, a, em/strong, code/pre, footnotes. No scripts, iframes, inline styles or event handlers. Embedded tweets and videos become a link card.
- **Images.** Download them at build time and serve them from the private site, resized to ≤1200 px WebP. The browser then makes no requests to other servers.
- **Reader page** `/read/<date>/<slug>/`: The Loop's own fonts and colours; reading time; a short "why it is here" at the top; "Original on <site>" in small type at the end; previous/next item; back to the edition. Paywalled posts show the free part, then "The rest is for paying subscribers of <publication>", with the link.
- **Edition page:** titles open the reader page; the original is a secondary link.
- **Login:** Cloudflare Access, emailing a one-time code to the reader's address, with a session of about 30 days. No passwords to manage.
- **Pipeline:** `weekly-edition.yml` also runs `timeleaf capture` after the edition is approved (on merge), writes to the private store, then builds and deploys the private site with `wrangler pages deploy` (new secret `CLOUDFLARE_API_TOKEN`).
- **Validator:** every item in a private build must have a captured body, or be marked `capture: failed` with a reason that appears in the colophon.

### Acceptance
- On a phone, the reader can read a whole edition, including every full piece, without leaving The Loop's domain.
- The public paper (A) contains no full texts and no third-party images.
- Zero third-party requests from reader pages (checked by the existing test, extended to `/read/`).

### Questions for the reader
- **Q1.** Is anyone besides you meant to read The Loop? (Decides A or B.)
- **Q2.** Is Cloudflare acceptable as the host of the private part? Alternatives exist, such as Netlify with password protection, but Access is the simplest free option with a real login.

---

## P2 — Less Zvi, more breadth

### Evidence (edition 1)
- 5 of 18 items link to Zvi Mowshowitz's posts; 7 of 18 "why it is here" lines name him.
- The reader doesn't know him, so "Zvi wrote a full post" is not a reason they recognise (value 4).

### Causes
1. **Roundups get more room.** Their excerpts are 12,000 characters against 3,500 for other posts, and Zvi writes the only large roundup in the reader's subscriptions.
2. **The editor credits the roundup, not the story.** It links Zvi's post instead of the primary source he links to. It can't easily do otherwise: the excerpt is plain text, so it can't tell which link belongs to which story.
3. **Nothing limits how many items come from one source.**
4. **The prompt's own examples** ("Zvi wrote a full post") teach it to cite him.

### Changes
1. **Roundups are an index, not a destination** (prompt). Link the primary source the roundup points to whenever that source is among the candidates, and credit its author. Link the roundup itself only when the roundup's own analysis is the point.
2. **Keep links inline in roundup excerpts** (`fetch/substack.py`). Render `<a href="U">text</a>` as `text [U]` so the editor can match stories to their sources. Raise the roundup excerpt limit to about 20,000 characters to compensate. Expected cost: about +$0.10 per edition.
3. **At most 2 items from the same site per edition** (`validate.py`, new rule `source-cap`, error). Large platforms where many authors publish are exempt: lesswrong.com, forum.effectivealtruism.org, substack.com, arxiv.org, x.com. The rule applies when an edition is created (the same moment as the provenance check), so edition 1 doesn't fail retroactively.
4. **"Why" lines in this order of preference** (prompt):
   1. the reader's friends (`Gamithra liked it`);
   2. the reader's signals (`Andrés restacked it`);
   3. breadth (`in 3 of this week's newsletters`, `162 karma on LessWrong`);
   4. a single roundup, named by publication rather than person, and only if nothing above applies.

   Remove "Zvi" from the prompt's examples.
5. **Dilute** by adding more roundups (P4).

### Acceptance
- On the next three editions: ≤ 2 items link to any one newsletter, and ≤ 2 "why" lines name any one roundup author.
- No loss in quality on the reader's read-through, judged with the prompt-evaluation procedure in docs/runbook.md.

### Not proposed
Dropping Zvi entirely. His roundup is the widest net in the current sources, and it is the raw material for The Buzz (PLAN-buzz Stage 0). The fix is to use him as an index, not to cite him less arbitrarily.

---

## P3 — Silence is not news

### Changes
- **Prompt:** remove the instruction to write a `note` when friends published nothing. If friends published nothing, fill "From your friends" with what they recommended (likes and restacks) as `friend` items. If there is nothing at all, leave the section out. Never mention in the lede that friends were quiet.
- **Edition 1 (live):** delete the note item and the lede's last sentence ("Your three friends posted nothing new."). It then has 17 items. Update the golden snapshot.
- **Model:** remove the `note` item kind; it only existed for this. Validator rules that exempted notes go with it.

### Acceptance
No edition mentions friends not publishing. The "friends always appear" check still holds whenever they do publish.

---

## P4 — More sources, and an honest list of what's missing

### Sources

| Source | Status (checked 2026-11-27) | Proposal |
|---|---|---|
| **Transformer** (transformernews.ai) | Substack; `https://www.transformernews.ai/api/v1/archive?sort=new` answers without login | **Add** as a roundup |
| **AI Safety Newsletter** (newsletter.safe.ai, CAIS) | Substack; archive endpoint answers without login | **Add** as a roundup |
| **EA Forum** | GraphQL like LessWrong, but returned a "Vercel Security Checkpoint" page to an automated request from a home connection | **Try** from GitHub Actions and via its RSS feed; add only if it works without evading the check |
| **X** | Needs a paid API, or second-hand reading via roundups | **Not in this round.** Second-hand reading (Buzz Stage 0, Milestone 4) gets easier once P2 keeps links inline |

**How to add publications:** a new `publications` list in `config/sources.json` (`{"name", "url"}`), fetched through `<url>/api/v1/archive?sort=new&limit=12`, then `posts/by-id`. This doesn't depend on what the reader's Substack account happens to subscribe to. *Alternative with no code:* subscribe to both on Substack. That's quicker but implicit, and unsubscribing silently removes a source.

Add one archive request to `timeleaf canary` per publication.

### The "what it cannot see" paragraph
Today the model writes it, so it can drift from reality (edition 1 lists Transformer and AISN as missing). Proposal: **the code writes it** from a small registry of known sources and their status, the same way the "what was checked" line is already generated. With P4 that becomes, for example:

> This edition cannot see X, the EA Forum, PauseAI's internal channels, or sites other than Substack and LessWrong. News items are reported as the linked authors describe them and were not checked against primary sources.

So, to answer the question: yes, X should always be named while it's missing; it's the biggest blind spot. Transformer and AISN drop off the list once they're added.

### Question for the reader
- **Q3.** Transformer and AISN as *roundups* (their links count as "votes" and they get longer excerpts) or as ordinary publications? Recommendation: roundups.

---

## P5 — One page of principles

Add [`docs/PRINCIPLES.md`](../PRINCIPLES.md) (draft included in this proposal): intent, 11 values, 10 user stories, how it is used, change log. It gathers what is now spread over PLAN.md §1 and PLAN-buzz §1 and §3, and adds the three values this feedback revealed (3, 6, and the second half of 7).

Follow-ups once approved:
- PLAN.md §1 shrinks to a pointer to PRINCIPLES.md (no duplicated rules).
- The PR template gains "Consistent with docs/PRINCIPLES.md?"
- Each validator rule names the value it protects in its docstring.

---

## Implementation notes for whoever implements

- One PR per part; P2 and P4 can share one.
- Tests: fixtures for the archive endpoint, inline-link rendering, the `source-cap` rule, the blind-spot registry, and the reader-page sanitiser (P1: hostile HTML must come out inert).
- Update `docs/schemas/` (`uv run timeleaf schema`) and the golden snapshot.
- P1 also needs an ADR (0005, private reading room) and changes to PLAN.md §4.2 (secrets) and docs/runbook.md.
