#!/usr/bin/env python3
"""Render an edition JSON to site/index.html and site/editions/DATE.html. Usage: build.py editions/DATE.json [fragment_out]"""
import json, sys, html, os, glob
e = json.load(open(sys.argv[1])); esc = html.escape
here = os.path.dirname(os.path.abspath(__file__))
CSS = open(os.path.join(here, "style.css")).read()

def item(i, lead=False):
    t = esc(i["title"])
    if i.get("url"): t = f'<a href="{esc(i["url"])}">{t}</a>'
    meta = " · ".join(x for x in [esc(i["source"]) if i.get("source") else "", f'{i["mins"]} min' if i.get("mins") else ""] if x)
    more = "".join(f'<li><a href="{esc(m["url"])}">{esc(m["label"])}</a></li>' for m in i.get("more", []))
    return (f'<article class="item{" lead" if lead else ""}"><p class="kicker">{esc(i["kicker"])}</p><h3>{t}</h3>'
            + (f'<p class="meta">{meta}</p>' if meta else "") + f'<p class="body">{esc(i["body"])}</p>'
            + (f'<ul class="more">{more}</ul>' if more else "")
            + (f'<p class="why"><span>Why it is here</span> {esc(i["why"])}</p>' if i.get("why") else "") + "</article>")

secs = ""
for n, s in enumerate(e["sections"]):
    secs += (f'<section><header class="sec"><h2>{esc(s["title"])}</h2><p>{esc(s["note"])}</p></header>'
             + "".join(item(i, lead=(n == 0 and k == 0)) for k, i in enumerate(s["items"])) + "</section>")
count = sum(len(s["items"]) for s in e["sections"])
page = f'''<meta name="claude:viewport-fit-sides" content="cover">
<title>The Loop</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="mast"><p class="issue">No. {e["number"]} · {esc(e["range"])}</p><h1>The Loop</h1><p class="lede">{esc(e["lede"])}</p></header>
{secs}
<footer><p class="end">That is all for this week.</p>
<p><strong>What was checked.</strong> {esc(e["colophon"]["checked"])}</p>
<p><strong>What it cannot see.</strong> {esc(e["colophon"]["blind"])}</p></footer>
</div>'''
full = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>{page}</body></html>'
os.makedirs(os.path.join(here, "site", "editions"), exist_ok=True)
for p in ("site/index.html", f'site/editions/{e["date"]}.html'):
    open(os.path.join(here, p), "w").write(full)
if len(sys.argv) > 2: open(sys.argv[2], "w").write(page)
print("built", e["date"], count, "items")
