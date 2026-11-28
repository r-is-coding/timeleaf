# Your own weekly paper

Timeleaf makes you a paper of your own: once a week, about fifteen things that the people you trust were reading and arguing about, on the subjects you care about. Then it ends. There is no feed, no likes and no notifications.

To set it up, answer the questions below in your own words and send them back to the person who invited you (the owner of Timeleaf). It takes about 15 minutes. Nothing here is final: you change your paper later by saying what you want changed, in plain words.

## Before you answer: who sees what

Please read this first. If any of it is not fine with you, say so, or do not sign up.

**Who can see your paper and your answers.** **You**, and **the owner of Timeleaf**, who runs the service and can read everything in it: your answers below, your sources, your notes and every edition of your paper. Technically, anyone the owner gives access to the code repository could see it too (today that is nobody else), and so can the services in the table below, which store or process it. Nobody else sees it unless you share it.

**Which services handle your data.**

| Service | What it handles | Why |
|---|---|---|
| **GitHub** | Your answers (including your login email), your sources, your notes and your editions, stored as files; the weekly job's logs and temporary files (kept up to 90 days) | Storage and automation |
| **Anthropic** (the Claude API) | Each week: your description of yourself, your notes, and the week's candidate posts. Not your email address | An AI model drafts your paper |
| **Cloudflare** (later, once papers are behind a login) | Your email address, to send you a one-time login code, and the pages of your paper | Hosting and login |

Substack and LessWrong are read without logging in. If you give a Substack handle, Timeleaf reads only what your profile already shows publicly: which publications you subscribe to.

**What your paper is not.** It is drafted by an AI model from what was collected that week. News items are reported as their authors describe them and are not checked against primary sources. Each edition ends with a note on what was checked and what the paper cannot see.

**People you name.** The friends and writers you list are stored with your answers, and their public posts are read and linked. Only name people whose public writing you want in your paper.

**How to be removed.** Tell the owner. They run `timeleaf reader remove <your id>`, which deletes your folder: your answers, sources, notes and every edition. They then remove it from the stored history and from Cloudflare's login list (see docs/runbook.md, *Removing a reader*). You can ask for a copy of everything first.

**When your paper starts.** Not before it can be kept private. Today the Timeleaf repository is public, so no new reader's answers are stored in it until the papers are behind a login.

## The questions

### 1. A name for your paper

The owner's is called *The Loop*. Yours can be anything.

### 2. The email address you will log in with

A one-time code is sent to it when you open your paper. It is used for nothing else, and you get no other email.

### 3. Your Substack handle and your X handle (both optional)

With a Substack handle, the publications you subscribe to become sources for your paper. X cannot be read yet; the handle is kept for when it can.

### 4. About you, in a few paragraphs

Write as you would to a well-read friend who is going to pick your reading for you.

- **What you do.** Your work, and what you are in the middle of.
- **What you want to understand better.** Subjects, questions, arguments you want to follow. Say which matter most.
- **What you never want to see.** Topics, tones, kinds of post.
- **How long you want to read each week.** Twenty minutes over coffee, or an hour on Sunday.

### 5. At least three people or publications whose judgement you trust

Your paper is built from what people you trust wrote, liked and linked, not from what is popular. Three is the minimum; ten is better. For each, a name and a link (a Substack, a blog, a newsletter).

If some of them write weekly round-ups of what happened in a field, say which: Timeleaf uses those to find stories, and then links you to the original.

### 6. Friends whose every post must appear

People whose writing you never want to miss, whatever it is about. Everything they publish will be in your paper. Weeks when they publish nothing are simply not mentioned.

## What happens next

1. The owner sets up your paper from your answers.
2. **The first edition is a trial.** Read it and reply in words: too much of this, none of that, never mention the other thing. Your reply is kept as a standing note to the editor.
3. From the second edition on, your paper follows your notes. You can send new ones at any time.

---

## For the owner: turning answers into a reader

Do this only once the repository is private (docs/proposals/DECISIONS.md, review note 6). Until then, never commit another person's answers.

```bash
uv run timeleaf reader add <id> --paper-name "<their name for it>" --email <their email> [--substack <handle>]
```

Then fill in the folder it creates, `readers/<id>/`:

| File | From |
|---|---|
| `profile.md` | Question 4, in their words. Do not rewrite it |
| `sources.json` | `friends` from question 6; `publications` (name and URL) and `signal_handles` from question 5; the round-ups among them also go in `roundups` |
| `reader.json` | Section titles and notes, if they want different ones; `review` (`"auto"` once their paper is private); `blind_spots` for things only they would miss |
| `notes.md` | Empty at first. Their feedback goes here, newest first, in their words |

```bash
uv run timeleaf reader check <id>          # says what is still missing
uv run timeleaf fetch --reader <id> -o candidates-<id>.json
uv run timeleaf edit candidates-<id>.json --reader <id> --dry-run   # cost estimate only
```

The weekly workflow picks up every reader in `readers/` by itself.
