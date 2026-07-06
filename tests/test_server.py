import httpx
from fastapi.testclient import TestClient

from gradianmatch import server


class _FakeClaude:
    def run_json(self, prompt, timeout=120):
        return {"cv": {"basics": {"name": "Alex"}, "skills": [{"name": "p", "keywords": ["Python"]}]},
                "offer": {"title": "Analyst", "must_have_skills": ["Python", "Power BI"],
                          "nice_to_have_skills": [], "min_years": 0, "languages": [], "seniority": "junior",
                          "location": "", "remote": None, "education": ""},
                "semantic": {"score_0_100": 70, "rationale": "ok", "transferable": [], "red_flags": []}}

    def check_available(self):
        return True, "ok"


def make_client(monkeypatch):
    monkeypatch.setattr(server, "get_claude", lambda: _FakeClaude())
    return TestClient(server.app)


def test_health(monkeypatch):
    c = make_client(monkeypatch)
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["claude_ok"] is True


def test_analyze_endpoint(monkeypatch):
    c = make_client(monkeypatch)
    r = c.post("/api/analyze", json={"cv": {"kind": "text", "value": "Python analyst"},
                                     "offer": {"kind": "text", "value": "Need Python and Power BI"}})
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] >= 0
    assert "power bi" in {k.lower() for k in body["missing_keywords"]}


def test_platforms_endpoint(monkeypatch):
    c = make_client(monkeypatch)
    r = c.get("/api/platforms?side=applier")
    ids = {p["id"] for p in r.json()}
    assert "arbeitnow" in ids


def test_analyze_bad_url_returns_clean_error(monkeypatch):
    """A source that fails to fetch/extract must degrade to a clean JSON error,
    never an unhandled 500 stack trace bubbling out of the ASGI app."""
    c = make_client(monkeypatch)

    def _boom(value, kind, fetcher=None):
        raise httpx.ConnectError("could not connect")

    monkeypatch.setattr(server, "extract_text", _boom)
    r = c.post("/api/analyze", json={"cv": {"kind": "url", "value": "http://nonexistent.invalid/cv"},
                                     "offer": {"kind": "text", "value": "Need Python"}})
    assert r.status_code >= 400
    assert "error" in r.json()


def test_regenerate_endpoint(monkeypatch):
    c = make_client(monkeypatch)
    r = c.post("/api/regenerate", json={"cv": {"kind": "text", "value": "Python"},
               "offer": {"kind": "text", "value": "Need Python"}, "aggressiveness": 50})
    assert r.status_code == 200
    b = r.json()
    assert "critic_score" in b and "iterations" in b and "resume" in b


def test_jobs_endpoint_no_network(monkeypatch):
    c = make_client(monkeypatch)
    r = c.post("/api/jobs", json={"cv_text": "Python analyst", "conditions": "", "platform_ids": []})
    assert r.status_code == 200 and r.json() == []


def test_verify_endpoint_no_urls(monkeypatch):
    c = make_client(monkeypatch)
    r = c.post("/api/verify", json={"kind": "text", "value": "no links here"})
    assert r.status_code == 200 and r.json() == []


def test_pdf_kind_rejected_on_analyze(monkeypatch):
    c = make_client(monkeypatch)
    r = c.post("/api/analyze", json={"cv": {"kind": "pdf", "value": "C:/secret.pdf"},
               "offer": {"kind": "text", "value": "x"}})
    assert r.status_code == 400 and "error" in r.json()


def test_origin_guard(monkeypatch):
    c = make_client(monkeypatch)
    assert c.get("/api/health", headers={"origin": "https://evil.example"}).status_code == 403
    assert c.get("/api/health", headers={"origin": "http://127.0.0.1:8765"}).status_code == 200


def test_upload_text_returns_extracted_text(monkeypatch):
    c = make_client(monkeypatch)
    r = c.post("/api/upload", files={"file": ("cv.txt", b"Python analyst", "text/plain")})
    assert r.status_code == 200 and "Python" in r.json()["text"]


def test_analyze_stream_emits_agents_and_result(monkeypatch):
    c = make_client(monkeypatch)
    with c.stream("POST", "/api/analyze/stream",
                  json={"cv": {"kind": "text", "value": "Python analyst"},
                        "offer": {"kind": "text", "value": "Need Python and Power BI"}}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert '"type": "start"' in body
    assert '"agent": "analyst"' in body
    assert '"type": "result"' in body
    assert '"type": "done"' in body


def test_regenerate_stream_runs_loop(monkeypatch):
    c = make_client(monkeypatch)
    with c.stream("POST", "/api/regenerate/stream",
                  json={"cv": {"kind": "text", "value": "Python"},
                        "offer": {"kind": "text", "value": "Need Python"}, "aggressiveness": 60}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert '"agent": "tailor"' in body and '"agent": "critic"' in body
    assert '"type": "result"' in body


def test_health_reports_backend(monkeypatch):
    c = make_client(monkeypatch)
    b = c.get("/api/health").json()
    assert "backend" in b and b["backend"]["backend"] in ("cli", "api")


def test_pdf_endpoint(monkeypatch):
    from gradianmatch.render_pdf import find_chrome
    if find_chrome() is None:
        import pytest; pytest.skip("no chrome/edge")
    c = make_client(monkeypatch)
    r = c.post("/api/pdf", json={"resume": {"basics": {"name": "Alex"}}})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
