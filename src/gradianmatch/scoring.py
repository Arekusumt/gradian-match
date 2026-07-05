# src/gradianmatch/scoring.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from gradianmatch.resume_model import Resume
from gradianmatch.skills_taxonomy import SkillTaxonomy

@dataclass
class OfferReqs:
    title: str = ""; seniority: str = ""
    must_have_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    min_years: int = 0; location: str = ""; remote: bool | None = None
    languages: list[str] = field(default_factory=list); education: str = ""

@dataclass
class SemanticFit:
    score_0_100: int = 0; rationale: str = ""
    transferable: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)

@dataclass
class CategoryScore:
    name: str; score_0_100: int; weight: float; details: str = ""

@dataclass
class CompatibilityReport:
    overall: int
    ats_coverage: CategoryScore
    gating: CategoryScore
    semantic: CategoryScore
    matched_keywords: list[str]
    missing_keywords: list[str]
    gaps: list[str]
    suggestions: list[str]

WEIGHTS = {"ats": 0.45, "gating": 0.25, "semantic": 0.30}

def _cv_terms(cv: Resume) -> set[str]:
    terms = set(cv.all_skill_terms())
    for w in cv.work:
        terms.add(w.position.lower())
        terms.update(h.lower() for h in w.highlights)
    for l in cv.languages:
        terms.add(l.language.lower())
    return terms

def _clamp(n) -> int:
    return max(0, min(100, int(n)))

def _ats(cv: Resume, offer: OfferReqs, tax: SkillTaxonomy):
    terms = _cv_terms(cv)
    def present(skill): return tax.match(terms, skill)
    must = offer.must_have_skills or []
    nice = offer.nice_to_have_skills or []
    matched = [s for s in must if present(s)]
    missing = [s for s in must if not present(s)]
    nice_hits = [s for s in nice if present(s)]
    nice_missing = [s for s in nice if not present(s)]
    must_score = (len(matched) / len(must)) if must else 1.0
    nice_score = (len(nice_hits) / len(nice)) if nice else 1.0
    score = round(100 * (0.8 * must_score + 0.2 * nice_score))
    detail = f"{len(matched)}/{len(must)} must-have + {len(nice_hits)}/{len(nice)} nice-to-have present"
    return CategoryScore("ATS keyword coverage", score, WEIGHTS["ats"], detail), matched, missing, nice_missing

def _cv_years(cv: Resume) -> int:
    years = 0
    for w in cv.work:
        try:
            start = int((w.startDate or "0")[:4])
            end = int((w.endDate or str(datetime.now().year))[:4])
            years += max(0, end - start)
        except ValueError:
            continue
    return years

def _gating(cv: Resume, offer: OfferReqs, tax: SkillTaxonomy):
    checks, passed = 0, 0
    notes = []
    if offer.languages:
        checks += 1
        cv_langs = {l.language.lower() for l in cv.languages}
        missing_langs = [req for req in offer.languages if not tax.match(cv_langs, req)]
        if not missing_langs:
            passed += 1
        else:
            notes.append(f"Missing language(s): {', '.join(missing_langs)}")
    if offer.min_years:
        checks += 1
        if _cv_years(cv) >= offer.min_years:
            passed += 1
        else:
            notes.append(f"Experience below {offer.min_years}y (CV ~{_cv_years(cv)}y)")
    score = round(100 * (passed / checks)) if checks else 100
    return CategoryScore("Recruiter gating", score, WEIGHTS["gating"], "; ".join(notes) or "all gates pass")

def score_compatibility(cv: Resume, offer: OfferReqs, semantic: SemanticFit,
                        taxonomy: SkillTaxonomy) -> CompatibilityReport:
    ats, matched, missing, nice_missing = _ats(cv, offer, taxonomy)
    gate = _gating(cv, offer, taxonomy)
    sem = CategoryScore("Semantic fit", _clamp(semantic.score_0_100), WEIGHTS["semantic"], semantic.rationale)
    overall = _clamp(round(ats.score_0_100 * WEIGHTS["ats"] + gate.score_0_100 * WEIGHTS["gating"]
                    + sem.score_0_100 * WEIGHTS["semantic"]))
    gaps = ([f"Missing must-have: {m}" for m in missing]
            + [f"Missing nice-to-have: {m}" for m in nice_missing] + list(semantic.red_flags))
    suggestions = ([f"Add or evidence: {m}" for m in missing]
                   + [f"Bonus: add {m}" for m in nice_missing]
                   + [f"Leverage transferable: {t}" for t in semantic.transferable])
    return CompatibilityReport(overall, ats, gate, sem, matched, missing, gaps, suggestions)
