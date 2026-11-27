# The Loop

A weekly personal newspaper.

1. `python3 fetch.py candidates.json 7` collects the week's candidates (friends, Substack subscriptions, likes from the circle, LessWrong top posts).
2. An editor reads the candidates and writes `editions/DATE.json`.
3. `python3 build.py editions/DATE.json` renders `site/index.html` and `site/editions/DATE.html`.

Sources and friends are in `sources.json`. `site/` is a static site that can be served by GitHub Pages.
