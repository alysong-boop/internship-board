"""Lever: one call returns every posting with its description."""
from datetime import datetime, timezone

from .base import posting, strip_html


def fetch(company, http, precheck, known):
    data = http.get(f"https://api.lever.co/v0/postings/{company['company_id']}?mode=json")
    out = []
    for j in data:
        cats = j.get("categories") or {}
        desc = " ".join([j.get("descriptionPlain") or "", j.get("additionalPlain") or ""]
                        + [strip_html(x.get("content")) for x in j.get("lists") or []])
        ts = j.get("createdAt")
        posted = datetime.fromtimestamp(ts / 1000, timezone.utc).date().isoformat() if ts else None
        out.append(posting(
            company, j["id"], j.get("text"), cats.get("location", ""), j.get("hostedUrl", ""), posted, desc,
            country=j.get("country"), remote_hint=(j.get("workplaceType") == "remote"), _detail=True,
        ))
    return out
