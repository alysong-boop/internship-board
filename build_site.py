"""Rebuilds docs/data.json, the single file the static board (docs/index.html) reads."""
import json
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
OUT = ROOT / "docs" / "data.json"


def build(store, companies, failed=()):
    open_posts = [p for p in store["postings"] if p.get("status") == "open"]
    manual = [
        {"name": c["name"], "industry": c.get("industry"), "url": c.get("careers_url"), "note": c.get("note", "")}
        for c in companies if c.get("ats") == "manual"
    ]
    data = {
        "updated": store.get("updated"),
        "counts": dict(Counter(p["industry"] for p in open_posts)),
        "postings": store["postings"],
        "manual": manual,
        "failed": sorted(failed),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False) + "\n")
    return data


if __name__ == "__main__":
    import merge
    cfg = yaml.safe_load((ROOT / "companies.yaml").read_text())
    build(merge.load(), cfg["companies"])
    print(f"wrote {OUT}")
