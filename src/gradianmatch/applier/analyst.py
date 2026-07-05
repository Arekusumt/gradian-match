from __future__ import annotations
import re
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

def _as_int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def _as_str_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v if x is not None]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []

def _load_prompt(cv_text: str, offer_text: str) -> str:
    tmpl = (config.AGENTS_DIR / "analyst.md").read_text(encoding="utf-8")
    repl = {"<<<CV>>>": cv_text, "<<<OFFER>>>": offer_text}
    return re.sub(r"<<<CV>>>|<<<OFFER>>>", lambda m: repl[m.group(0)], tmpl)

def analyze(cv_text: str, offer_text: str, claude, taxonomy: SkillTaxonomy) -> AnalyzeResult:
    data = claude.run_json(_load_prompt(cv_text, offer_text))
    if not isinstance(data, dict):
        data = {}
    cv = resume_from_dict(data.get("cv") or {})
    o = data.get("offer") or {}
    if not isinstance(o, dict):
        o = {}
    offer = OfferReqs(
        title=str(o.get("title") or ""), seniority=str(o.get("seniority") or ""),
        must_have_skills=_as_str_list(o.get("must_have_skills")),
        nice_to_have_skills=_as_str_list(o.get("nice_to_have_skills")),
        min_years=_as_int(o.get("min_years")),
        location=str(o.get("location") or ""),
        remote=o.get("remote", None),
        languages=_as_str_list(o.get("languages")),
        education=str(o.get("education") or ""))
    s = data.get("semantic") or {}
    if not isinstance(s, dict):
        s = {}
    semantic = SemanticFit(
        score_0_100=_as_int(s.get("score_0_100")),
        rationale=str(s.get("rationale") or ""),
        transferable=_as_str_list(s.get("transferable")),
        red_flags=_as_str_list(s.get("red_flags")))
    report = score_compatibility(cv, offer, semantic, taxonomy)
    return AnalyzeResult(report=report, offer=offer, cv=cv, semantic=semantic)
