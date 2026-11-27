# ADR 0003 — Claude drafts each edition; a person approves it via pull request

- **Status:** Accepted · 2026-11-27

## Context
Edition 1 was edited by Claude in a chat session. To run weekly without effort, the editor step must be automated, but the site is public and names real people, so nothing should go live unreviewed.

## Decision
- A scheduled workflow calls the Claude API (`claude-opus-5-5`, effort `high`, streaming) with **structured outputs** whose schema is the `Edition` model.
- Output is checked by deterministic validators (schema, item cap, friends' posts present, every URL traceable to the fetched candidates). One automatic repair round-trip is allowed.
- The result is opened as a pull request. Merging it is the act of publishing.
- Facts about the run (requests made, failures, cost) are written by code, not by the model.
- Refusals: server-side fallback (`fallbacks: "default"`); `stop_reason` is always checked.

## Alternatives considered
- **Fully automatic publishing:** fastest, but a wrong or injected item goes straight to a public page.
- **Manual editing every week:** the current state; it does not scale with the owner's time.
- **An agent with web tools:** more reach, but harder to constrain and audit; the fetch step already gathers what the editor needs.

## Consequences
- ~US$0.50–1.00 per edition; per-run cap enforced in code.
- Edition PRs must trigger CI, so they are opened with a GitHub App / fine-grained token, not `GITHUB_TOKEN`.
- Prompt changes are reviewed like code and evaluated on stored candidate artifacts.
