"""Run with:  python -m unittest discover -s tests"""
import json
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from filter import evaluate, hits, is_us, parse_eligibility, parse_term  # noqa: E402
import merge  # noqa: E402

CFG = yaml.safe_load((ROOT / "keywords.yaml").read_text())
FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "postings.json").read_text())


class FilterFixtures(unittest.TestCase):
    def test_fixtures(self):
        for fx in FIXTURES:
            with self.subTest(fx["name"]):
                result = evaluate(fx["posting"], CFG)
                for field, expected in fx["expect"].items():
                    self.assertEqual(result.get(field), expected, f"{fx['name']}: {field}")


class Keywords(unittest.TestCase):
    def test_whole_words(self):
        self.assertEqual(hits("Internal Audit Lead", ["intern"]), [])
        self.assertEqual(hits("Summer Interns - R&D", ["intern", "R&D"]), ["intern", "R&D"])
        self.assertEqual(hits("Co-Op, Process Engineering", ["co-op"]), ["co-op"])
        self.assertEqual(hits("Coop student", ["co-op"]), ["co-op"])

    def test_short_caps_are_case_sensitive(self):
        self.assertEqual(hits("Make it happen intern", ["IT"]), [])
        self.assertEqual(hits("IT Intern", ["IT"]), ["IT"])


class Eligibility(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(parse_eligibility(text, CFG), expected, text)

    def test_ok(self):
        self.check("Open to rising juniors and seniors", "rising junior OK")
        self.check("Must have completed sophomore year", "rising junior OK")
        self.check("Expected graduation between December 2028 and June 2029", "rising junior OK")
        self.check("Graduating in May 2028 or later", "rising junior OK")
        self.check("Must be enrolled in an advanced degree program if graduating before May 2027", "rising junior OK")

    def test_seniors_only(self):
        self.check("Must be a rising senior", "seniors only")
        self.check("Anticipated graduation date of December 2027 - May 2028", "seniors only")
        self.check("Juniors and seniors pursuing a BS in engineering", "seniors only")
        self.check("Rising seniors and master's students. Expected graduation date after August 2027.", "seniors only")

    def test_split_digits_in_html(self):
        from fetchers.base import strip_html
        text = strip_html("<p>graduation date between December 202<span>7</span> and May 202<b>9</b>.</p><p>Next</p>")
        self.assertIn("December 2027 and May 2029.", text)
        self.check(text, "rising junior OK")

    def test_unclear(self):
        self.check("Currently enrolled in a bachelor's program. The company was founded in 2030.", "unclear")


class Terms(unittest.TestCase):
    def test_terms(self):
        self.assertEqual(parse_term("Summer 2027 R&D Intern", ""), "Summer 2027")
        self.assertEqual(parse_term("Internship '27: R&D", ""), "Summer 2027")
        self.assertEqual(parse_term("2026 Summer Intern", ""), "other")
        self.assertEqual(parse_term("Fall Co-op, Process Development", ""), "other")
        self.assertEqual(parse_term("2027 Co-Op: R&D Packaging (6 months, Jan. start)", ""), "other")
        self.assertEqual(parse_term("2027 Analytical Development Co-Op (June - Dec)", ""), "Summer 2027")
        self.assertEqual(parse_term("R&D Intern", "This is a 12-week Summer 2027 internship."), "Summer 2027")
        self.assertEqual(parse_term("R&D Intern", "Our summer 2026 program runs May to August."), "other")
        self.assertEqual(parse_term("R&D Intern", "Join us."), "unspecified")


class Locations(unittest.TestCase):
    def test_us(self):
        for loc in ["Cambridge, MA", "US - Illinois - Chicago", "Remote", "United States - Remote", "Rahway, New Jersey"]:
            self.assertTrue(is_us(loc, None, tuple(CFG["non_us_hints"])), loc)
        for loc in ["Toronto, Canada", "Basel", "Dublin, Ireland"]:
            self.assertFalse(is_us(loc, None, tuple(CFG["non_us_hints"])), loc)
        self.assertFalse(is_us("Cambridge", "United Kingdom"))


class Merge(unittest.TestCase):
    def kept(self, job_id="1", title="R&D Intern"):
        return {"company": "Acme", "job_id": job_id, "title": title, "industry": "food", "location": "Ann Arbor, MI",
                "remote": False, "url": "u", "posted": None, "term": "unspecified", "eligibility_flag": "unclear",
                "source": "greenhouse", "feed": "Acme", "matched": [], "score": 3}

    def test_new_then_closed_then_never_deleted(self):
        store, new = merge.merge({"postings": []}, [self.kept()], set(), {"Acme"}, "2026-11-01")
        self.assertEqual(len(new), 1)
        store, new = merge.merge(store, [], {"Acme::1"}, {"Acme"}, "2026-11-02")
        self.assertEqual((new, store["postings"][0]["last_seen"], store["postings"][0]["status"]), ([], "2026-11-02", "open"))
        store, _ = merge.merge(store, [], set(), {"Acme"}, "2026-11-03")
        p = store["postings"][0]
        self.assertEqual((p["status"], p["last_seen"], p["first_seen"]), ("closed", "2026-11-02", "2026-11-01"))

    def test_failed_feed_does_not_close(self):
        store, _ = merge.merge({"postings": []}, [self.kept()], set(), {"Acme"}, "2026-11-01")
        store, _ = merge.merge(store, [], set(), set(), "2026-11-02")
        self.assertEqual(store["postings"][0]["status"], "open")

    def test_fallback_dedupe_on_title_and_location(self):
        store, _ = merge.merge({"postings": []}, [self.kept("1")], set(), {"Acme"}, "2026-11-01")
        store, new = merge.merge(store, [self.kept("99")], set(), {"Acme"}, "2026-11-02")
        self.assertEqual((len(store["postings"]), new, store["postings"][0]["id"]), (1, [], "Acme::99"))


if __name__ == "__main__":
    unittest.main()
