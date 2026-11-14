"""SimplifyJobs community list (supplementary). No descriptions, so only titles are filtered.

Used for companies in companies.yaml that have no direct feed; companies with a working
feed are skipped here so postings are not listed twice.
"""
import re
from datetime import datetime, timezone

from .base import posting

FEED_NAME = "SimplifyJobs list"


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch(source, http, companies, only_listed, target_term):
    data = http.get(source["url"])
    lookup = {}
    for c in companies:
        for name in [c["name"]] + list(c.get("aliases") or []):
            lookup[_norm(name)] = c
    out = []
    for j in data:
        if not j.get("active") or not j.get("is_visible", True):
            continue
        if target_term not in (j.get("terms") or []):
            continue
        company = lookup.get(_norm(j.get("company_name")))
        if company and company.get("ats") != "manual":
            continue  # already covered by its own feed
        if not company:
            if only_listed:
                continue
            company = {"name": j.get("company_name", "?"), "industry": "adjacent"}
        ts = j.get("date_posted")
        posted = datetime.fromtimestamp(ts, timezone.utc).date().isoformat() if ts else None
        p = posting(company, j["id"], j.get("title"), "; ".join(j.get("locations") or []), j.get("url", ""), posted,
                    term_hint=target_term, _detail=True)
        p["source"] = "simplify"
        out.append(p)
    return out
