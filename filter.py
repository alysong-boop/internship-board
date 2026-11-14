"""Decides which postings to keep, and labels term + eligibility. All word lists come from keywords.yaml."""
import re
from functools import lru_cache

SEASONS = "summer|fall|autumn|spring|winter"
US_STATES = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC "
             "ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC").split()
US_STATE_NAMES = ("alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|"
                  "idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|"
                  "minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|"
                  "new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|"
                  "south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|"
                  "wisconsin|wyoming")
_US_EXPLICIT = re.compile(r"united states|\bU\.S\.|(?<![A-Za-z])USA?(?![A-Za-z])")
_US_ABBR = re.compile(r"(?:,|-|/|\s)\s*(?:%s)(?![A-Za-z])" % "|".join(US_STATES))
_US_NAME = re.compile(r"\b(?:%s)\b" % US_STATE_NAMES, re.I)


@lru_cache(maxsize=None)
def _kw_regex(kw):
    kw = kw.strip()
    case_sensitive = kw.isalpha() and kw.isupper() and len(kw) <= 3
    body = re.escape(kw).replace(r"\-", r"[\s\-]?").replace(r"\ ", r"[\s\-/]+")
    plural = "s?" if kw[-1].isalpha() and not case_sensitive else ""
    return re.compile(r"(?<![A-Za-z0-9])%s%s(?![A-Za-z0-9])" % (body, plural), 0 if case_sensitive else re.I)


def hits(text, keywords):
    """Keywords (in config order) that appear in text."""
    return [k for k in keywords or [] if _kw_regex(k).search(text or "")]


def is_us(location, country=None, non_us_hints=()):
    if country:
        return country.strip().lower() in ("us", "usa", "united states", "united states of america")
    loc = location or ""
    if _US_EXPLICIT.search(loc):
        return True
    if any(re.search(r"\b%s\b" % re.escape(h), loc.lower()) for h in non_us_hints):
        return False
    return bool(_US_ABBR.search(loc) or _US_NAME.search(loc) or "remote" in loc.lower())


def _term_pairs(text):
    pairs = set()
    for season, year in re.findall(r"(%s)\W{0,3}(?:of\s+)?'?(20\d\d|\d\d)\b" % SEASONS, text):
        pairs.add((season, year if len(year) == 4 else "20" + year))
    for year, season in re.findall(r"\b(20\d\d)\W{0,3}(%s)" % SEASONS, text):
        pairs.add((season, year))
    return pairs


def parse_term(title, description, target="Summer 2027"):
    """Returns the target term, "unspecified", or "other" (clearly a different term)."""
    t_season, t_year = target.lower().split()
    tl = (title or "").lower()
    pairs = _term_pairs(tl)
    if pairs:
        return target if (t_season, t_year) in pairs else "other"
    years = set(re.findall(r"\b(20\d\d)\b", tl)) | {"20" + y for y in re.findall(r"'(\d\d)\b", tl)}
    seasons = set(re.findall(SEASONS, tl))
    # A start month in the title ("Jan. start", "July - Dec") counts as a season: only May-Aug starts are summer.
    months = re.findall(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", tl)
    if months and t_season == "summer":
        seasons.add("summer" if months[0] in ("may", "jun", "jul", "aug") else "other")
    if years:
        return target if t_year in years and (not seasons or t_season in seasons) else "other"
    if seasons and t_season not in seasons:
        return "other"
    pairs = _term_pairs((description or "").lower())
    if (t_season, t_year) in pairs:
        return target
    if any(season == t_season for season, _ in pairs):
        return "other"  # e.g. describes Summer 2026 and never mentions the target
    return "unspecified"


def parse_eligibility(text, cfg):
    """"rising junior OK" / "seniors only" / "unclear" for someone graduating in profile.grad_year."""
    grad_year = int(cfg.get("profile", {}).get("grad_year", 2029))
    elig = cfg.get("eligibility", {})
    t = (text or "").lower()
    years, open_ended = set(), False
    for m in re.finditer(r"graduat\w*|class of|degree completion|completion date", t):
        window = t[m.start(): m.end() + 90]
        found = [int(y) for y in re.findall(r"\b(20[2-3]\d)\b", window) if int(y) >= 2026]
        years.update(found)
        if found and re.search(r"or later|\bafter\b|or beyond|and beyond|and later|20\d\d\s*\+|\bbefore\b|prior to|no earlier than", window):
            open_ended = True
    # Explicit class-year wording beats graduation dates ("rising seniors ... graduating after Aug 2027").
    if hits(t, elig.get("ok_phrases")):
        return "rising junior OK"
    if hits(t, elig.get("seniors_phrases")):
        return "seniors only"
    if years:
        return "rising junior OK" if (max(years) >= grad_year or open_ended) else "seniors only"
    return "unclear"


def title_precheck(title, cfg):
    """Cheap title-only test. Returns a rejection reason, or None if the posting deserves a full look."""
    if not hits(title, cfg["internship_title"]):
        return "not an internship (title)"
    cleaned = title
    for phrase in cfg.get("exclude_exceptions") or []:
        cleaned = _kw_regex(phrase).sub(" ", cleaned)
    excluded = hits(cleaned, cfg.get("exclude_title"))
    if excluded:
        return f"excluded word in title: {excluded[0]}"
    if parse_term(title, "", cfg["profile"]["target_term"]) == "other":
        return "different term"
    return None


def evaluate(p, cfg):
    """Returns {"keep": bool, "reason": str, ...parsed fields when kept}."""
    title, desc = p.get("title", ""), p.get("description") or ""
    reason = title_precheck(title, cfg)
    if reason:
        return {"keep": False, "reason": reason}
    if not is_us(p.get("location"), p.get("country"), tuple(cfg.get("non_us_hints") or ())):
        return {"keep": False, "reason": "not US"}
    target = cfg["profile"]["target_term"]
    term = p.get("term_hint") or parse_term(title, desc, target)
    if term == "other":
        return {"keep": False, "reason": "different term"}
    if hits(desc, cfg.get("phd_only_phrases")) and not hits(desc, cfg.get("undergrad_words")):
        return {"keep": False, "reason": "PhD-only"}
    title_hits, desc_hits = hits(title, cfg["include"]), hits(desc, cfg["include"])
    if not title_hits and len(desc_hits) < int(cfg.get("description_min_hits", 1)):
        return {"keep": False, "reason": "no R&D keywords"}
    flag = parse_eligibility(f"{title}\n{desc}", cfg)
    loc = p.get("location", "")
    score = 3 * len(title_hits) + min(len(desc_hits), 5) + (1 if term == target else 0)
    score += {"rising junior OK": 2, "seniors only": -2}.get(flag, 0)
    return {
        "keep": True,
        "reason": "kept",
        "term": term,
        "eligibility_flag": flag,
        "remote": bool(p.get("remote_hint")) or "remote" in f"{title} {loc}".lower(),
        "matched": list(dict.fromkeys(title_hits + desc_hits))[:6],
        "score": score,
    }
