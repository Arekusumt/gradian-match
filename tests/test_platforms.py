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

def test_search_remotive_maps_to_jobposting():
    http = FakeHttp({"https://remotive.com/api/remote-jobs":
        {"jobs": [{"title": "Data Analyst", "company_name": "ACME",
                   "candidate_required_location": "Worldwide", "url": "https://r/1",
                   "description": "SQL Python"}]}})
    jobs = search_jobs("data", ["remotive"], http, cfg=None)
    assert len(jobs) == 1 and jobs[0].source == "remotive" and jobs[0].location == "Worldwide"

def test_search_adzuna_with_keys_maps_fields():
    class Cfg:
        adzuna_app_id = "id"; adzuna_app_key = "key"; jooble_key = None
    http = FakeHttp({"https://api.adzuna.com/v1/api/jobs/es/search/1":
        {"results": [{"title": "Analyst", "company": {"display_name": "ACME"},
                      "location": {"display_name": "Barcelona"}, "redirect_url": "https://a/1",
                      "description": "SQL", "salary_min": 30000}]}})
    jobs = search_jobs("analyst", ["adzuna"], http, Cfg())
    assert len(jobs) == 1 and jobs[0].company == "ACME" and jobs[0].salary == "30000"
