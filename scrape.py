"""
Scrape the set of films Odeon currently has pages for, from their sitemap,
and resolve a poster for each.

Why the sitemap and not the /films/ page:
  - /films/ is behind Cloudflare's bot challenge, and it builds its list with
    JavaScript, so a plain download gets an empty shell.
  - sitemap.xml is plain XML and isn't challenged when we present a real
    browser's TLS fingerprint (curl_cffi's `impersonate`). It lists every
    /films/<slug>/HO<id>/ page - the authoritative "these are the films" set.

Posters:
  - First choice: Odeon's own poster endpoint, keyed by the HO id (~96% hit).
  - Fallback: TMDB search by title, if a TMDB key is available (env var
    TMDB_API_KEY, or a `tmdb-key.txt` file next to this script). Optional - with
    no key we just leave those films posterless and the page shows a colour tile.

Output: snapshots/YYYY-MM-DD.json   (date = today, UK time)
"""

import datetime
import json
import os
import pathlib
import re
import sys
import time
import zoneinfo
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests

HERE = pathlib.Path(__file__).parent
SITEMAP = "https://www.odeon.co.uk/sitemap.xml"
ODEON_POSTER = "https://vwc.odeon.co.uk/CDN/media/entity/get/FilmPosterGraphic/{id}?width=400"
TMDB_SEARCH = "https://api.themoviedb.org/3/search/movie"
TMDB_IMG = "https://image.tmdb.org/t/p/w500{path}"
SNAP_DIR = HERE / "snapshots"
UK = zoneinfo.ZoneInfo("Europe/London")

# Refuse to write a snapshot with fewer than this - a near-empty scrape would
# otherwise look like "almost everything was removed this week".
MIN_FILMS = 30

FILM_LOC = re.compile(
    r"<loc>\s*(https://www\.odeon\.co\.uk/films/([a-z0-9-]+)/(HO\d+)/)\s*</loc>",
    re.IGNORECASE,
)

# Words we don't capitalise mid-title.
_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "from",
          "in", "of", "on", "or", "the", "to", "vs", "with"}

# Tokens on slug-titles that hurt a TMDB search: languages, formats, event tags.
_TMDB_STRIP = {"dubbed", "subbed", "sub", "dub", "malayalam", "tamil", "telugu",
               "hindi", "punjabi", "bengali", "korean", "japanese",
               "imax", "4dx", "3d", "2d", "70mm", "35mm", "vistavision",
               "encore", "rerelease", "re", "release", "remastered", "restored",
               "presented", "in", "the", "screening", "preview", "marathon",
               "unlimited", "anniversary", "sing", "along", "singalong"}


def title_from_slug(slug: str) -> str:
    """Best-effort readable title from a URL slug. Imperfect by nature -
    the slug has already lost '&', apostrophes, brackets etc."""
    words = [w for w in slug.split("-") if w]
    out: list[str] = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw == "s" and out:                      # "woolf-s-night" -> "Woolf's Night"
            out[-1] += "'s"
        elif i != 0 and lw in _SMALL:
            out.append(lw)
        elif re.fullmatch(r"\d+[a-z]{1,3}", lw):    # 70mm, 3d, 4dx, 2d
            out.append(lw.upper())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def fetch_sitemap() -> str:
    """Fetch the sitemap, trying a few browser fingerprints. Run this from a
    home / residential connection - Cloudflare 403s datacenter IPs (incl.
    GitHub Actions runners) whatever fingerprint we present."""
    last = "no attempt made"
    for attempt, imp in enumerate(("chrome131", "chrome124", "edge101")):
        try:
            r = requests.get(
                SITEMAP,
                impersonate=imp,
                timeout=45,
                headers={"Referer": "https://www.odeon.co.uk/"},
            )
            if r.status_code == 200 and "<loc>" in r.text:
                return r.text
            last = f"HTTP {r.status_code} ({len(r.text)} bytes)"
        except Exception as exc:  # noqa: BLE001
            last = repr(exc)
        if attempt < 2:
            time.sleep(4)
    raise RuntimeError(f"sitemap fetch failed after 3 tries - last: {last}")


def parse(xml: str):
    seen: dict[str, dict] = {}
    for m in FILM_LOC.finditer(xml):
        url, slug, film_id = m.group(1), m.group(2), m.group(3)
        seen.setdefault(film_id, {
            "id": film_id,
            "slug": slug,
            "title": title_from_slug(slug),
            "url": url,
            "poster": ODEON_POSTER.format(id=film_id),
            "poster_source": "odeon",
        })
    return sorted(seen.values(), key=lambda f: f["title"].lower())


# ---------------------------------------------------------------- posters

def _tmdb_key() -> str | None:
    key = os.environ.get("TMDB_API_KEY", "").strip()
    if key:
        return key
    f = HERE / "tmdb-key.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip() or None
    return None


def _odeon_has_poster(session, url: str) -> bool:
    try:
        r = session.get(url.replace("width=400", "width=92"), timeout=15)
        return r.status_code == 200 and r.headers.get("content-type", "").startswith("image")
    except Exception:  # noqa: BLE001
        return False


def _tmdb_poster(session, title: str, key: str) -> str | None:
    for query in (title, " ".join(
            w for w in title.split() if w.lower().strip("()") not in _TMDB_STRIP)):
        if not query:
            continue
        try:
            r = session.get(TMDB_SEARCH, timeout=15, params={
                "api_key": key, "query": query, "include_adult": "false"})
            for res in r.json().get("results", []):
                if res.get("poster_path"):
                    return TMDB_IMG.format(path=res["poster_path"])
        except Exception:  # noqa: BLE001
            return None
        if query == title:
            time.sleep(0.3)
    return None


def resolve_posters(films: list[dict]) -> None:
    """Verify each Odeon poster; for the misses, try TMDB (if a key is set)."""
    s = requests.Session(impersonate="chrome131",
                         headers={"Referer": "https://www.odeon.co.uk/"})
    with ThreadPoolExecutor(max_workers=8) as ex:
        ok = list(ex.map(lambda f: _odeon_has_poster(s, f["poster"]), films))

    missing = [f for f, good in zip(films, ok) if not good]
    for f, good in zip(films, ok):
        if not good:
            f["poster"] = None
            f["poster_source"] = None

    key = _tmdb_key()
    if not missing:
        print("posters: all from Odeon")
        return
    if not key:
        print(f"posters: {len(films) - len(missing)} from Odeon, "
              f"{len(missing)} missing (no TMDB key - set TMDB_API_KEY or add tmdb-key.txt)")
        return

    ts = requests.Session()
    found = 0
    for f in missing:
        p = _tmdb_poster(ts, f["title"], key)
        if p:
            f["poster"] = p
            f["poster_source"] = "tmdb"
            found += 1
    print(f"posters: {len(films) - len(missing)} from Odeon, "
          f"{found} from TMDB, {len(missing) - found} still missing")


# ---------------------------------------------------------------- main

def main():
    try:
        films = parse(fetch_sitemap())
    except Exception as exc:  # noqa: BLE001 - any failure should be loud
        print(f"scrape failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if len(films) < MIN_FILMS:
        print(
            f"only {len(films)} films found (< {MIN_FILMS}); not writing a snapshot",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        resolve_posters(films)
    except Exception as exc:  # noqa: BLE001 - posters are cosmetic, never fail the run
        print(f"poster resolution had a problem (continuing): {exc}", file=sys.stderr)

    today = datetime.datetime.now(UK).date().isoformat()
    SNAP_DIR.mkdir(exist_ok=True)
    out = SNAP_DIR / f"{today}.json"
    out.write_text(
        json.dumps(
            {
                "scraped_at": datetime.datetime.now(UK).isoformat(),
                "source": SITEMAP,
                "count": len(films),
                "films": films,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {out.name}: {len(films)} films")


if __name__ == "__main__":
    main()
