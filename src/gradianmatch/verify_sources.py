# src/gradianmatch/verify_sources.py
from __future__ import annotations
import re
from dataclasses import dataclass, field

_URL = re.compile(r"(https?://[^\s)]+|(?:www\.|github\.com/|linkedin\.com/)[^\s)]+)", re.I)
_GH_REPO = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+)", re.I)

@dataclass
class SourceResult:
    url: str; kind: str; ok: bool; details: dict = field(default_factory=dict)

def extract_urls(text: str) -> list[str]:
    seen, out = set(), []
    for m in _URL.finditer(text or ""):
        u = m.group(0).rstrip(".,);")
        if not u.startswith("http"):
            u = "https://" + u
        if u not in seen:
            seen.add(u); out.append(u)
    return out

def classify_url(url: str) -> str:
    u = url.lower()
    if "github.com" in u: return "github"
    if "linkedin.com" in u: return "linkedin"
    return "web"

def _verify_github(url: str, http) -> SourceResult:
    m = _GH_REPO.search(url)
    if not m:
        r = http.get(url)
        return SourceResult(url, "github", 200 <= r.status_code < 400, {"type": "profile"})
    owner, repo = m.group(1), m.group(2)
    api = f"https://api.github.com/repos/{owner}/{repo}"
    r = http.get(api)
    if r.status_code == 200:
        d = r.json()
        return SourceResult(url, "github", True, {
            "owner": d.get("owner", {}).get("login", owner),
            "repo": repo, "stars": d.get("stargazers_count", 0),
            "last_commit": d.get("pushed_at", ""), "language": d.get("language", "")})
    return SourceResult(url, "github", False, {"reason": f"repo not found ({r.status_code})"})

def _verify_web(url: str, kind: str, http) -> SourceResult:
    try:
        r = http.get(url)
        return SourceResult(url, kind, 200 <= r.status_code < 400, {"status": r.status_code})
    except Exception as e:  # noqa: BLE001
        return SourceResult(url, kind, False, {"error": str(e)[:120]})

def verify_sources(text: str, http) -> list[SourceResult]:
    out = []
    for url in extract_urls(text):
        kind = classify_url(url)
        try:
            out.append(_verify_github(url, http) if kind == "github" else _verify_web(url, kind, http))
        except Exception as e:  # noqa: BLE001 — one bad URL must not kill the batch
            out.append(SourceResult(url, kind, False, {"error": str(e)[:120]}))
    return out
