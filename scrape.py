"""
Scrape the set of films Odeon currently has pages for, from their sitemap.

Why the sitemap and not the /films/ page:
  - /films/ is behind Cloudflare's bot challenge, and it builds its list with
    JavaScript, so a plain download gets an empty shell.
  - sitemap.xml is plain XML and isn't challenged when we present a real
    browser's TLS fingerprint (curl_cffi's `impersonate`). It lists every
    /films/<slug>/HO<id>/ page - the authoritative "these are the films" set.

What this gives us:  id, slug, url, and a title derived from the slug.
What it does NOT:     posters, age ratings, now-showing vs coming-soon.

Output: snapshots/YYYY-MM-DD.json   (date = today, UK time)
"""

import datetime
import json
import pathlib
import re
import sys
import time
import zoneinfo

from curl_cffi import requests

SITEMAP = "https://www.odeon.co.uk/sitemap.xml"
# Poster endpoint, keyed by the HO film id - open, no auth, not Cloudflare-gated.
POSTER = "https://vwc.odeon.co.uk/CDN/media/entity/get/FilmPosterGraphic/{id}?width=400"
SNAP_DIR = pathlib.Path(__file__).parent / "snapshots"
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
            "poster": POSTER.format(id=film_id),
        })
    return sorted(seen.values(), key=lambda f: f["title"].lower())


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
