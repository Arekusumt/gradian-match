from gradianmatch.resume_model import resume_from_dict
from gradianmatch.skills_taxonomy import SkillTaxonomy
from gradianmatch.scoring import (OfferReqs, SemanticFit, score_compatibility)

CV = resume_from_dict({
    "basics": {"name": "Sam"},
    "skills": [{"name": "prog", "keywords": ["Python", "SQL", "R"]}],
    "languages": [{"language": "English", "fluency": "Fluent"}],
    "work": [{"name": "Gradian", "position": "Analyst", "startDate": "2025"}],
})

def _offer(**kw):
    base = dict(title="Data Analyst", seniority="junior",
               must_have_skills=["Python", "SQL", "Power BI"],
               nice_to_have_skills=["Azure"], min_years=1,
               location="Barcelona", remote=None, languages=["English"], education="")
    base.update(kw); return OfferReqs(**base)

def test_matched_and_missing_keywords():
    sem = SemanticFit(score_0_100=70, rationale="ok", transferable=[], red_flags=[])
    rep = score_compatibility(CV, _offer(), sem, SkillTaxonomy())
    assert "python" in {k.lower() for k in rep.matched_keywords}
    assert "power bi" in {k.lower() for k in rep.missing_keywords}
    assert 0 <= rep.overall <= 100
    assert rep.ats_coverage.score_0_100 < 100  # missing Power BI

def test_language_gate_penalizes_when_missing():
    sem = SemanticFit(score_0_100=70, rationale="", transferable=[], red_flags=[])
    rep_missing = score_compatibility(CV, _offer(languages=["German"]), sem, SkillTaxonomy())
    rep_ok = score_compatibility(CV, _offer(languages=["English"]), sem, SkillTaxonomy())
    assert rep_missing.gating.score_0_100 < rep_ok.gating.score_0_100

def test_overall_is_weighted_blend():
    sem_hi = SemanticFit(score_0_100=100, rationale="", transferable=[], red_flags=[])
    sem_lo = SemanticFit(score_0_100=0, rationale="", transferable=[], red_flags=[])
    hi = score_compatibility(CV, _offer(), sem_hi, SkillTaxonomy()).overall
    lo = score_compatibility(CV, _offer(), sem_lo, SkillTaxonomy()).overall
    assert hi > lo

def test_overall_is_clamped_to_0_100():
    lo = SemanticFit(score_0_100=-100)
    hi = SemanticFit(score_0_100=250)
    r_lo = score_compatibility(CV, _offer(must_have_skills=[], nice_to_have_skills=[], languages=[], min_years=0), lo, SkillTaxonomy())
    r_hi = score_compatibility(CV, _offer(), hi, SkillTaxonomy())
    assert 0 <= r_lo.overall <= 100 and 0 <= r_hi.overall <= 100
    assert r_hi.semantic.score_0_100 <= 100

def test_language_gate_matches_catalan_label():
    from gradianmatch.resume_model import resume_from_dict as _rfd
    cv_ca = _rfd({"languages": [{"language": "anglès", "fluency": "fluid"}]})
    sem = SemanticFit(score_0_100=70)
    rep = score_compatibility(cv_ca, _offer(must_have_skills=[], nice_to_have_skills=[], min_years=0, languages=["English"]), sem, SkillTaxonomy())
    assert rep.gating.score_0_100 == 100  # anglès satisfies English

def test_nice_to_have_miss_is_surfaced():
    sem = SemanticFit(score_0_100=70)
    rep = score_compatibility(CV, _offer(must_have_skills=["Python", "SQL"], nice_to_have_skills=["Azure"]), sem, SkillTaxonomy())
    assert any("Azure" in g for g in rep.gaps)
