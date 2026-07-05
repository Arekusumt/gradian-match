from __future__ import annotations
from dataclasses import dataclass
from gradianmatch import config
from gradianmatch.resume_model import Resume, resume_from_dict
from gradianmatch.scoring import (OfferReqs, SemanticFit, CompatibilityReport, score_compatibility)
from gradianmatch.skills_taxonomy import SkillTaxonomy

@dataclass
class AnalyzeResult:
    report: CompatibilityReport
    offer: OfferReqs
    cv: Resume
    semantic: SemanticFit

def _load_prompt(cv_text: str, offer_text: str) -> str:
    tmpl = (config.AGENTS_DIR / "analyst.md").read_text(encoding="utf-8")
    return tmpl.replace("<<<CV>>>", cv_text).replace("<<<OFFER>>>", offer_text)

def analyze(cv_text: str, offer_text: str, claude, taxonomy: SkillTaxonomy) -> AnalyzeResult:
    data = claude.run_json(_load_prompt(cv_text, offer_text))
    cv = resume_from_dict(data.get("cv", {}))
    o = data.get("offer", {})
    offer = OfferReqs(
        title=o.get("title", ""), seniority=o.get("seniority", ""),
        must_have_skills=o.get("must_have_skills", []), nice_to_have_skills=o.get("nice_to_have_skills", []),
        min_years=int(o.get("min_years", 0) or 0), location=o.get("location", ""),
        remote=o.get("remote", None), languages=o.get("languages", []), education=o.get("education", ""))
    s = data.get("semantic", {})
    semantic = SemanticFit(score_0_100=int(s.get("score_0_100", 0) or 0),
                           rationale=s.get("rationale", ""), transferable=s.get("transferable", []),
                           red_flags=s.get("red_flags", []))
    report = score_compatibility(cv, offer, semantic, taxonomy)
    return AnalyzeResult(report=report, offer=offer, cv=cv, semantic=semantic)
