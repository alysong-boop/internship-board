"""Greenhouse: one call returns every job with its description."""
from .base import posting, strip_html


def fetch(company, http, precheck, known):
    data = http.get(f"https://boards-api.greenhouse.io/v1/boards/{company['token']}/jobs?content=true")
    out = []
    for j in data.get("jobs", []):
        out.append(posting(
            company, j["id"], j.get("title"), (j.get("location") or {}).get("name", ""),
            j.get("absolute_url", ""), (j.get("first_published") or j.get("updated_at") or "")[:10] or None,
            strip_html(j.get("content")), _detail=True,
        ))
    return out
