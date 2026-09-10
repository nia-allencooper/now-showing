# Now Showing

A weekly diff of every film Odeon is listing. Each Tuesday evening it scrapes
Odeon's "all films" page, saves the list, compares it with last week's, and
publishes a page showing what was **added** and what was **removed** — each title
linking back to its Odeon page.

## How it fits together

| File | Job |
| --- | --- |
| `scrape.py` | Drives headless Chromium to load `odeon.co.uk/films`, reads every film card, writes `snapshots/YYYY-MM-DD.json` |
| `diff.py` | Compares two snapshots by Odeon's stable `HO…` film id → added / removed |
| `build.py` | Takes the two newest snapshots, runs the diff, renders `site/index.html` from `templates/index.html.j2` |
| `.github/workflows/update.yml` | Runs the above every Tuesday, commits the snapshot, publishes `site/` to GitHub Pages |

Why a real browser: Odeon is behind Cloudflare + Queue-it, so a plain HTTP
request gets bounced. Playwright loads the page like a person would.

## Local setup

Needs Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
python -m playwright install chromium
```

Then:

```bash
python scrape.py     # writes snapshots/<today>.json
python build.py       # writes site/index.html  (open it in a browser)
```

The first run has no previous week to compare against, so the diff is empty —
run it again next week (or drop a second dated file in `snapshots/`) to see it work.

## Publishing (GitHub Actions + Pages)

1. Push this repo to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. The workflow runs every Tuesday 19:00 UTC. Trigger it by hand any time from
   the **Actions** tab → *Weekly update* → *Run workflow*.

Each run commits that week's snapshot back to the repo (that's the baseline for
the following week) and redeploys the page.

## If GitHub's runner gets blocked

Cloudflare / Queue-it sometimes treat datacenter IPs harshly. If a run fails at
the scrape step with a timeout, switch to scraping on your own machine:

- Run `python scrape.py` locally on a schedule (Windows Task Scheduler, Tuesday
  evening), then `git add snapshots && git commit && git push`.
- Change the workflow to drop the `playwright install` and `python scrape.py`
  steps — it just runs `build.py` and deploys whatever snapshot you pushed.

## Tweaks

- **Run time:** edit the `cron:` line in `.github/workflows/update.yml`.
- **"Blocked" threshold:** `MIN_FILMS` in `scrape.py` (currently 30) guards
  against publishing an empty scrape as "everything removed".
- **Look:** everything visual is in `templates/index.html.j2` (inline CSS).
