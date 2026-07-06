from gradianmatch.recruiter.rank import rank_candidates, RankedCandidate
from gradianmatch.skills_taxonomy import SkillTaxonomy

OFFER = {"title": "Data Analyst", "seniority": "junior",
         "must_have_skills": ["Python", "SQL", "Power BI"],
         "nice_to_have_skills": ["Azure"], "min_years": 0,
         "location": "Barcelona", "remote": None, "languages": [], "education": ""}


def _payload(skills, sem):
    return {"cv": {"basics": {"name": "x"},
                   "skills": [{"name": "prog", "keywords": skills}]},
            "offer": OFFER,
            "semantic": {"score_0_100": sem, "rationale": "ok",
                         "transferable": [], "red_flags": []}}


# Alice matches every must-have + high semantic; Bob matches one + low semantic.
ALICE = _payload(["Python", "SQL", "Power BI"], 90)
BOB = _payload(["Python"], 40)


class FakeClaude:
    """Returns a payload keyed by a marker present in the CV text (=> in the prompt)."""

    def __init__(self, by_marker):
        self.by_marker = by_marker

    def run_json(self, prompt, timeout=300):
        for marker, payload in self.by_marker.items():
            if marker in prompt:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        return {}


class FakeResp:
    def __init__(self, status):
        self.status_code = status

    def json(self):
        return {}


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes

    def get(self, url, **kw):
        return self.routes.get(url, FakeResp(404))


def test_ranks_by_score_desc():
    claude = FakeClaude({"ALICE": ALICE, "BOB": BOB})
    cands = [{"name": "Bob", "cv_text": "BOB candidate"},
             {"name": "Alice", "cv_text": "ALICE candidate"}]
    ranked = rank_candidates("offer text", cands, claude, SkillTaxonomy())
    assert [c.name for c in ranked] == ["Alice", "Bob"]
    assert isinstance(ranked[0], RankedCandidate)
    assert ranked[0].score >= ranked[1].score
    # matched / missing populated from the report
    assert "power bi" in {k.lower() for k in ranked[0].matched}
    assert "power bi" in {k.lower() for k in ranked[1].missing}
    assert ranked[0].sources == []  # no http => no source verification


def test_bad_candidate_is_skipped_not_fatal():
    claude = FakeClaude({"ALICE": ALICE, "BOOM": RuntimeError("bad cv")})
    cands = [{"name": "Alice", "cv_text": "ALICE candidate"},
             {"name": "Carol", "cv_text": "BOOM candidate"}]
    ranked = rank_candidates("offer", cands, claude, SkillTaxonomy())
    assert [c.name for c in ranked] == ["Alice"]  # Carol raised => skipped


def test_stable_order_for_equal_scores():
    claude = FakeClaude({"ONE": BOB, "TWO": BOB})  # identical score
    cands = [{"name": "One", "cv_text": "ONE"}, {"name": "Two", "cv_text": "TWO"}]
    ranked = rank_candidates("offer", cands, claude, SkillTaxonomy())
    assert [c.name for c in ranked] == ["One", "Two"]  # original order kept


def test_sources_attached_when_http_given():
    claude = FakeClaude({"ALICE": ALICE})
    http = FakeHttp({"https://github.com/alice": FakeResp(200)})
    cands = [{"name": "Alice", "cv_text": "ALICE profile github.com/alice"}]
    ranked = rank_candidates("offer", cands, claude, SkillTaxonomy(), http=http)
    assert ranked[0].sources and isinstance(ranked[0].sources[0], dict)
    gh = ranked[0].sources[0]
    assert gh["kind"] == "github" and gh["ok"] is True and "url" in gh
