from . import ashby, greenhouse, lever, simplify, smartrecruiters, workday

FETCHERS = {
    "workday": workday.fetch,
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}
