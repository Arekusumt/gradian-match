from gradianmatch.platforms import list_platforms, search_jobs, JobPosting

class FakeResp:
    def __init__(self, payload): self._p = payload; self.status_code = 200
    def json(self): return self._p
class FakeHttp:
    def __init__(self, routes): self.routes = routes; self.calls = []
    def get(self, url, **kw):
        self.calls.append(url)
        key = next(k for k in self.routes if url.startswith(k))
        return FakeResp(self.routes[key])

def test_applier_platforms_include_paste_and_api():
    ids = {p.id for p in list_platforms("applier")}
    assert {"adzuna", "arbeitnow", "remotive"} <= ids
    kinds = {p.id: p.kind for p in list_platforms("applier")}
    assert kinds["infojobs"] == "paste" and kinds["arbeitnow"] == "api"

def test_search_arbeitnow_maps_to_jobposting():
    http = FakeHttp({"https://www.arbeitnow.com/api/job-board-api":
        {"data": [{"title": "Data Analyst", "company_name": "ACME",
                   "location": "Remote", "url": "https://x/y", "description": "SQL"}]}})
    jobs = search_jobs("data analyst", ["arbeitnow"], http, cfg=None)
    assert len(jobs) == 1 and isinstance(jobs[0], JobPosting)
    assert jobs[0].company == "ACME" and jobs[0].source == "arbeitnow"

def test_adzuna_skipped_without_keys():
    http = FakeHttp({})
    jobs = search_jobs("x", ["adzuna"], http, cfg=None)  # no keys → skip, no crash
    assert jobs == []
