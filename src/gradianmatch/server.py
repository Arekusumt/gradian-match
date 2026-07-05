# src/gradianmatch/server.py
from __future__ import annotations
from dataclasses import asdict
from functools import wraps

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gradianmatch import config
from gradianmatch.claude_client import ClaudeClient, ClaudeError
from gradianmatch.skills_taxonomy import SkillTaxonomy
from gradianmatch.extract import extract_text
from gradianmatch.resume_model import resume_to_dict
from gradianmatch.scoring import CompatibilityReport
from gradianmatch.applier.analyst import analyze
from gradianmatch.applier.regenerate import regenerate
from gradianmatch.applier.jobs_search import find_jobs
from gradianmatch.platforms import list_platforms
from gradianmatch.verify_sources import verify_sources

app = FastAPI(title="Gradian Match")
_TAX = SkillTaxonomy()
_CFG = config.load_config()


def get_claude() -> ClaudeClient:  # patched in tests
    return ClaudeClient()


def _http() -> httpx.Client:
    headers = {"User-Agent": "GradianMatch/0.1"}
    if _CFG.github_token:
        headers["Authorization"] = f"token {_CFG.github_token}"
    return httpx.Client(timeout=25, headers=headers, follow_redirects=True)


class ApiError(Exception):
    """Raised by route handlers to surface a clean JSON error response instead of
    letting a bad URL fetch / Claude failure / anything unexpected bubble up as a
    raw, unhandled 500 stack trace."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@app.exception_handler(ApiError)
def _handle_api_error(request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


def _guarded(fn):
    """Endpoint decorator: map expected failure modes to clean JSON errors.

    Order matters — ApiError is re-raised as-is (already the right shape), known
    transport/Claude failures get a 502, bad input a 400, and anything else a 500
    with a short message. Nothing is ever left to escape as a raw traceback.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError:
            raise
        except ClaudeError as e:
            raise ApiError(502, f"Claude Code error: {e}") from e
        except httpx.HTTPError as e:
            raise ApiError(502, f"Network error fetching source: {e}") from e
        except ValueError as e:
            raise ApiError(400, str(e)) from e
        except Exception as e:  # noqa: BLE001 — last resort, never leak a raw 500 trace
            raise ApiError(500, f"Unexpected error: {e}") from e
    return wrapper


class Source(BaseModel):
    kind: str  # "text" | "url" | "pdf" (path)
    value: str


class AnalyzeReq(BaseModel):
    cv: Source
    offer: Source


class RegenReq(BaseModel):
    cv: Source
    offer: Source
    aggressiveness: int = 50


class JobsReq(BaseModel):
    cv_text: str = ""
    conditions: str = ""
    platform_ids: list[str] = ["arbeitnow", "remotive"]


def _text(src: Source) -> str:
    return extract_text(src.value, src.kind).text


def _report_to_json(rep: CompatibilityReport) -> dict:
    return {"overall": rep.overall,
            "categories": [asdict(rep.ats_coverage), asdict(rep.gating), asdict(rep.semantic)],
            "matched_keywords": rep.matched_keywords, "missing_keywords": rep.missing_keywords,
            "gaps": rep.gaps, "suggestions": rep.suggestions}


@app.get("/api/health")
def health():
    ok, msg = get_claude().check_available()
    return {"claude_ok": ok, "message": msg}


@app.get("/api/platforms")
def platforms(side: str = "applier"):
    return [asdict(p) for p in list_platforms(side)]


@app.post("/api/analyze")
@_guarded
def api_analyze(req: AnalyzeReq):
    res = analyze(_text(req.cv), _text(req.offer), get_claude(), _TAX)
    return _report_to_json(res.report)


@app.post("/api/regenerate")
@_guarded
def api_regenerate(req: RegenReq):
    res = analyze(_text(req.cv), _text(req.offer), get_claude(), _TAX)
    out = regenerate(res.cv, res.offer, req.aggressiveness, get_claude())
    return {"resume": resume_to_dict(out.resume),
            "ledger": [l.__dict__ for l in out.ledger],
            "critic_score": out.critic_score, "iterations": out.iterations, "passed": out.passed}


@app.post("/api/jobs")
@_guarded
def api_jobs(req: JobsReq):
    with _http() as http:
        ranked = find_jobs(req.cv_text, req.conditions, req.platform_ids, get_claude(), http, _CFG)
    return [{"score": r.score, **r.posting.__dict__} for r in ranked]


@app.post("/api/verify")
@_guarded
def api_verify(req: Source):
    text = _text(req)
    with _http() as http:
        return [r.__dict__ for r in verify_sources(text, http)]


# static UI last so /api/* always wins the route match
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")
