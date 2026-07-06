# src/gradianmatch/recruiter/rank.py
"""Rank a batch of candidate CVs against a single offer (recruiter side).

Reuses the applier's analyst so recruiter and applier score identically.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from gradianmatch.applier.analyst import analyze
from gradianmatch.scoring import CompatibilityReport
from gradianmatch.skills_taxonomy import SkillTaxonomy
from gradianmatch.verify_sources import verify_sources


@dataclass
class RankedCandidate:
    name: str
    score: int
    matched: list[str]
    missing: list[str]
    report: CompatibilityReport
    sources: list = field(default_factory=list)


def rank_candidates(offer_text: str, candidates: list[dict], claude,
                    taxonomy: SkillTaxonomy, http=None) -> list[RankedCandidate]:
    """Analyze each candidate against the offer and return them ranked by score DESC.

    ``candidates`` is a list of ``{"name": str, "cv_text": str}``. A single bad
    candidate (analyst error, malformed dict) is skipped, never fatal to the batch.
    When ``http`` is given, each CV's URLs are verified and attached to ``.sources``.
    """
    ranked: list[RankedCandidate] = []
    for cand in candidates:
        try:
            name = str((cand or {}).get("name") or "")
            cv_text = str((cand or {}).get("cv_text") or "")
            res = analyze(cv_text, offer_text, claude, taxonomy)
            report = res.report
            sources: list = []
            if http is not None:
                sources = [s.__dict__ for s in verify_sources(cv_text, http)]
            ranked.append(RankedCandidate(
                name=name,
                score=report.overall,
                matched=list(report.matched_keywords),
                missing=list(report.missing_keywords),
                report=report,
                sources=sources,
            ))
        except Exception:  # noqa: BLE001 — one bad candidate must not kill the batch
            continue
    # Stable sort: equal scores keep their original (input) order.
    ranked.sort(key=lambda c: c.score, reverse=True)
    return ranked
