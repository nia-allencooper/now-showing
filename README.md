# Now Showing

A weekly diff of every film Odeon has a page for. Each Tuesday evening it reads
Odeon's sitemap, saves the list, compares it with last week's, and publishes a
page showing what was **added** and what was **removed** — plus an **In Theaters**
grid of everything currently listed. Every title links back to its Odeon page.

## How it fits together

| Piece | Job |
| --- | --- |
| `scrape.py` | Fetches `odeon.co.uk/sitemap.xml` with `curl_cffi` (browser TLS fingerprint), pulls every `/films/<slug>/HO<id>/` entry → `snapshots/<that-week's-Tuesday>.json` |
| `diff.py` | Compares two snapshots by Odeon's stable `HO…` id → added / removed |
| `build.py` | Two newest snapshots → diff → renders `site/index.html` from `templates/index.html.j2` |
| `run-weekly.bat` | Runs the three above and `git push`es the result. Windows Task Scheduler fires it weekly. |
| `.github/workflows/update.yml` | On each push that touches `site/`, publishes `site/` to GitHub Pages |

### Why the scrape runs on a home PC, not in the cloud

`odeon.co.uk` is behind Cloudflare, which **403s datacenter IPs** — including
GitHub Actions runners — no matter what fingerprint we send. From a normal home
connection `curl_cffi` gets through fine. So the scrape + build happen on your
machine; GitHub only publishes the page.

### What the sitemap gives us

Film IDs, URLs, and slug-derived titles. Titles are approximate — the slug has
already lost `&`, apostrophes and brackets (`arrietty-dubbed` → "Arrietty
Dubbed"). No age ratings, no now-showing vs coming-soon split.

### Posters

`scrape.py` resolves a poster per film:

1. Odeon's own poster endpoint, keyed by the `HO` id (covers ~96%).
2. For the rest, a **TMDB** search by title — *optional*, needs a free key.

Without a TMDB key those ~7 films just show a coloured tile with the title.
To enable the fallback: get a key at
<https://www.themoviedb.org/settings/api> (the **API Key (v3 auth)** value),
then either set an environment variable `TMDB_API_KEY`, or save the key in a file
`tmdb-key.txt` next to `scrape.py` (git-ignored).

## One-time setup

### 1. Local environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Test it: `python scrape.py` then `python build.py`, open `site/index.html`.

Snapshots are named after **the Tuesday of the week they belong to**, not the day
the scraper ran — so running it several times mid-week just overwrites that
week's file. The added/removed diff only advances from one Tuesday to the next,
never because a build happened on some other day.

### 2. GitHub

Repo is already pushed. In **Settings → Pages**, set **Source: GitHub Actions**
(needs a public repo on the free plan). The page will be at
`https://<you>.github.io/now-showing/`.

### 3. Windows Task Scheduler

- Task Scheduler → **Create Basic Task** → name it "Now Showing".
- Trigger: **Weekly**, **Tuesday**, start time ~20:00.
- Action: **Start a program** → Program/script: the full path to `run-weekly.bat`
  → "Start in": this project folder.
- After creating, open the task's **Properties**:
  - **Run only when user is logged on** (so it uses your saved Git credentials).
  - **Settings** tab → tick **Run task as soon as possible after a scheduled
    start is missed** (covers the PC being off/asleep on Tuesday).

Run the task once by hand (right-click → Run) to confirm it works.

## Your marks (watchlist / booked / seen / skip)

Each poster has a mark control; the filter bar above the grid narrows to one
kind. Marks are stored in the browser's `localStorage`, keyed by Odeon's `HO`
id, so they survive the weekly rebuild.

### Cross-device sync (optional, free)

Off by default (per-browser). To turn it on, follow the steps at the top of
[`apps-script.gs`](apps-script.gs): make a Google Sheet, paste that script into
its Apps Script editor, deploy it as a web app, and put the resulting `/exec`
URL in a file `sync-url.txt` in this folder. Next build bakes it in and the page
gains a **Sync** button.

[`appsscript.json`](appsscript.json) is the manifest to paste into the Apps
Script editor so the auth prompt asks for *this one spreadsheet* instead of all
of them (see the note in `apps-script.gs`).

- `sync-url.txt` is git-ignored (local config); the URL still ends up in the
  built `site/index.html`, which is fine — access control is the secret link,
  not the URL.
- Model: one JSON blob per secret key, newest write wins. Good for one person on
  two devices; not built for many people editing the same list at once.
- No key set = no sync, page works exactly as before.

## Adding posters / exact titles later

Needs the rendered `/films/` page (Cloudflare + JavaScript), via either a paid
unblocker's free tier (one request a week) or a real browser on the PC. Either
way it's an enrichment step mapping each `HO…` id to a poster + real title.

## Tweaks

- **Run time:** the Task Scheduler trigger.
- **"Blocked" guard:** `MIN_FILMS` in `scrape.py` (30) — stops an empty fetch
  being published as "almost everything removed".
- **Look:** all visual, in `templates/index.html.j2` (inline CSS).
