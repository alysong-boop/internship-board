"""Shared HTTP helper: real User-Agent, small delay between calls, retries with backoff."""
import html
import re
import time

import requests

USER_AGENT = "internship-board/1.0 (personal student job tracker; python-requests)"


class FetchError(Exception):
    pass


class Http:
    def __init__(self, delay=0.35, retries=3, timeout=30):
        self.delay, self.retries, self.timeout = delay, retries, timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    def request(self, method, url, **kw):
        last = None
        for attempt in range(self.retries):
            time.sleep(self.delay if attempt == 0 else 1.5 * 2 ** attempt)
            try:
                r = self.session.request(method, url, timeout=self.timeout, **kw)
            except requests.RequestException as e:
                last = f"{type(e).__name__}"
                continue
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    raise FetchError(f"non-JSON response from {url}")
            last = f"HTTP {r.status_code}"
            if r.status_code != 429 and r.status_code < 500:
                break  # a 4xx will not get better by retrying
        raise FetchError(f"{last} from {url}")

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


def strip_html(s):
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", s, flags=re.I)
    # Inline tags vanish (Workday often splits "2027" into "202<span>7</span>"); other tags become a space.
    s = re.sub(r"</?(span|b|i|u|em|strong|font|a|sup|sub)\b[^>]*>", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(s)).strip()


def posting(company, job_id, title, location="", url="", posted=None, description="", **extra):
    """The common shape every fetcher returns."""
    p = {
        "company": company["name"],
        "industry": company.get("industry", "adjacent"),
        "source": company.get("ats", ""),
        "job_id": str(job_id),
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "url": url,
        "posted": posted,
        "description": description,
    }
    p.update(extra)
    return p
