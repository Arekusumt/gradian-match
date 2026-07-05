# src/gradianmatch/platforms.py
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Platform:
    id: str; label: str; side: str; kind: str  # kind: api|paste|xray|local
    note: str = ""

@dataclass
class JobPosting:
    title: str; company: str; location: str; url: str
    description: str = ""; source: str = ""; salary: str = ""

_REGISTRY = [
    Platform("adzuna", "Adzuna", "applier", "api", "Spain + international; free dev key"),
    Platform("arbeitnow", "Arbeitnow", "applier", "api", "Free, no key"),
    Platform("remotive", "Remotive", "applier", "api", "Remote roles, free"),
    Platform("jooble", "Jooble", "applier", "api", "Free key"),
    Platform("infojobs", "InfoJobs", "applier", "paste", "No open API — paste an offer link"),
    Platform("indeed", "Indeed", "applier", "paste", "No open API — paste an offer link"),
    Platform("linkedin_jobs", "LinkedIn Jobs", "applier", "paste", "ToS — paste an offer link"),
    Platform("github", "GitHub", "recruiter", "api", "Candidate sourcing (phase 2)"),
    Platform("linkedin_xray", "LinkedIn X-ray", "recruiter", "xray", "Generated search string (phase 2)"),
    Platform("uploaded_cvs", "Uploaded CVs", "recruiter", "local", "Rank CVs you already have"),
]

def list_platforms(side: str) -> list[Platform]:
    return [p for p in _REGISTRY if p.side == side]

def _search_arbeitnow(query, http, cfg) -> list[JobPosting]:
    r = http.get("https://www.arbeitnow.com/api/job-board-api")
    data = r.json().get("data", [])
    q = query.lower()
    out = []
    for j in data:
        if q and q not in (j.get("title", "") + j.get("description", "")).lower():
            continue
        out.append(JobPosting(j.get("title", ""), j.get("company_name", ""),
                              j.get("location", ""), j.get("url", ""),
                              j.get("description", ""), "arbeitnow"))
    return out

def _search_remotive(query, http, cfg) -> list[JobPosting]:
    r = http.get(f"https://remotive.com/api/remote-jobs?search={query}")
    out = []
    for j in r.json().get("jobs", []):
        out.append(JobPosting(j.get("title", ""), j.get("company_name", ""),
                              j.get("candidate_required_location", ""), j.get("url", ""),
                              j.get("description", ""), "remotive"))
    return out

def _search_adzuna(query, http, cfg) -> list[JobPosting]:
    if not (cfg and cfg.adzuna_app_id and cfg.adzuna_app_key):
        return []
    url = (f"https://api.adzuna.com/v1/api/jobs/es/search/1?app_id={cfg.adzuna_app_id}"
           f"&app_key={cfg.adzuna_app_key}&what={query}&results_per_page=20")
    r = http.get(url)
    out = []
    for j in r.json().get("results", []):
        sal = j.get("salary_min")
        out.append(JobPosting(j.get("title", ""), j.get("company", {}).get("display_name", ""),
                              j.get("location", {}).get("display_name", ""), j.get("redirect_url", ""),
                              j.get("description", ""), "adzuna", str(sal) if sal else ""))
    return out

def _search_jooble(query, http, cfg) -> list[JobPosting]:
    if not (cfg and cfg.jooble_key):
        return []
    return []

_SEARCHERS = {"arbeitnow": _search_arbeitnow, "remotive": _search_remotive,
              "adzuna": _search_adzuna, "jooble": _search_jooble}

def search_jobs(query: str, platform_ids: list[str], http, cfg) -> list[JobPosting]:
    out: list[JobPosting] = []
    for pid in platform_ids:
        fn = _SEARCHERS.get(pid)
        if not fn:
            continue
        try:
            out.extend(fn(query, http, cfg))
        except Exception:  # noqa: BLE001 — one bad source must not kill the search
            continue
    return out
