# ADR 0002 — Python package with Jinja2 as the static site generator

- **Status:** Accepted · 2026-11-27

## Context
Fetching, editing and building are all Python in the prototype. The site is a few templates: edition, archive, about, 404, feed.

## Decision
One Python 3.12 package (`timeleaf`) with a CLI. Templates in Jinja2 with autoescaping. Dependencies via uv. No JavaScript framework and no client-side JS in v1.

## Alternatives considered
- **Astro / Eleventy / Hugo:** good generators, but they split the codebase into two languages and toolchains for a site with five templates.
- **Keep f-string templating from the prototype:** no autoescape-by-default, hard to maintain as pages grow.

## Consequences
- One language, one lockfile, one test runner.
- If the site later needs rich interactivity, reconsider with a new ADR.
