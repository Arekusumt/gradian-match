# src/gradianmatch/server.py
from __future__ import annotations
import os, tempfile
from dataclasses import asdict
from functools import wraps

import httpx
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.background import BackgroundTask
from pydantic import BaseModel

from gradianmatch import config
from gradianmatch.claude_client import ClaudeClient, ClaudeError
from gradianmatch.skills_taxonomy import SkillTaxonomy
from gradianmatch.extract import extract_text
from gradianmatch.render_pdf import render_pdf
from gradianmatch.resume_model import resume_from_dict, resume_to_dict
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


# This app binds to localhost and is meant for the machine's own user. Reject any
# request carrying a cross-origin Origin header so a malicious page in the user's
# browser can't drive the local API on their behalf (CSRF-style abuse).
_LOCAL_ORIGINS = ("http://127.0.0.1", "http://localhost")


@app.middleware("http")
async def _origin_guard(request, call_next):
    origin = request.headers.get("origin")
    if origin and not origin.startswith(_LOCAL_ORIGINS):
        return JSONResponse({"error": "cross-origin request blocked"}, status_code=403)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def _validation_handler(request, exc):
    # Normalize pydantic's verbose 422 body into our {"error": ...} contract.
    return JSONResponse({"error": "Invalid request body."}, status_code=422)


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
    # Allowlist: never let a JSON body hand us an arbitrary local file path to read.
    # PDFs are uploaded through /api/upload (multipart), never as a client-supplied path.
    if src.kind not in ("text", "url"):
        raise ApiError(400, "Unsupported input kind here; upload PDFs via /api/upload.")
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


class PdfReq(BaseModel):
    resume: dict


@app.post("/api/pdf")
@_guarded
def api_pdf(req: PdfReq):
    resume = resume_from_dict(req.resume)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    render_pdf(resume, path)
    return FileResponse(path, media_type="application/pdf", filename="gradian-match-cv.pdf",
                        background=BackgroundTask(os.remove, path))


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    # async, so it can't use the sync _guarded decorator — handles errors inline.
    try:
        data = await file.read()
        is_pdf = (file.filename or "").lower().endswith(".pdf")
        if is_pdf:
            fd, path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                with open(path, "wb") as f:
                    f.write(data)
                text = extract_text(path, "pdf").text
            finally:
                os.remove(path)
        else:
            text = data.decode("utf-8", errors="replace")
        return {"text": text}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"Upload failed: {e}"}, status_code=400)


# static UI last so /api/* always wins the route match
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")
