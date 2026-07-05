from __future__ import annotations
import re
from dataclasses import dataclass
from gradianmatch.platforms import JobPosting, search_jobs

@dataclass
class QuerySpec:
    query: str; location: str = ""

@dataclass
class RankedJob:
    posting: JobPosting; score: int

_QUERY_PROMPT = ("Extract a concise job-search query and location from this profile. "
                 "Return ONLY JSON: {\"query\": str, \"location\": str}.\nPROFILE:\n")

def build_query(cv_text: str, conditions: str, claude) -> QuerySpec:
    profile = "\n".join(p for p in (conditions, cv_text) if p)
    if claude is not None and profile:
        data = claude.run_json(_QUERY_PROMPT + profile)
        return QuerySpec(query=data.get("query", ""), location=data.get("location", ""))
    words = re.findall(r"[^\W\d_]{3,}", profile.lower(), re.UNICODE)
    stop = {"the", "and", "for", "with", "amb", "les", "los", "una", "que"}
    return QuerySpec(query=" ".join(w for w in words if w not in stop)[:80])

def _relevance(posting: JobPosting, terms: set[str]) -> int:
    hay = (posting.title + " " + posting.description).lower()
    hits = sum(1 for t in terms if t in hay)
    return min(100, round(100 * hits / max(1, len(terms))))

def find_jobs(cv_text: str, conditions: str, platform_ids: list[str], claude, http, cfg,
              searcher=search_jobs) -> list["RankedJob"]:
    spec = build_query(cv_text, conditions, claude)
    postings = searcher(spec.query, platform_ids, http, cfg)
    terms = {w for w in re.findall(r"[^\W\d_]{3,}", spec.query.lower(), re.UNICODE)}
    ranked = [RankedJob(p, _relevance(p, terms)) for p in postings]
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked
