"""Fetch every source -> filter -> merge into data/postings.json -> rebuild the site.

  python main.py              normal run (writes data/, docs/data.json, .run/summary.json)
  python main.py --dry-run    print what would be kept / filtered; writes nothing, emails nothing
  python main.py --refresh    ignore the cache and re-read every posting's description
  python main.py --only "Eli Lilly" --dry-run     test a single company
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

import build_site
import merge
import notify
from fetchers import FETCHERS, simplify
from fetchers.base import Http
from filter import evaluate, title_precheck

ROOT = Path(__file__).parent
REJECTS = ROOT / "data" / "rejected.json"   # cache of postings already read and rejected (also handy for tuning)
SUMMARY = ROOT / ".run" / "summary.json"


def load_rejects(config_hash, refresh):
    """Returns (cached rejects, use_cache). The cache is ignored when keywords.yaml has changed."""
    if refresh:
        return {}, False
    if not REJECTS.exists():
        return {}, True
    data = json.loads(REJECTS.read_text())
    if data.get("config_hash") != config_hash:
        return {}, False
    return data.get("items", {}), True


def run_feed(name, fn):
    try:
        return name, fn(), None
    except Exception as e:  # one bad source must never stop the run
        return name, [], f"{name}: {e}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--only", help="run a single company (name as in companies.yaml)")
    args = ap.parse_args()

    kw_text = (ROOT / "keywords.yaml").read_text()
    cfg = yaml.safe_load(kw_text)
    sources = yaml.safe_load((ROOT / "companies.yaml").read_text())
    companies = sources["companies"]
    config_hash = hashlib.sha256(kw_text.encode()).hexdigest()[:12]
    now = datetime.now(ZoneInfo("America/New_York"))
    today = now.date().isoformat()

    store = merge.load()
    stored = {p["id"]: p for p in store["postings"]}
    old_rejects, use_cache = load_rejects(config_hash, args.refresh)
    stored_known = stored if use_cache else {}   # keywords changed or --refresh: re-evaluate everything
    known = defaultdict(set)
    for key in list(stored_known) + list(old_rejects):
        company, _, job_id = key.partition("::")
        known[company].add(job_id)

    precheck = lambda title: title_precheck(title, cfg)
    feeds = {}
    for c in companies:
        if c.get("ats") in FETCHERS and (not args.only or c["name"] == args.only):
            feeds[c["name"]] = (lambda c=c: FETCHERS[c["ats"]](c, Http(), precheck, known[c["name"]]))
    simp = (sources.get("supplementary") or {}).get("simplifyjobs")
    if simp and not args.only:
        feeds[simplify.FEED_NAME] = lambda: simplify.fetch(
            simp, Http(), companies, cfg.get("simplify_only_listed_companies", True), cfg["profile"]["target_term"])

    print(f"Fetching {len(feeds)} sources...", flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda kv: run_feed(*kv), feeds.items()))

    kept, filtered, still_seen, rejects, failed, feeds_ok = [], [], set(), {}, [], set()
    per_feed = {}
    for name, postings, error in results:
        if error:
            failed.append(error)
            print(f"  FAILED  {error}", flush=True)
            continue
        feeds_ok.add(name)
        n_kept = 0
        for p in postings:
            p["feed"] = name
            key = merge.key_of(p)
            if p.get("_known"):
                if key in stored_known:
                    still_seen.add(key)
                    n_kept += 1
                elif key in old_rejects:
                    rejects[key] = old_rejects[key]
                continue
            res = evaluate(p, cfg)
            if res["keep"]:
                kept.append({**p, **res})
                n_kept += 1
            else:
                filtered.append((p, res["reason"]))
                if p.get("_detail") and res["reason"] != "not an internship (title)":
                    rejects[key] = {"company": p["company"], "title": p["title"], "location": p["location"],
                                    "reason": res["reason"], "url": p["url"]}
        per_feed[name] = (len(postings), n_kept)

    new_store, new = merge.merge(store, kept, still_seen, feeds_ok, today)
    new_store["updated"] = now.isoformat(timespec="minutes")
    open_now = [p for p in new_store["postings"] if p["status"] == "open"]
    summary = {"date": today, "new": new, "failed": failed}

    print(f"\n{len(feeds_ok)} sources OK, {len(failed)} failed. "
          f"{len(open_now)} open postings ({len(new)} new today).")
    if args.dry_run:
        report(kept, filtered, per_feed, failed)
        if new:
            subject, text, _ = notify.compose(summary, "https://<you>.github.io/<repo>/")
            print("\n=== EMAIL PREVIEW (not sent) ===\nSubject: " + subject + "\n" + text[:1500])
        print("\nDry run: nothing written, nothing emailed.")
        return 0

    merge.save(new_store)
    REJECTS.write_text(json.dumps({"config_hash": config_hash, "items": rejects}, indent=1, ensure_ascii=False) + "\n")
    build_site.build(new_store, companies, failed)
    SUMMARY.parent.mkdir(exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=1))
    print("Wrote data/postings.json, data/rejected.json, docs/data.json")
    return 0


def report(kept, filtered, per_feed, failed):
    print("\n=== PER SOURCE (fetched -> kept) ===")
    for name, (n, k) in sorted(per_feed.items()):
        print(f"  {name:42} {n:5} -> {k}")
    print(f"\n=== KEPT ({len(kept)}) ===")
    for p in sorted(kept, key=lambda p: (-p["score"], p["company"])):
        print(f"  [{p['score']:2}] {p['company'][:18]:18} | {p['title'][:62]:62} | {p['location'][:28]:28} | "
              f"{p['term']:11} | {p['eligibility_flag']:16} | {', '.join(p['matched'][:3])}")
    print(f"\n=== FILTERED OUT ({len(filtered)}) ===")
    reasons = Counter(r for _, r in filtered)
    for reason, n in reasons.most_common():
        print(f"\n  {reason}: {n}")
        examples = [p for p, r in filtered if r == reason]
        for p in examples[:: max(1, len(examples) // 8)][:8]:
            print(f"      {p['company'][:18]:18} | {p['title'][:70]:70} | {p['location'][:30]}")
    if failed:
        print("\n=== FAILED SOURCES ===")
        for f in failed:
            print("  " + f)


if __name__ == "__main__":
    sys.exit(main())
