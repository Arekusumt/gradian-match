from gradianmatch.applier.jobs_search import build_query, find_jobs
from gradianmatch.platforms import JobPosting

class FakeClaude:
    def run_json(self, prompt, timeout=120):
        return {"query": "data analyst python sql", "location": "Barcelona"}

def fake_search(query, ids, http, cfg):
    return [JobPosting("Data Analyst", "ACME", "Barcelona", "http://x", "SQL Python", "arbeitnow"),
            JobPosting("Chef", "Resto", "Reus", "http://y", "cooking", "arbeitnow")]

def test_build_query_from_conditions_without_claude():
    q = build_query(cv_text="", conditions="python data analyst barcelona", claude=None)
    assert "python" in q.query.lower()

def test_find_jobs_ranks_relevant_first():
    jobs = find_jobs(cv_text="Python SQL analyst", conditions="", platform_ids=["arbeitnow"],
                     claude=FakeClaude(), http=None, cfg=None, searcher=fake_search)
    assert jobs[0].posting.title == "Data Analyst"
    assert jobs[0].score >= jobs[-1].score

def test_build_query_uses_both_conditions_and_cv():
    captured = {}
    class FC:
        def run_json(self, prompt, timeout=120):
            captured["prompt"] = prompt
            return {"query": "x", "location": ""}
    build_query(cv_text="Python SQL", conditions="remote Barcelona", claude=FC())
    assert "Python SQL" in captured["prompt"] and "remote Barcelona" in captured["prompt"]
