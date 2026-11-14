# Summer 2027 R&D internship board

Every morning a GitHub Action pulls internship postings from public company job feeds, keeps the
US R&D ones, updates `data/postings.json`, rebuilds the page in `docs/`, and emails the new ones.

## Add a company

Open `companies.yaml` and add one line under the right industry heading.

1. Go to the company's careers site and open any job. Look at the address of the job or its Apply button.
2. Match it to a feed type:

| Address looks like | Line to add |
| --- | --- |
| `acme.wd5.myworkdayjobs.com/Careers/job/...` | `- {name: Acme, industry: food, ats: workday, tenant: acme, dc: wd5, site: Careers}` |
| `boards.greenhouse.io/acme/...` | `- {name: Acme, industry: food, ats: greenhouse, token: acme}` |
| `jobs.lever.co/acme/...` | `- {name: Acme, industry: food, ats: lever, company_id: acme}` |
| `jobs.ashbyhq.com/acme/...` | `- {name: Acme, industry: food, ats: ashby, board: acme}` |
| `jobs.smartrecruiters.com/Acme/...` | `- {name: Acme, industry: food, ats: smartrecruiters, company_id: Acme}` |
| anything else | `- {name: Acme, industry: food, ats: manual, careers_url: "https://..."}` |

`industry` is `food`, `pharma` or `adjacent`. A `manual` company only gets a link in the board's
"Manual check" section. Add `aliases: [Other Name]` to a manual company so the SimplifyJobs
community list can be matched to it.

3. Test it: `python main.py --dry-run --only "Acme"`

## Edit keywords

Everything the filter uses is in `keywords.yaml`: internship words, R&D keywords, excluded title
words, eligibility phrases. Change a list, then run `python main.py --dry-run` to see what would be
kept and what would be filtered out (with the reason). The next real run re-checks every posting
against the new lists.

How a posting is kept:

- its **title** says intern / internship / co-op;
- it is in the US (or remote);
- an R&D keyword is in the title, or at least `description_min_hits` different ones are in the description;
- no excluded word is in the title, and it is not PhD-only;
- it does not clearly target a different term than `profile.target_term`.

`data/rejected.json` lists postings that were read and rejected, with the reason. It is the best
place to look when tuning.

## Run it locally

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python -m unittest discover -s tests     # tests
    .venv/bin/python main.py --dry-run                 # prints results; writes and emails nothing
    .venv/bin/python main.py                           # real run (updates data/ and docs/)
    .venv/bin/python main.py --refresh                 # re-read every description, ignoring the cache

## Files

| File | What it does |
| --- | --- |
| `companies.yaml` | company -> job feed (or "manual") |
| `keywords.yaml` | all filter words and settings |
| `fetchers/` | one module per feed type |
| `filter.py` | keep/drop decision, term and eligibility labels |
| `merge.py` | merges into `data/postings.json`; marks vanished postings closed, never deletes |
| `build_site.py` | writes `docs/data.json` for the page |
| `notify.py` | the email digest |
| `main.py` | runs all of the above |
| `.github/workflows/daily.yml` | the daily schedule |

Statuses you set on the board (Interested / Applied / Not a fit) are saved in your browser only.
