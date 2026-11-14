"""Merges today's kept postings into the master list (data/postings.json). Nothing is ever deleted."""
import json
import re
from pathlib import Path

STORE = Path(__file__).parent / "data" / "postings.json"
FIELDS = ("company", "title", "industry", "location", "remote", "url", "posted", "term",
          "eligibility_flag", "source", "feed", "matched", "score")


def key_of(p):
    return f"{p['company']}::{p['job_id']}"


def _fallback(p):
    norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    return (p["company"], norm(p["title"]), norm(p["location"]))


def load(path=STORE):
    if Path(path).exists():
        return json.loads(Path(path).read_text())
    return {"updated": None, "postings": []}


def save(store, path=STORE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(store, indent=1, ensure_ascii=False) + "\n")


def merge(store, kept, still_seen_keys, feeds_ok, today):
    """
    kept            freshly evaluated postings that passed the filter
    still_seen_keys keys of stored postings the source still lists (not re-evaluated today)
    feeds_ok        feed names that were fetched successfully; only their postings can be closed
    Returns (new_store, list_of_new_postings).
    """
    by_key = {p["id"]: p for p in store.get("postings", [])}
    by_fallback = {_fallback(p): p for p in by_key.values()}
    seen, new = set(still_seen_keys), []
    for k in kept:
        key = key_of(k)
        rec = by_key.get(key) or by_fallback.get(_fallback(k))
        if rec is None:
            rec = {"id": key, "job_id": k["job_id"], "first_seen": today}
            new.append(rec)
        elif rec["id"] != key:  # same posting, re-listed under a new ATS id
            by_key.pop(rec["id"], None)
            rec["id"], rec["job_id"] = key, k["job_id"]
        rec.update({f: k.get(f) for f in FIELDS})
        by_key[key] = rec
        seen.add(key)
    for key, rec in by_key.items():
        if key in seen:
            rec["last_seen"], rec["status"] = today, "open"
        elif rec.get("status") != "closed" and rec.get("feed") in feeds_ok:
            rec["status"] = "closed"  # gone from its source; last_seen keeps the last day it was listed
    postings = sorted(by_key.values(), key=lambda r: (r["first_seen"], r.get("score") or 0), reverse=True)
    return {"updated": store.get("updated"), "postings": postings}, new
