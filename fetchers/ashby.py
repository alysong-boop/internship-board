"""Ashby: one call returns the whole public job board."""
from .base import posting, strip_html


def fetch(company, http, precheck, known):
    data = http.get(f"https://api.ashbyhq.com/posting-api/job-board/{company['board']}")
    out = []
    for j in data.get("jobs", []):
        desc = j.get("descriptionPlain") or strip_html(j.get("descriptionHtml"))
        out.append(posting(
            company, j["id"], j.get("title"), j.get("location", ""), j.get("jobUrl", ""),
            (j.get("publishedAt") or "")[:10] or None, desc,
            remote_hint=bool(j.get("isRemote")), _detail=True,
        ))
    return out
