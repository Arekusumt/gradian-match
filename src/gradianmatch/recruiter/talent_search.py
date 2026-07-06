# src/gradianmatch/recruiter/talent_search.py
"""Candidate sourcing helpers (recruiter side).

- ``github_search``: GitHub user search via the public API (injectable http).
- ``xray_query``: a Google X-ray string the human runs in their own browser —
  the consent-based, ToS-friendly sourcing path (no scraping here).
"""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass
class Candidate:
    login: str
    name: str
    url: str
    location: str = ""
    source: str = ""


def _keywords_str(keywords) -> str:
    if isinstance(keywords, (list, tuple)):
        return " ".join(str(k).strip() for k in keywords if k and str(k).strip())
    return str(keywords or "").strip()


def _github_query(criteria: dict) -> str:
    language = str((criteria or {}).get("language") or "").strip()
    location = str((criteria or {}).get("location") or "").strip()
    keywords = _keywords_str((criteria or {}).get("keywords"))
    parts: list[str] = []
    if keywords:
        parts.append(f'"{keywords}"' if " " in keywords else keywords)
    if language:
        parts.append(f"language:{language}")
    if location:
        parts.append(f"location:{location}")
    parts.append("type:user")
    return " ".join(parts)


def github_search(criteria: dict, http, cfg=None) -> list[Candidate]:
    """Search GitHub users. Auth (if any) is applied by the caller's http headers."""
    q = _github_query(criteria)
    url = f"https://api.github.com/search/users?q={quote_plus(q)}&per_page=20"
    try:
        r = http.get(url)
        if getattr(r, "status_code", 0) != 200:
            return []
        items = (r.json() or {}).get("items", []) or []
    except Exception:  # noqa: BLE001 — a bad/empty response yields no candidates
        return []
    out: list[Candidate] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        login = it.get("login")
        if not login:
            continue
        out.append(Candidate(
            login=login,
            name=it.get("name") or login,
            url=it.get("html_url", ""),
            location=str(it.get("location") or ""),
            source="github",
        ))
    return out


def xray_query(role: str, location: str = "", site: str = "linkedin") -> str:
    """Build a Google X-ray search string for manual, in-browser sourcing."""
    role = (role or "").strip()
    location = (location or "").strip()
    if site == "github":
        s = f'site:github.com "{role}"'
        if location:
            s += f' "{location}"'
        return s
    # default: LinkedIn public profiles
    s = f'site:linkedin.com/in ("{role}")'
    if location:
        s += f' "{location}"'
    return s
