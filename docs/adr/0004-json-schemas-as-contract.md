# ADR 0004 — Versioned JSON schemas are the contract between stages

- **Status:** Accepted · 2026-11-27

## Context
Three stages (fetch, edit, build) and a human editor all touch the same files. The prototype has no schema, so a typo in an edition breaks the build silently or renders badly.

## Decision
Pydantic v2 models for `Sources`, `Candidates` and `Edition` in `src/timeleaf/models.py`. Every file carries `schema_version`. JSON Schemas are generated from the models and committed in `docs/schemas/`; the `Edition` schema is also what the Claude API is constrained to.

## Consequences
- Each stage validates input and output; CI validates every edition in `content/`.
- Breaking changes bump `schema_version` and ship a `timeleaf migrate` step for existing editions.
- Edition JSON in git is the source of truth; HTML is always regenerated.
