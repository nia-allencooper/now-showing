# Now Showing

A weekly diff of every film Odeon has a page for. Each Tuesday evening it reads
Odeon's sitemap, saves the list, compares it with last week's, and publishes a
page showing what was **added** and what was **removed** — plus an **In Theaters**
grid of everything currently listed. Every title links back to its Odeon page.

## How it fits together

| File | Job |
| --- | --- |
| `scrape.py` | Fetches `odeon.co.uk/sitemap.xml` with `curl_cffi` (browser TLS fingerprint, so Cloudflare lets it through), pulls every `/films/<slug>/HO<id>/` entry, writes `snapshots/YYYY-MM-DD.json` |
| `diff.py` | Compares two snapshots by Odeon's stable `HO…` id → added / removed |
| `build.py` | Takes the two newest snapshots, runs the diff, renders `site/index.html` from `templates/index.html.j2` |
| `.github/workflows/update.yml` | Runs the above every Tuesday, commits the snapshot, publishes `site/` to GitHub Pages |

### Why the sitemap and not the /films/ page

`odeon.co.uk/films/` is behind Cloudflare's bot challenge **and** builds its list
with JavaScript, so no unattended scraper can read it. The sitemap is plain XML
that isn't challenged for a browser-looking client. Trade-off: it gives film IDs,
URLs and slug-derived titles — **no posters, no age ratings, no now-showing vs
coming-soon split**. Titles come from the URL slug, so they're approximate
(`arrietty-dubbed` → "Arrietty Dubbed", not "ARRIETTY (DUBBED)").

## Local setup

Needs Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

Then:

```bash
python scrape.py     # writes snapshots/<today>.json
python build.py       # writes site/index.html  (open it in a browser)
```

The first run has no previous week to compare against, so the diff is empty. Run
it again next week (or hand-drop a second dated file in `snapshots/`) to see the
added/removed columns fill in.

## Publishing (GitHub Actions + Pages)

1. Push this repo to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. The workflow runs every Tuesday 19:00 UTC. Run it by hand any time from the
   **Actions** tab → *Weekly update* → *Run workflow*.

Each run commits that week's snapshot back to the repo (the baseline for next
week) and redeploys the page.

## Adding posters / real titles later

That needs the rendered `/films/` page, which means getting past Cloudflare with a
real browser:

- **Paid unblocker** (ScrapingBee / ZenRows / Scrapfly free tier) — one request a
  week fits any free plan; returns the rendered HTML. Add an enrichment step that
  maps each `HO…` id to its poster + exact title.
- **Your own PC** — a scheduled task runs a real browser against `/films/`,
  writes the richer snapshot, pushes it; Actions just rebuilds.

## Tweaks

- **Run time:** the `cron:` line in `.github/workflows/update.yml`.
- **"Blocked" guard:** `MIN_FILMS` in `scrape.py` (currently 30) stops an empty
  fetch being published as "almost everything removed".
- **Look:** everything visual is in `templates/index.html.j2` (inline CSS).
