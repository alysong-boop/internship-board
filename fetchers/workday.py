"""Workday: POST /wday/cxs/{tenant}/{site}/jobs (search), GET the same base + externalPath (detail)."""
from .base import posting, strip_html

PAGE = 20           # Workday's maximum page size
MAX_RESULTS = 2000  # safety cap per search
SEARCHES = ("intern", "co-op")


def fetch(company, http, precheck, known):
    tenant, dc = company["tenant"], company["dc"]
    sites = company.get("sites") or [company["site"]]
    host = f"https://{tenant}.{dc}.myworkdayjobs.com"
    out, seen = [], set()
    for site in sites:
        api = f"{host}/wday/cxs/{tenant}/{site}"
        for term in SEARCHES:
            offset, total, dry_pages = 0, None, 0
            while True:
                body = {"appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": term}
                data = http.post(f"{api}/jobs", json=body)
                rows = data.get("jobPostings") or []
                if total is None:
                    total = data.get("total") or 0  # only reliable on the first page
                page_had_match = False
                for row in rows:
                    path = row.get("externalPath")
                    if not path or path in seen:
                        continue
                    seen.add(path)
                    title = row.get("title", "")
                    job_id = (row.get("bulletFields") or [path.rsplit("_", 1)[-1]])[0]
                    p = posting(company, job_id, title, row.get("locationsText", ""), f"{host}/{site}{path}")
                    if precheck(title) is None:
                        page_had_match = True
                        if str(job_id) in known:
                            p["_known"] = True  # already classified on an earlier run
                        else:
                            _add_detail(p, http.get(f"{api}{path}").get("jobPostingInfo") or {})
                    out.append(p)
                offset += PAGE
                dry_pages = 0 if page_had_match else dry_pages + 1
                # Results are relevance-sorted, so 3 pages without a single internship title means we are done.
                if not rows or offset >= total or offset >= MAX_RESULTS or dry_pages >= 3:
                    break
    return out


def _add_detail(p, info):
    locs = [info.get("location")] + list(info.get("additionalLocations") or [])
    locs = [x for x in locs if x]
    if locs:
        p["location"] = "; ".join(dict.fromkeys(locs))
    p["country"] = (info.get("country") or {}).get("descriptor")
    p["posted"] = info.get("startDate")
    p["description"] = strip_html(info.get("jobDescription"))
    p["remote_hint"] = "remote" in (info.get("remoteType") or "").lower()
    p["_detail"] = True
