# Principles

**Status:** Accepted 2026-11-27 (see [proposals/DECISIONS.md](proposals/DECISIONS.md)) · **Owner:** the owner of Timeleaf

The one place that says what The Loop is for. Plans, prompts, validators and reviews refer back here. When a change conflicts with this page, either the change or this page is wrong: decide which, and record it in the change log at the bottom.

Sources: docs/PLAN.md §1, docs/PLAN-buzz.md §1 and §3, and the reader's feedback of 2026-11-27.

## Intent

Timeleaf makes each reader **their own weekly paper**: what the people they trust are reading and arguing about, on the subjects they care about, without a feed, in one calm and striking place, once a week. It is private to that reader.

It started with one reader. They work in AI safety advocacy and have left social media, and their paper, *The Loop*, covers AI safety and AI policy first, and rationalist, post-rationalist and contemplative writing second. A friend's paper is next.

## Values

1. **Finite.** One edition a week, about 15–18 items, and then it ends: *"That is all for this week."* The Buzz and any new section replace weaker items; they never make the paper longer.
2. **Trust over popularity.** Things arrive through people the reader trusts. Raw popularity is not a reason to include something.
3. **Breadth over one voice.** No single writer or newsletter dominates an edition. Roundups are an index for finding stories, not where the stories should come from.
4. **Say why, in terms the reader recognises.** Every item says who pointed at it. People the reader knows come first; strangers' names mean little.
5. **Respect attention.** News is compressed so the reader rarely needs to click. Essays get a reason to read and a reading time, never a summary.
6. **One place, one vibe.** Reading happens inside The Loop, in its own typography, not in other apps.
7. **Friends always appear, and silence is not news.** Everything a friend publishes is included. Weeks when they publish nothing are not mentioned.
8. **Honest about blind spots.** Each edition says what it checked, what failed, and what it cannot see.
9. **Calm.** No likes, counts, streaks, notifications or infinite scroll. Feedback is given in words.
10. **A person approves what goes public.** An AI drafts the paper. Nothing goes public without a person approving it. A private paper goes straight to its one reader after the automatic checks; the reader's feedback is the correction loop.
11. **Respect writers.** Credit and link the original. Never republish others' work publicly. Paywalls are respected.
12. **Private by default.** A reader's interests, sources and paper are seen only by that reader and by the owner of Timeleaf, who runs the service. Readers are told this before they sign up. No one else sees them unless the reader shares.

### Design values

13. **Usable first.** Easy to read on a phone at 7 a.m. and on a laptop at night: large text, short lines, obvious navigation, fast, works without JavaScript, accessible. When striking and usable conflict, usable wins.
14. **Simple.** Few elements, and each one earns its place. No chrome, no badges, nothing that moves unless the reader moves it.
15. **Striking and its own.** Recognisable from a single screenshot. It borrows the newspaper's *rituals*: masthead, dateline, sections, a lead story, an end. It does not imitate the newspaper's *material*: paper textures, cramped columns on a phone, tiny print.

## User stories

As **the reader**:

- **US-1** On Friday morning I read one edition in 30–45 minutes and know what colleagues will be talking about on Monday. *(values 1, 5)*
- **US-2** I read the full text of a piece, with its pictures, without leaving The Loop. *(6, 11)*
- **US-3** I see everything my friends published this week, and nothing about weeks they didn't publish. *(7)*
- **US-4** For every item I can tell why it is there, through people I know or through how widely it was discussed. *(2, 4)*
- **US-5** The paper covers the whole field, not one commentator's view of it. *(3)*
- **US-6** Now and then I meet a new voice that people I trust engaged with, and I decide whether to follow them. *(2)*
- **US-7** I know what the edition could not see, so I know what I might be missing. *(8)*
- **US-8** I can tell the editor what to change in plain words. *(9)*

- **US-11** I can tell a story's importance and the size of the whole edition at a glance, before I start reading. *(5, 13, 15)*
- **US-12** When I open my paper it feels like *my* paper, with its name, and it looks like nothing else I use. *(6, 15)*

As **a new reader** (a friend of the owner):

- **US-13** I set up my own paper in under 15 minutes by describing my interests and the people I trust, in my own words. *(2, 12)*
- **US-14** I change what I get by writing feedback in words, and the next edition reflects it. *(9)*

As **the approver** (for *The Loop*, the same person as its reader, in another role):

- **US-9** I review and approve an edition in under 10 minutes, and nothing goes out without that. *(10)*

As **a writer whose work appears**:

- **US-10** My work is credited and linked, and is not republished to the public without my permission. *(11)*

## How this page is used

- `src/timeleaf/edit/prompt.md` restates values 1–7 as instructions to the editor.
- `src/timeleaf/validate.py` enforces the parts that can be checked by a program, and names the value each rule protects.
- Every proposal in `docs/proposals/` lists which values and stories it serves or changes.
- The PR template asks: *"Consistent with docs/PRINCIPLES.md?"*

## Change log

| Date | Change | Why |
|---|---|---|
| 2026-11-27 | First draft. Added values 3, 6 and the second half of 7 | Reader feedback round 1 |
| 2026-11-27 | Intent widened to one private paper per reader; value 10 reworded; value 12 added; US-13, US-14 | Proposal 0002 (a friend gets their own paper) |
| 2026-11-27 | Design values 13–15; US-11, US-12 | Owner: "striking and different, but core committed to usability and simplicity" (proposal 0003) |
