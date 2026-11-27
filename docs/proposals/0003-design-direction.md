# Proposal 0003 — Design direction

**Status:** Proposed, for review · **Date:** 2026-11-27 · **Author:** Claude (Opus 5.5) · **Reviewer:** Claude Fable, then the owner
**Serves:** design values 13–15 and US-11, US-12 in [PRINCIPLES.md](../PRINCIPLES.md)

## The request

> We need to think again about the core values, which include the design. At first I was thinking of an actual paper feel, like an actual newspaper, but that might not be the most convenient for the internet. I want it to look striking and different, but be very committed to usability and simplicity.

## Where the design is now (an honest read)

Edition 1's design was ported unchanged from the prototype: green on pale grey (dark mode: mint on near-black), Bricolage Grotesque for headlines, Source Serif for text, IBM Plex Mono for small labels, section names in a left rail, every headline underlined.

- **Works:** readable, calm, good on a phone, no clutter, light and dark modes.
- **Doesn't yet:**
  - **Not distinctive.** It looks like a well-made blog or newsletter, not like a paper; you wouldn't recognise it from a screenshot.
  - **No front-page hierarchy** beyond one larger lead headline.
  - **The edition's size is invisible** (17 items? 40 minutes?) until you scroll to the end.
  - **Monospace everywhere for small text** makes metadata feel technical rather than editorial.
  - **Underlined headlines** add noise.

## The core idea: the newspaper's rituals, not its material

What makes a newspaper feel like a newspaper, and whether to keep it on screen:

| Newspaper trait | On screen | Keep? |
|---|---|---|
| Masthead with the paper's name, dateline, edition number | Works; it's identity | **Yes**, and make it bolder |
| A front page that ranks stories by size | Works; it's hierarchy at a glance (US-11) | **Yes** |
| Sections with clear openers | Works; it's navigation | **Yes** |
| A definite end | Core to "finite" | **Yes** |
| Rules (lines) as structure instead of boxes and cards | Works; simple and striking | **Yes** |
| Multi-column body text | Bad on phones; awkward to scroll | **No.** Columns only for the front-page index on wide screens |
| Paper texture, yellowed tone, fake fold lines | Gimmick; hurts contrast | **No** |
| Tiny dense print | Hurts usability | **No** |
| Something you can hold | Only via print | **Optional:** a print stylesheet that gives a real A4 edition (Q11) |

## Three directions to try

All three use the same content (edition 1), the same usability rules (below), and a light and a dark version.

**A. Broadsheet.** Closest to a real paper.
- A high-contrast serif masthead.
- On wide screens, a front page in 3–4 columns of varying story sizes, with hairline rules.
- On phones, it collapses to one column.
- Striking and nostalgic. *Risks:* it can feel like a costume, and the desktop layout fights scrolling.

**B. Edition** *(recommended).* Newspaper rituals with a web-native single column.
- **Masthead as a poster:** very large paper name, with dateline and edition number set like a newspaper's.
- **A front page that works like a cover:** the lead story large, then a compact **index of the whole edition**: every section with its items as one-line headlines, each with its reading time, and the total at the top ("17 items · about 40 minutes"). Tapping an index line jumps to the item, or opens it in the reading room.
- **Section openers:** full-width rule, section name in large type, one line of note.
- **Typography carries the identity:** one display face used with confidence at extreme sizes, one text face for reading, and no monospace. Metadata in small caps of the text face.
- **Colour:** ink on paper-white, with **one accent colour per paper** (each reader's paper gets its own, a small tie to 0002). Dark mode is a deliberate "night edition", not an inverted page.
- **The end** gets a real typographic moment.

**C. Quiet book.** Book typography with almost no ornament. Supremely usable, but probably not striking enough for value 15.

**Recommendation: B**, borrowing A's rules and A's front-page index layout on wide screens.

## Usability rules (non-negotiable, all directions)

| Rule | Target |
|---|---|
| Body text | ≥ 18 px on phones, line length 60–72 characters |
| Contrast | WCAG 2.2 AA in both modes (AAA for body text where possible) |
| Tap targets | ≥ 44 × 44 px |
| Speed | ≤ 150 KB per page, including fonts; no layout shift; no JavaScript required |
| Navigation | From any item: back to the index, next and previous item, in one tap |
| Orientation | Always know where you are: "Policy desk · 4 of 17" |
| Motion | None, unless the reader starts it; respects reduced motion |
| Accessibility | Semantic headings, skip link, visible focus, screen-reader-friendly index |

These become automated checks where possible: the existing tests plus Lighthouse/axe in CI (the PLAN M2 item still open).

## Process

1. **Mock-ups:** three static pages (A, B, C) of edition 1, each with a front page, a section and a reading-room article, at phone and desktop sizes, light and dark. About 1–1.5 days.
2. **The owner picks one,** or mixes ("B, with A's masthead").
3. **Write `docs/DESIGN.md`:** tokens (type scale, colours, spacing), components (masthead, index, item, section opener, reading-room article, end mark), and the usability rules above. Each reader's accent colour is a token.
4. **Implement** in the templates, and update the golden snapshot.

Do this **before** the reading room (0001 P1, 0002 phase 4), so the reading room is built once in the final design.

## Questions for the owner

- **Q10.** Two or three things whose look you love: a newspaper, magazine, website, book or poster. They don't need to be about news.
- **Q11.** Would you want a printable edition (A4 PDF or the browser's Print) as the "real paper" option?
- **Q12.** Keep the green, or start fresh with colour? (In B, each paper chooses its own accent.)
