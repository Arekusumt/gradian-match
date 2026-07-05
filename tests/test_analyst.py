from gradianmatch.applier.analyst import analyze
from gradianmatch.skills_taxonomy import SkillTaxonomy

class FakeClaude:
    def __init__(self, payload): self.payload = payload; self.prompts = []
    def run_json(self, prompt, timeout=120):
        self.prompts.append(prompt); return self.payload

PAYLOAD = {
    "cv": {"basics": {"name": "Alex"},
           "skills": [{"name": "prog", "keywords": ["Python", "SQL", "R"]}],
           "languages": [{"language": "English", "fluency": "Fluent"}]},
    "offer": {"title": "Data Analyst", "seniority": "junior",
              "must_have_skills": ["Python", "SQL", "Power BI"],
              "nice_to_have_skills": ["Azure"], "min_years": 1,
              "location": "Barcelona", "remote": None, "languages": ["English"], "education": ""},
    "semantic": {"score_0_100": 72, "rationale": "Strong Python.", "transferable": ["automation"], "red_flags": ["No Power BI"]},
}

def test_analyze_builds_report_from_claude(sample_cv_text, sample_offer_text):
    claude = FakeClaude(PAYLOAD)
    res = analyze(sample_cv_text, sample_offer_text, claude, SkillTaxonomy())
    assert res.report.overall > 0
    assert "power bi" in {k.lower() for k in res.report.missing_keywords}
    assert res.report.semantic.score_0_100 == 72
    assert "<<<CV>>>" not in claude.prompts[0]  # placeholders were substituted

class _FC:
    def __init__(self, payload): self.payload = payload
    def run_json(self, prompt, timeout=120): return self.payload

def test_analyze_survives_malformed_payload():
    bad = {"cv": None, "offer": {"min_years": "several", "must_have_skills": "Python"},
           "semantic": None}
    res = analyze("cv", "offer", _FC(bad), SkillTaxonomy())
    assert 0 <= res.report.overall <= 100
    assert res.offer.must_have_skills == ["Python"]  # bare string coerced to a list
    assert res.offer.min_years == 0                   # non-numeric coerced to 0

def test_analyze_survives_nondict_payload():
    res = analyze("cv", "offer", _FC([]), SkillTaxonomy())  # Claude returned a list
    assert res.report.overall >= 0

def test_load_prompt_does_not_reinject_placeholder():
    from gradianmatch.applier.analyst import _load_prompt
    out = _load_prompt("CV mentions <<<OFFER>>> literally", "THE_OFFER")
    assert out.count("THE_OFFER") == 1        # only the template slot was filled
    assert "<<<OFFER>>>" in out               # the literal token inside the CV survives
