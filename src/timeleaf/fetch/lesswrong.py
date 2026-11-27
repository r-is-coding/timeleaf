"""LessWrong GraphQL: top posts in the window."""

from __future__ import annotations

import datetime as dt

from timeleaf.fetch.http import Http
from timeleaf.models import LessWrongPost

ENDPOINT = "https://www.lesswrong.com/graphql"
QUERY = (
    '{posts(input:{terms:{view:"top",limit:%d,after:"%s"}}){results{title baseScore commentCount pageUrl '
    "postedAt wordCount user{displayName} tags{name} contents{plaintextDescription}}}}"
)


def top_posts(http: Http, since: dt.date, limit: int = 25) -> list[LessWrongPost]:
    j = http.json(ENDPOINT, {"query": QUERY % (limit, since.isoformat())})
    results = (((j or {}).get("data") or {}).get("posts") or {}).get("results") or []
    out = []
    for p in results:
        out.append(
            LessWrongPost(
                title=p["title"],
                url=p["pageUrl"],
                karma=p.get("baseScore") or 0,
                comments=p.get("commentCount") or 0,
                author=(p.get("user") or {}).get("displayName"),
                date=(p.get("postedAt") or "")[:10],
                words=p.get("wordCount"),
                tags=[t["name"] for t in p.get("tags") or []][:6],
                excerpt=((p.get("contents") or {}).get("plaintextDescription") or "")[:1800],
            )
        )
    return out
