# Plan: add "The Buzz" (what X is talking about) to The Loop

Handoff document. It is written for a Claude session that has not seen the earlier conversation.

## 1. Context

**The reader.** Works at PauseAI. Deleted social media but wants to stay in the loop on AI safety and AI policy, and for curiosity on rationalist / post-rationalist / contemplative writing. Wants novelty through people they trust, not through a fixed source list.

**What exists.** "The Loop", a weekly personal newspaper. Edition 1 (20–27 Nov 2026) is published as a private preview at https://claude.ai/artifact/Ciha5JMRSMhAUAanswSczA. The pipeline is three steps:

1. `fetch.py OUT.json 7` collects candidates and writes one JSON file.
2. An editor (Claude) reads the candidates and writes `editions/DATE.json`.
3. `build.py editions/DATE.json` renders a static site into `site/`.

`sources.json` holds the reader's Substack handle (`richard594526`), three friends whose every post must appear (`gamithra` with recommendations, `outsideourcave`, `amoretlicentia`), the roundup publications, and signal handles.

**Where the code is.** It was committed to a local git repo in a cloud session with no GitHub connected. Unless the reader has since pushed it or attached `the-loop.tar.gz`, it is gone and must be rebuilt. Appendix A lists the endpoints that were verified to work, which is most of what is needed.

**Decisions already made. Do not reopen them.**
- Weekly, finite, capped at about 15–18 items. It ends with "That is all for this week."
- Every item has a "why it is here" line naming who pointed at it.
- News is compressed. Essays get a pitch and a reading time, never a summary.
- The form is a public static website (GitHub Pages intended).
- No thumbs-up buttons. Feedback is given in words.
- A colophon states what was checked, what failed, and what the edition cannot see.

## 2. Goal

Add a section called **The Buzz**: what the relevant circles on X argued about this week. The reader wants the feel of having been on the timeline, without the timeline.

The unit is a **conversation**, not a tweet. A good entry reads like:

> **Is Anthropic's plan "handoverism"?** Critics say the lab's strategy amounts to handing power to its models. Dario Amodei replied at length. Habryka's read: Anthropic believes its own superintelligence would be safe and everyone else's catastrophic. [3 linked tweets]
> *Why it is here: 14 accounts in your AI safety circle posted on this; Zvi quoted 6 of them.*

Three to five conversations per edition. Two circles, kept apart: **AI safety and policy** (the main one) and **post-rat / contemplative** (one or two entries at most).

## 3. First principles

- **Buzz is breadth inside the circle, not raw popularity.** Rank a conversation by how many distinct circle accounts took part, not by likes. A tweet with 50k likes that nobody in the circle touched is not buzz.
- **Show the disagreement.** Name the sides and link one representative tweet per side.
- **No outrage for its own sake.** Drop pile-ons and personal drama unless they change what people at PauseAI need to know.
- **Say how it was seen.** Each entry is labelled as read directly from X or seen second-hand through a roundup.
- **A quiet week is allowed.** If nothing clears the bar, the section says so in one line.

## 4. Approach, in three stages

Build them in order. Stop after any stage if the reader is satisfied.

### Stage 0: second-hand buzz. No X access, no cost.

Zvi Mowshowitz's posts quote dozens of tweets each week in the form `Name : quoted text`, with links to `x.com/<handle>/status/<id>`. Other seeds link tweets too. `fetch.py` already downloads these bodies and extracts links.

1. From every seed post body in the window, extract tweet links together with the handle, the display name before the quote, the quoted text, and the heading of the section it sits under.
2. Count per handle and per section. Zvi's section headings ("The Quest for Sane Regulations", "Rhetorical Innovation") are already a rough topic clustering.
3. Give the editor this table. The editor writes the Buzz entries from it.
4. Run the same extraction over the last 8–10 weeks of Zvi's posts once, to produce a ranked list of the handles he quotes most. Save it as `circle_ai.json`. This is the data-driven definition of the AI safety circle, and Stage 1 needs it.

Limits to state in the colophon: this is one curator's view, it lags by a few days, and it barely covers the post-rat circle.

### Stage 1: read the circle directly.

1. **Circles.** `circle_ai.json` from Stage 0 (trim to roughly 80–150 accounts, and let the reader strike or add names). `circle_tpot.json` seeded from the reader's X following (handle `@_virtual_vapor`; a partial list is in Appendix B).
2. **Access.** Compare current options before choosing, because pricing and terms change often: the official X API, and established third-party read APIs. Also check whether the Community Archive (an open archive of tweets donated by TPOT users) covers enough of the second circle to avoid paying for it. Prefer the official API if the weekly cost is acceptable. Do not log in as the reader, use their cookies, or scrape behind a login.
3. **Fetch.** For each account, the week's original posts, quotes and replies with engagement counts and the IDs of what they quote or reply to. Where the provider supports list timelines or batched search (`from:a OR from:b`), use them to cut the number of calls.
4. **Group.** Link posts into threads by reply, quote and shared URL. Then have an LLM merge threads about the same subject and name each conversation.
5. **Score.** Distinct circle participants first, then whether a seed roundup also covered it, then engagement as a tie-breaker.
6. **Write.** The editor writes the top three to five as described in section 2.

### Stage 2: discovery.

Accounts outside the circle that three or more circle members quoted or replied to in a month become candidates. Show at most one per edition as "New voice", with who engaged with them. The reader decides whether to add them.

## 5. Changes to the code

- `fetch.py`: add a `buzz` key to the output. Stage 0 fills `buzz.secondhand` (rows of handle, name, text, url, source post, section). Stage 1 fills `buzz.conversations` (title, participants, tweets, score).
- `sources.json`: add `x.circles` (paths to the two circle files) and `x.provider`.
- Edition JSON: add a section `{"title": "The Buzz", ...}`. Each item needs a `more` list of tweet links and a `seen` field with the value `direct` or `via <source>`. `build.py` should render `seen` next to the "why it is here" line.
- Colophon: add accounts read, accounts that failed, and API spend for the edition.

## 6. Environment constraints

- The cloud environment only allows listed hosts. So far: `substack.com`, `www.astralcodexten.com`, `thezvi.substack.com`, `www.lesswrong.com`. The X data host will need to be added, and the API key requested through the secure credential form. Never ask the reader to paste a key into chat or put one in code.
- Set a hard spend cap per run and stop when it is reached.
- The site is public. Quote only public posts, link to the original, and keep quotes short.

## 7. Done when

- Stage 0: an edition contains a Buzz section built only from seed posts, each entry with at least two linked tweets and a `seen: via` label, and `circle_ai.json` exists.
- Stage 1: a run reads at least 90% of circle accounts, the colophon reports failures and spend, and the reader agrees that the top conversations match what they hear from colleagues that week.
- Both: the edition still ends within the item cap. The Buzz replaces weaker items; it does not lengthen the paper.

## 8. Questions for the reader before Stage 1

1. What weekly spend on X data is acceptable?
2. Should replies count, or only original posts and quotes?
3. Should the post-rat circle be read directly, or is second-hand enough?
4. Has GitHub been connected, and what is the repo name?

## Appendix A: endpoints verified on 27 Nov 2026

All on `substack.com`, no login, send a browser User-Agent:

- Profile, including subscriptions and each publication's `author_id`: `/api/v1/user/<handle>/public_profile`
- A person's posts (teasers only): `/api/v1/profile/posts?profile_user_id=<id>&limit=8`
- Full post body by id: `/api/v1/posts/by-id/<post_id>` (field `post.body_html`)
- A person's activity (notes, restacks): `/api/v1/reader/feed/profile/<id>`; likes: add `?types[]=like`. Items carry `context.type` (`post_like`, `post_restack`, `note`) and `context.timestamp`.
- Publication archives on `<name>.substack.com` are a different host and were not allowed; going through the author id avoids that.

LessWrong: POST to `https://www.lesswrong.com/graphql` with
`{posts(input:{terms:{view:"top",limit:25,after:"YYYY-MM-DD"}}){results{title baseScore commentCount pageUrl postedAt wordCount user{displayName} tags{name} contents{plaintextDescription}}}}`

## Appendix B: reader's X following (partial, contemplative circle)

OpenDharmaFdn, TVachaW, vividvoid, dewy_stars, QualiaRI, manamajere, nickcammarata, gptbrooke, tasshinfogleman, RichDecibels, joespurpleshirt, RomeoStevens76, IkkyusDen, frideswyth, 42irrationalist, nwspk, RogerThisdell

Substack subscriptions: Andrés Gómez-Emilsson, Astral Codex Ten, Don't Worry About the Vase, The EU AI Act Newsletter, Good Structures, Gwern.net Newsletter, In One Lifetime, Integral Altruism, Meaningness, The Modern Improviser, No Ghosts, No One's Busyness, Notes on the Research System.
