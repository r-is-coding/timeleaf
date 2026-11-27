# ADR 0001 — Static site on GitHub Pages at timeleaf.ee

- **Status:** Accepted · 2026-11-27

## Context
The Loop is one page per week, read by a handful of people. The prototype already emits static HTML. The owner wants it on GitHub, at timeleaf.ee, with no servers to look after.

## Decision
Publish a fully static site to GitHub Pages using the Actions deploy flow (`upload-pages-artifact` + `deploy-pages`), with timeleaf.ee as a verified custom domain and HTTPS enforced.

## Alternatives considered
- **Cloudflare Pages / Netlify:** real HTTP headers (CSP, caching) and per-PR preview URLs. Rejected for v1: another account and vendor for little gain; we set CSP with a `<meta>` tag and use workflow artifacts for previews. Revisit if per-PR live previews become important.
- **A VPS or a dynamic app:** unnecessary for weekly static content; adds patching, uptime and cost.

## Consequences
- No server-side code, no response headers; CSP via `<meta>`.
- Pages from a private repo needs a paid GitHub plan (see PLAN Q2).
- Rollback = revert the commit on `main`; the deploy reruns.
