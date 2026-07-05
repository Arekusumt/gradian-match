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
