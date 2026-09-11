"""
Build site/index.html from the two most recent snapshots.

  - newest snapshot        -> "films listed" + the "now" side of the diff
  - second-newest snapshot -> the "last week" baseline
  - first ever run         -> no baseline, so no added/removed yet

Run:  python build.py
"""

import datetime
import json
import pathlib
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape

from diff import diff

ROOT = pathlib.Path(__file__).parent
SNAP_DIR = ROOT / "snapshots"
SITE_DIR = ROOT / "site"
TEMPLATES = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"

# Favicon / installed-app icon - not shown in the page itself.
ASSET_FILES = [
    "icon.svg", "favicon-32.png", "favicon-16.png",
    "icon-192.png", "icon-512.png", "apple-touch-icon.png",
    "manifest.webmanifest",
]

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def date_label(d: datetime.date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def hue(s: str) -> int:
    """Stable 0-359 hue from a title (mirrors the mock's colouring)."""
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) % 360
    return h


def decorate(films):
    out = []
    for f in films:
        g = dict(f)
        g["hue"] = hue(f.get("title", ""))
        out.append(g)
    return out


def load(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


RELEASE_FILE = ROOT / "release-dates.json"


def load_release_dates() -> dict:
    if not RELEASE_FILE.exists():
        return {}
    try:
        return json.loads(RELEASE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def prune_release_dates(dates: dict, current_ids: set) -> dict:
    """A release date is entered by hand once and kept as long as the film
    stays listed - it isn't tied to the weekly scrape. Drop it only when the
    film itself falls off Odeon's list."""
    pruned = {k: v for k, v in dates.items() if k in current_ids}
    if pruned != dates:
        RELEASE_FILE.write_text(
            json.dumps(pruned, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )
    return pruned


def main():
    snaps = sorted(SNAP_DIR.glob("20*.json"))
    if not snaps:
        raise SystemExit("no snapshots yet - run scrape.py first")

    latest_path = snaps[-1]
    latest = load(latest_path)
    latest_date = datetime.date.fromisoformat(latest_path.stem)

    release_dates = prune_release_dates(
        load_release_dates(), {f["id"] for f in latest["films"]}
    )
    for f in latest["films"]:
        entry = release_dates.get(f["id"])
        f["release_label"] = entry.get("label") if entry else None
        f["release_iso"] = entry.get("iso") if entry else None

    prev_path = snaps[-2] if len(snaps) > 1 else None
    if prev_path:
        prev = load(prev_path)
        prev_date = datetime.date.fromisoformat(prev_path.stem)
        added, removed = diff(prev["films"], latest["films"])
        prev_label = date_label(prev_date)
    else:
        added, removed = [], []
        prev_label = None

    # Optional cross-device sync backend (Google Apps Script web-app URL).
    sync_file = ROOT / "sync-url.txt"
    sync_url = ""
    if sync_file.exists():
        for line in sync_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                sync_url = line
                break

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    html = env.get_template("index.html.j2").render(
        total=latest["count"],
        films=decorate(sorted(latest["films"], key=lambda f: f["title"].lower())),
        added=decorate(added),
        removed=decorate(removed),
        this_label=date_label(latest_date),
        prev_label=prev_label,
        is_first_run=prev_path is None,
        sync_url=sync_url,
    )

    SITE_DIR.mkdir(exist_ok=True)
    for name in ASSET_FILES:
        src = ASSETS_DIR / name
        if src.exists():
            shutil.copyfile(src, SITE_DIR / name)
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (SITE_DIR / "latest.json").write_text(
        json.dumps(
            {
                "this": latest_path.stem,
                "previous": prev_path.stem if prev_path else None,
                "total": latest["count"],
                "added": added,
                "removed": removed,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"built site/index.html - {latest['count']} listed, "
        f"+{len(added)} / -{len(removed)}"
        + ("" if prev_path else "  (first run, no baseline)")
    )


if __name__ == "__main__":
    main()
