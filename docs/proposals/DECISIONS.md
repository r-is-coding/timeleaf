# Decisions and review: proposals 0001–0003

**Date:** 2026-11-27 · **Reviewer:** Claude (Fable 5.2) · **Decided by:** the owner

This page is the outcome of the review. Where it differs from a proposal's text, this page wins.

## Owner's answers

| # | Question | Answer |
|---|---|---|
| Q1 | Does anyone else read *The Loop*? | Not now. Timeleaf grows by giving others **their own** papers, a friend first |
| Q2 | Cloudflare for the private part? | Yes |
| Q3 | Transformer and AISN as roundups (links count as votes)? | Yes |
| Q4 | The friend's interests? | They fill in the questionnaire themselves |
| Q5 | Who pays for the friend's drafting? | The owner. Cap: $2 per edition (default) |
| Q6 | Can the owner read the friend's paper? | **Yes** |
| Q7 | Weekly "your paper is ready" email? | No |
| Q8 | *The Loop*: PR approval or automatic? | **Automatic** (see review note 1) |
| Q9 | Move DNS to Cloudflare? | Yes |
| Q10 | Design references | [Asterisk](https://asteriskmag.com/issues/16/the-dream-of-an-aristotelian-machine), [Gi Effektivt](https://gieffektivt.no/) |
| Q11 | Printable edition? | No |
| Q12 | Colour | Designer's choice; **one fixed look for every paper** for now (no per-paper accents) |

## Review notes (changes to the proposals)

1. **Automatic publishing waits for private hosting.** Q8 says publish automatically, but today the paper is on a public site, and value 10 says nothing goes public without a person approving it. So `review` is a per-reader setting, and *The Loop* stays on `"pr"` until it is behind a login (0002 phase 2). The switch to `"auto"` is then a one-line change.
2. **Q6 changes value 12.** It now reads: a reader's paper is private to them **and the owner of Timeleaf**. The questionnaire and the privacy note say so in plain words, so the friend knows before they sign up.
3. **No shared shelf yet** (0002). `config/shelf.json` is cut from v1. The questionnaire asks for at least three trusted people or publications; add a shelf only if a real reader turns out to need one.
4. **No design bake-off** (0003). The owner delegated the choice, so the three mock-ups are skipped. The designer implements direction **B, "Edition"**, informed by the two references, and the owner reacts to the real thing. One accent colour for all papers (Q12); the "accent per paper" idea is dropped.
5. **No print stylesheet** (Q11) and **no email** (Q7). Both are removed from scope.
6. **The repo stays public until the Cloudflare move.** Making it private now would take the site offline, because free GitHub Pages needs a public repo. Until then, **no friend's data is committed**; the friend is onboarded only after the move.
7. **Order of work:**
   1. 0001 P3, P2, P4, P5, and the per-reader refactor (0002 phase 1), with *The Loop* as the only reader and no change to its address.
   2. Design (0003), in parallel.
   3. Reading room and per-reader private builds (0001 P1, 0002 phases 2 and 4): code can be written and tested now, but it only goes live after the owner creates the Cloudflare account and moves DNS.
   4. Onboard the friend (0002 phase 3).

## What needs the owner

- Create a Cloudflare account and add `timeleaf.ee` to it (step-by-step instructions will be in docs/runbook.md when the hosting code lands).
- Add `ANTHROPIC_API_KEY` (still pending; the editor has never run live).
- Send the questionnaire to the friend once it exists (`docs/onboarding.md`).
