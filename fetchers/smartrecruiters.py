"""SmartRecruiters: list postings (US, search "intern"/"co-op"), then one detail call per candidate."""
from .base import posting, strip_html

API = "https://api.smartrecruiters.com/v1/companies"


def fetch(company, http, precheck, known):
    cid = company["company_id"]
    out, seen = [], set()
    for term in ("intern", "co-op"):
        offset = 0
        while True:
            data = http.get(f"{API}/{cid}/postings", params={"q": term, "country": "us", "limit": 100, "offset": offset})
            rows = data.get("content") or []
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                loc = row.get("location") or {}
                place = ", ".join(x for x in [loc.get("city"), (loc.get("region") or "").upper()] if x)
                p = posting(
                    company, row["id"], row.get("name"), place,
                    f"https://jobs.smartrecruiters.com/{cid}/{row['id']}", (row.get("releasedDate") or "")[:10] or None,
                    country=loc.get("country"), remote_hint=bool(loc.get("remote")),
                )
                if precheck(p["title"]) is None:
                    if p["job_id"] in known:
                        p["_known"] = True
                    else:
                        detail = http.get(f"{API}/{cid}/postings/{row['id']}")
                        sections = ((detail.get("jobAd") or {}).get("sections") or {}).values()
                        p["description"] = " ".join(strip_html(s.get("text")) for s in sections)
                        p["url"] = detail.get("postingUrl") or p["url"]
                        p["_detail"] = True
                out.append(p)
            offset += 100
            if not rows or offset >= (data.get("totalFound") or 0):
                break
    return out
