"""
Compare two snapshots and work out what was added / removed.

This is the "list checker": films keyed by Odeon's stable HO id.
  added   = in the new list, not in the old one
  removed = in the old list, not in the new one
"""


def _key(film):
    return film.get("id") or ("title:" + film.get("title", "").strip().lower())


def diff(old_films, new_films):
    old = {_key(f): f for f in old_films}
    new = {_key(f): f for f in new_films}

    added = [new[k] for k in new.keys() - old.keys()]
    removed = [old[k] for k in old.keys() - new.keys()]

    added.sort(key=lambda f: f["title"].lower())
    removed.sort(key=lambda f: f["title"].lower())
    return added, removed
