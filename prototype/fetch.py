#!/usr/bin/env python3
"""Collect candidate items for one edition. Usage: fetch.py OUT.json [days]"""
import json, sys, re, html, time, urllib.request, urllib.parse, datetime as dt

UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 7
NOW = dt.datetime.now(dt.timezone.utc)
CUT = NOW - dt.timedelta(days=DAYS)
cfg = json.load(open(__file__.rsplit("/", 1)[0] + "/sources.json"))
health = {"ok": 0, "failed": []}

def get(url, data=None):
    for i in range(3):
        try:
            r = urllib.request.Request(url, headers=UA, data=data.encode() if data else None)
            out = json.loads(urllib.request.urlopen(r, timeout=30).read())
            health["ok"] += 1
            return out
        except Exception as e:
            err = str(e); time.sleep(2 * (i + 1))
    health["failed"].append(f"{url[:90]} ({err})")
    return None

def text(h, n):
    t = html.unescape(re.sub(r"<[^>]+>", " ", h or ""))
    return re.sub(r"\s+", " ", t).strip()[:n]

def when(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

def profile(handle):
    return get(f"https://substack.com/api/v1/user/{handle}/public_profile")

def posts_by(uid, limit=8):
    j = get(f"https://substack.com/api/v1/profile/posts?profile_user_id={uid}&limit={limit}")
    return (j or {}).get("posts", [])

def full(p):
    """The posts list only carries a teaser; fetch the whole post."""
    j = get(f"https://substack.com/api/v1/posts/by-id/{p['id']}") or {}
    return j.get("post") or p

def heads(p):
    return [text(h, 120) for h in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", p.get("body_html") or "", re.S)][:60]

def slim(p, n=1500):
    return {"title": p.get("title"), "subtitle": p.get("subtitle"), "url": p.get("canonical_url"),
            "date": (p.get("post_date") or "")[:10], "words": p.get("wordcount"),
            "likes": p.get("reaction_count"), "paywalled": p.get("audience") == "only_paid",
            "authors": [b.get("name") for b in p.get("publishedBylines", [])],
            "excerpt": text(p.get("body_html") or p.get("truncated_body_text") or p.get("description"), n)}

def links(p):
    out = []
    for u in re.findall(r'href="(https?://[^"#?]+)', p.get("body_html") or ""):
        if not re.search(r"substackcdn|/subscribe|twitter\.com/intent|\.(png|jpg|jpeg|gif)$", u):
            out.append(u.rstrip("/"))
    return sorted(set(out))

def activity(uid, days):
    """Posts a person liked or restacked: their recommendations."""
    j = get(f"https://substack.com/api/v1/reader/feed/profile/{uid}") or {}
    j2 = get(f"https://substack.com/api/v1/reader/feed/profile/{uid}?types%5B%5D=like") or {}
    out, seen = [], set()
    for it in j.get("items", []) + j2.get("items", []):
        c, p = it.get("context") or {}, it.get("post")
        if not p or c.get("type") not in ("post_like", "post_restack", "restack", "note") or not c.get("timestamp"):
            continue
        if when(c["timestamp"]) < NOW - dt.timedelta(days=days) or p.get("id") in seen:
            continue
        if c.get("type") == "note" and uid in [b.get("id") for b in p.get("publishedBylines", [])]:
            continue
        seen.add(p["id"])
        d = slim(p, 500); d["how"] = c["type"]; d["when"] = c["timestamp"][:10]
        d["publication"] = (it.get("publication") or {}).get("name")
        out.append(d)
    return out

res = {"generated": NOW.isoformat(), "window_days": DAYS, "friends": [], "seeds": [], "signals": [], "lesswrong": []}
link_votes = {}

for f in cfg["friends"]:
    pr = profile(f["handle"])
    if not pr: continue
    ps = [slim(full(p) if i == 0 or (p.get("post_date") or "") >= CUT.isoformat()[:19] else p, 4000) for i, p in enumerate(posts_by(pr["id"], 6))]
    entry = {"name": f["name"], "handle": f["handle"],
             "new_posts": [p for p in ps if p["date"] >= CUT.date().isoformat()],
             "latest_post": ps[0] if ps else None}
    if f.get("recommendations"):
        entry["recommended"] = activity(pr["id"], f.get("rec_days", DAYS))
    res["friends"].append(entry)

me = profile(cfg["me"])
seeds = {s["publication"]["author_id"]: s["publication"]["name"] for s in (me or {}).get("subscriptions", [])}
for h in cfg.get("extra_seed_handles", []):
    pr = profile(h)
    if pr: seeds[pr["id"]] = (pr.get("primaryPublication") or {}).get("name") or pr["name"]
friend_handles = {f["handle"] for f in cfg["friends"]}
for uid, name in seeds.items():
    for p in posts_by(uid, 8):
        if (p.get("post_date") or "") < CUT.isoformat()[:19]: continue
        if (p.get("wordcount") or 0) < 300: continue  # open threads, admin notes
        p = full(p)
        d = slim(p, 12000 if name in cfg.get("roundups", []) else 3500); d["publication"] = name
        d["headings"] = heads(p)
        if any(d["url"] == q["url"] for fr in res["friends"] for q in fr["new_posts"]): continue
        res["seeds"].append(d)
        for u in links(p): link_votes.setdefault(u, set()).add(name)

for h in cfg.get("signal_handles", []):
    pr = profile(h)
    if not pr: continue
    for a in activity(pr["id"], DAYS * 2):
        a["via"] = pr["name"]; res["signals"].append(a)

q = '{posts(input:{terms:{view:"top",limit:25,after:"%s"}}){results{title baseScore commentCount pageUrl postedAt wordCount user{displayName} tags{name} contents{plaintextDescription}}}}' % CUT.date().isoformat()
j = get("https://www.lesswrong.com/graphql", json.dumps({"query": q}))
for p in ((j or {}).get("data", {}).get("posts", {}) or {}).get("results", []):
    res["lesswrong"].append({"title": p["title"], "url": p["pageUrl"], "karma": p["baseScore"], "comments": p["commentCount"],
        "author": (p.get("user") or {}).get("displayName"), "date": p["postedAt"][:10], "words": p.get("wordCount"),
        "tags": [t["name"] for t in p.get("tags") or []][:6],
        "excerpt": ((p.get("contents") or {}).get("plaintextDescription") or "")[:1800]})
    link_votes.setdefault(p["pageUrl"].rstrip("/"), set()).add("LessWrong top")

res["co_cited"] = sorted([{"url": u, "by": sorted(v)} for u, v in link_votes.items() if len(v) >= 2], key=lambda x: -len(x["by"]))
res["health"] = health
json.dump(res, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
print(f"friends {len(res['friends'])} | seed posts {len(res['seeds'])} | signals {len(res['signals'])} | LW {len(res['lesswrong'])} | co-cited {len(res['co_cited'])} | ok {health['ok']} failed {len(health['failed'])}")
for f in health["failed"]: print("FAILED", f)
